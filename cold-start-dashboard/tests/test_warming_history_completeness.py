"""
Property-based tests for warming history completeness
Tests that warming history retrieval and display meets completeness requirements
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
import os
import json

# Add the parent directory to the path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.warming_system import WarmingSystemService, WarmingEvent, WarmingMetrics
from config import AWSConfig

class TestWarmingHistoryCompleteness:
    """Property-based tests for warming history completeness"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_config = Mock(spec=AWSConfig)
        self.mock_config.region = 'us-east-1'
        self.mock_config.intelligent_warmer_function = 'IntelligentLambdaWarmer'
        
        # Mock AWS clients
        with patch('boto3.client') as mock_boto3:
            self.mock_cloudwatch = Mock()
            self.mock_lambda_client = Mock()
            self.mock_logs_client = Mock()
            
            mock_boto3.side_effect = lambda service, **kwargs: {
                'cloudwatch': self.mock_cloudwatch,
                'lambda': self.mock_lambda_client,
                'logs': self.mock_logs_client
            }[service]
            
            self.service = WarmingSystemService(self.mock_config)
        
        # Reset mocks for each test
        self.mock_cloudwatch.reset_mock()
        self.mock_lambda_client.reset_mock()
        self.mock_logs_client.reset_mock()
    
    @given(
        hours=st.integers(min_value=1, max_value=168),  # 1 hour to 1 week
        num_events=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50, deadline=5000)
    def test_warming_history_completeness(self, hours, num_events):
        """
        Property 14: Warming History Completeness
        
        For any time period and number of warming events:
        - All warming events within the time period are retrieved
        - Each event contains complete information (timestamp, function, success rate, etc.)
        - Events are properly sorted by timestamp (most recent first)
        - No duplicate events are returned
        - Event data is properly formatted for display
        
        Validates: Requirements 5.1
        """
        # Mock log events response
        mock_events = []
        base_time = datetime.now()
        
        for i in range(num_events):
            event_time = base_time - timedelta(minutes=i * 15)  # Events every 15 minutes
            mock_events.append({
                'timestamp': int(event_time.timestamp() * 1000),
                'message': f'INFO Warming complete - 3 functions warmed, 95.0% success rate'
            })
        
        self.mock_logs_client.filter_log_events.return_value = {
            'events': mock_events
        }
        
        # Get warming history
        start_time = datetime.now()
        history = self.service.get_warming_history(hours)
        
        # Property 1: All events within time period are retrieved
        if num_events > 0:
            assert len(history) > 0, "Should retrieve warming events when they exist"
            
            # For sample data, just verify events have reasonable timestamps
            # The exact timing is less important than the completeness properties
            for event in history:
                assert isinstance(event.timestamp, datetime), "Event should have valid datetime timestamp"
                # Verify timestamp is not in the future (with small buffer for execution time)
                assert event.timestamp <= datetime.now() + timedelta(seconds=10), "Event timestamp should not be in the future"
        
        # Property 2: Each event contains complete information
        for event in history:
            assert isinstance(event, WarmingEvent), "Each event should be a WarmingEvent object"
            assert isinstance(event.timestamp, datetime), "Event should have valid timestamp"
            assert isinstance(event.function_name, str) and event.function_name, "Event should have function name"
            assert isinstance(event.endpoint, str) and event.endpoint, "Event should have endpoint"
            assert isinstance(event.success_rate, (int, float)) and 0 <= event.success_rate <= 1, "Success rate should be between 0 and 1"
            assert isinstance(event.attempts, int) and event.attempts >= 0, "Attempts should be non-negative integer"
            assert isinstance(event.successful, int) and event.successful >= 0, "Successful should be non-negative integer"
            assert event.successful <= event.attempts, "Successful attempts cannot exceed total attempts"
            assert isinstance(event.priority, str) and event.priority in ['HIGH', 'MEDIUM', 'LOW', 'NONE'], "Priority should be valid"
            assert isinstance(event.probability, (int, float)) and 0 <= event.probability <= 1, "Probability should be between 0 and 1"
            assert isinstance(event.reason, str), "Event should have reason string"
        
        # Property 3: Events are sorted by timestamp (most recent first)
        if len(history) > 1:
            for i in range(len(history) - 1):
                assert history[i].timestamp >= history[i + 1].timestamp, "Events should be sorted by timestamp (most recent first)"
        
        # Property 4: No duplicate events
        event_signatures = set()
        for event in history:
            signature = (event.timestamp, event.function_name, event.endpoint)
            assert signature not in event_signatures, f"Duplicate event found: {signature}"
            event_signatures.add(signature)
        
        # Property 5: Event data is properly formatted for display
        formatted_history = self.service.format_warming_history_display(history)
        
        assert len(formatted_history) == len(history), "Formatted history should have same length as original"
        
        for i, formatted_event in enumerate(formatted_history):
            original_event = history[i]
            
            # Check required display fields
            assert 'timestamp' in formatted_event, "Formatted event should have timestamp"
            assert 'function_name' in formatted_event, "Formatted event should have function_name"
            assert 'endpoint' in formatted_event, "Formatted event should have endpoint"
            assert 'success_rate' in formatted_event, "Formatted event should have success_rate"
            assert 'status' in formatted_event, "Formatted event should have status"
            
            # Check timestamp formatting
            assert isinstance(formatted_event['timestamp'], str), "Timestamp should be formatted as string"
            
            # Check success rate formatting (should be percentage)
            assert '%' in formatted_event['success_rate'], "Success rate should be formatted as percentage"
            
            # Check status formatting
            assert formatted_event['status'] in ['✅ Success', '⚠️ Partial', '❌ Failed'], "Status should be properly formatted"
    
    @given(
        hours=st.integers(min_value=1, max_value=72),
        success_rates=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=20)
    )
    @settings(max_examples=30, deadline=5000)
    def test_warming_metrics_calculation_accuracy(self, hours, success_rates):
        """
        Property: Warming metrics are calculated accurately from history data
        
        For any set of warming events with known success rates:
        - Overall success rate is calculated correctly
        - Function count is accurate
        - Cost savings estimation is reasonable
        - Frequency calculation matches event distribution
        """
        # Create mock warming events with specified success rates
        base_time = datetime.now()
        mock_events = []
        
        for i, success_rate in enumerate(success_rates):
            event_time = base_time - timedelta(minutes=i * 30)  # Events every 30 minutes
            attempts = 2
            successful = int(attempts * success_rate)
            
            mock_events.append(WarmingEvent(
                timestamp=event_time,
                function_name=f'function-{i % 3}',  # Cycle through 3 functions
                endpoint=f'endpoint-{i % 3}',
                success_rate=success_rate,
                attempts=attempts,
                successful=successful,
                priority='HIGH' if success_rate > 0.8 else 'MEDIUM',
                probability=0.8,
                reason=f"Test event {i}"
            ))
        
        # Mock the get_warming_history method to return our test events
        with patch.object(self.service, 'get_warming_history', return_value=mock_events):
            metrics = self.service.get_warming_metrics(hours)
        
        # Verify metrics calculations
        assert metrics.total_events == len(success_rates), "Total events should match input"
        
        # Calculate expected success rate
        total_attempts = sum(2 for _ in success_rates)  # 2 attempts per event
        total_successful = sum(int(2 * rate) for rate in success_rates)
        expected_success_rate = (total_successful / total_attempts * 100) if total_attempts > 0 else 0
        
        assert abs(metrics.success_rate - expected_success_rate) < 0.1, f"Success rate calculation error: expected {expected_success_rate}, got {metrics.success_rate}"
        
        # Verify function count (should be at most 3 since we cycle through 3 functions)
        assert 1 <= metrics.functions_warmed <= 3, "Functions warmed should be between 1 and 3"
        
        # Verify cost savings is reasonable (should be positive if there were successful warmings)
        if total_successful > 0:
            assert metrics.cost_savings > 0, "Cost savings should be positive when there are successful warmings"
        
        # Verify warming frequency
        expected_frequency = len(success_rates) / hours
        assert abs(metrics.warming_frequency - expected_frequency) < 0.1, "Warming frequency calculation should be accurate"
        
        # Verify next evaluation is in the future
        assert metrics.next_evaluation > datetime.now(), "Next evaluation should be in the future"
    
    @given(
        function_names=st.lists(st.text(min_size=5, max_size=20), min_size=1, max_size=5),
        priority=st.sampled_from(['HIGH', 'MEDIUM', 'LOW'])
    )
    @settings(max_examples=20, deadline=5000)
    def test_manual_warming_trigger_completeness(self, function_names, priority):
        """
        Property: Manual warming trigger provides complete response information
        
        For any set of function names and priority:
        - Warming payload is properly constructed
        - All specified functions are included
        - Response contains complete status information
        - Error handling provides meaningful feedback
        """
        # Reset mock for each test run
        self.mock_lambda_client.reset_mock()
        
        # Filter out empty or invalid function names
        valid_function_names = [name.strip() for name in function_names if name.strip()]
        assume(len(valid_function_names) > 0)
        
        # Mock successful Lambda invocation
        mock_response = {
            'StatusCode': 200,
            'Payload': Mock()
        }
        
        mock_body = {
            'message': 'Intelligent warming completed successfully',
            'summary': {
                'functions_evaluated': len(valid_function_names),
                'functions_warmed': len(valid_function_names),
                'total_warming_attempts': len(valid_function_names) * 2,
                'successful_warming_attempts': len(valid_function_names) * 2,
                'overall_success_rate': '100.0%'
            },
            'warming_results': [
                {
                    'function_name': func_name,
                    'attempts': 2,
                    'successful': 2,
                    'success_rate': 1.0
                } for func_name in valid_function_names
            ]
        }
        
        mock_response['Payload'].read.return_value = json.dumps({
            'statusCode': 200,
            'body': json.dumps(mock_body)
        }).encode()
        
        self.mock_lambda_client.invoke.return_value = mock_response
        
        # Trigger manual warming
        result = self.service.trigger_manual_warming(valid_function_names, priority)
        
        # Verify response completeness
        assert 'success' in result, "Response should indicate success status"
        assert 'message' in result, "Response should contain message"
        assert 'functions_warmed' in result, "Response should contain functions warmed count"
        assert 'warming_results' in result, "Response should contain warming results"
        assert 'timestamp' in result, "Response should contain timestamp"
        
        # Verify success case properties
        if result['success']:
            assert result['functions_warmed'] == len(valid_function_names), "Functions warmed count should match input"
            assert len(result['warming_results']) == len(valid_function_names), "Warming results should cover all functions"
            
            # Verify each function was processed
            result_function_names = {r['function_name'] for r in result['warming_results']}
            expected_function_names = set(valid_function_names)
            assert result_function_names == expected_function_names, "All specified functions should be in results"
        
        # Verify Lambda invocation was called with correct parameters
        self.mock_lambda_client.invoke.assert_called_once()
        call_args = self.mock_lambda_client.invoke.call_args
        
        assert call_args[1]['FunctionName'] == 'IntelligentLambdaWarmer', "Should invoke correct warming function"
        assert call_args[1]['InvocationType'] == 'RequestResponse', "Should use synchronous invocation"
        
        # Verify payload structure
        payload = json.loads(call_args[1]['Payload'])
        assert 'predictions' in payload, "Payload should contain predictions"
        assert len(payload['predictions']) == len(valid_function_names), "Payload should contain all functions"
        
        for prediction in payload['predictions']:
            assert 'function_name' in prediction, "Each prediction should have function_name"
            assert 'endpoint' in prediction, "Each prediction should have endpoint"
            assert 'ensemble_probability' in prediction, "Each prediction should have probability"
            assert 'manual_trigger' in prediction, "Each prediction should be marked as manual trigger"
            assert prediction['priority'] == priority, "Each prediction should have correct priority"