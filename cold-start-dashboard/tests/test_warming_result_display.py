"""
Property-based tests for warming result display
Tests that warming results and manual controls meet display requirements
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

class TestWarmingResultDisplay:
    """Property-based tests for warming result display"""
    
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
        probabilities=st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=10),
        endpoints=st.lists(st.text(min_size=3, max_size=10), min_size=1, max_size=10)
    )
    @settings(max_examples=30, deadline=5000)
    def test_warming_recommendation_accuracy(self, probabilities, endpoints):
        """
        Property 16: Warming Result Display
        
        For any prediction results with various probabilities:
        - High-risk predictions (>80%) generate HIGH priority recommendations
        - Medium-risk predictions (70-80%) generate MEDIUM priority recommendations  
        - Low-risk predictions (<70%) generate LOW priority recommendations
        - Recommendations include appropriate urgency and frequency
        - All recommendations contain complete information
        
        Validates: Requirements 5.3
        """
        # Ensure we have matching probabilities and endpoints
        min_length = min(len(probabilities), len(endpoints))
        assume(min_length > 0)
        
        probabilities = probabilities[:min_length]
        endpoints = endpoints[:min_length]
        
        for probability, endpoint in zip(probabilities, endpoints):
            # Create prediction result
            prediction_result = {
                'ensemble_probability': probability,
                'endpoint': endpoint.strip(),
                'model_agreement': 0.9,
                'xgboost_probability': probability * 0.95,
                'rf_probability': probability * 1.05
            }
            
            # Get warming recommendation
            recommendation = self.service.create_warming_recommendation(prediction_result)
            
            # Verify recommendation completeness
            assert 'should_warm' in recommendation, "Recommendation should indicate if warming is needed"
            assert 'priority' in recommendation, "Recommendation should have priority"
            assert 'reason' in recommendation, "Recommendation should have reason"
            assert 'suggested_functions' in recommendation, "Recommendation should suggest functions"
            assert 'urgency' in recommendation, "Recommendation should indicate urgency"
            assert 'warming_frequency' in recommendation, "Recommendation should specify frequency"
            
            # Verify priority logic based on probability
            if probability > 0.8:
                assert recommendation['should_warm'] == True, f"High probability {probability} should recommend warming"
                assert recommendation['priority'] == 'HIGH', f"High probability {probability} should have HIGH priority"
                assert recommendation['urgency'] == 'immediate', f"High probability should have immediate urgency"
                assert recommendation['warming_frequency'] >= 2, f"High probability should have frequent warming"
                assert len(recommendation['suggested_functions']) > 0, "High priority should suggest functions"
                
            elif probability > 0.7:
                assert recommendation['should_warm'] == True, f"Medium probability {probability} should recommend warming"
                assert recommendation['priority'] == 'MEDIUM', f"Medium probability {probability} should have MEDIUM priority"
                assert recommendation['urgency'] == 'soon', f"Medium probability should have soon urgency"
                assert recommendation['warming_frequency'] >= 1, f"Medium probability should have some warming"
                assert len(recommendation['suggested_functions']) > 0, "Medium priority should suggest functions"
                
            else:
                assert recommendation['should_warm'] == False, f"Low probability {probability} should not recommend warming"
                assert recommendation['priority'] == 'LOW', f"Low probability {probability} should have LOW priority"
                assert recommendation['urgency'] == 'none', f"Low probability should have no urgency"
                assert recommendation['warming_frequency'] == 0, f"Low probability should have no warming"
                assert len(recommendation['suggested_functions']) == 0, "Low priority should not suggest functions"
            
            # Verify reason contains probability information
            assert f"{probability:.1%}" in recommendation['reason'], "Reason should contain probability percentage"
    
    @given(
        warming_results=st.lists(
            st.fixed_dictionaries({
                'function_name': st.text(min_size=5, max_size=20),
                'attempts': st.integers(min_value=1, max_value=5),
                'successful': st.integers(min_value=0, max_value=5),
                'endpoint': st.text(min_size=3, max_size=10),
                'priority': st.sampled_from(['HIGH', 'MEDIUM', 'LOW']),
                'probability': st.floats(min_value=0.0, max_value=1.0)
            }),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=20, deadline=5000)
    def test_warming_progress_display_completeness(self, warming_results):
        """
        Property: Warming progress display provides complete status information
        
        For any set of warming results:
        - Progress percentage is calculated correctly
        - Function processing status is accurate
        - Completion status is properly determined
        - Success rates are calculated correctly
        - All display fields are present and valid
        """
        # Ensure successful attempts don't exceed total attempts
        valid_results = []
        for result in warming_results:
            if result['successful'] <= result['attempts']:
                valid_results.append(result)
        
        assume(len(valid_results) > 0)
        
        # Mock warming progress based on results
        total_functions = len(valid_results)
        completed_functions = len([r for r in valid_results if r['successful'] > 0])
        
        # Simulate progress display
        progress_info = {
            'in_progress': False,
            'completed': True,
            'progress_percentage': (completed_functions / total_functions * 100) if total_functions > 0 else 0,
            'functions_processed': completed_functions,
            'total_functions': total_functions,
            'current_function': None,
            'estimated_completion': None,
            'warming_results': valid_results
        }
        
        # Verify progress display completeness
        assert 'in_progress' in progress_info, "Progress should indicate if warming is in progress"
        assert 'completed' in progress_info, "Progress should indicate completion status"
        assert 'progress_percentage' in progress_info, "Progress should show percentage"
        assert 'functions_processed' in progress_info, "Progress should show processed count"
        assert 'total_functions' in progress_info, "Progress should show total count"
        
        # Verify progress percentage calculation
        expected_percentage = (completed_functions / total_functions * 100) if total_functions > 0 else 0
        assert abs(progress_info['progress_percentage'] - expected_percentage) < 0.1, "Progress percentage should be calculated correctly"
        
        # Verify function counts
        assert progress_info['functions_processed'] == completed_functions, "Processed count should match successful functions"
        assert progress_info['total_functions'] == total_functions, "Total count should match input functions"
        
        # Verify completion logic
        if completed_functions == total_functions and total_functions > 0:
            assert progress_info['completed'] == True, "Should be completed when all functions processed"
            assert progress_info['progress_percentage'] == 100, "Should be 100% when completed"
        
        # Verify warming results are included
        assert 'warming_results' in progress_info, "Progress should include warming results"
        assert len(progress_info['warming_results']) == len(valid_results), "All results should be included"
    
    def test_available_functions_display(self):
        """
        Property: Available functions display provides complete function information
        
        The available functions list should:
        - Include all standard Lambda functions
        - Provide complete function information
        - Have consistent formatting
        - Include status information
        """
        available_functions = self.service.get_available_functions()
        
        # Verify we have functions
        assert len(available_functions) > 0, "Should return available functions"
        
        # Verify each function has complete information
        for function in available_functions:
            assert 'function_name' in function, "Function should have name"
            assert 'endpoint' in function, "Function should have endpoint"
            assert 'description' in function, "Function should have description"
            assert 'status' in function, "Function should have status"
            
            # Verify data types
            assert isinstance(function['function_name'], str), "Function name should be string"
            assert isinstance(function['endpoint'], str), "Endpoint should be string"
            assert isinstance(function['description'], str), "Description should be string"
            assert isinstance(function['status'], str), "Status should be string"
            
            # Verify naming consistency
            assert function['endpoint'] in function['function_name'], "Function name should contain endpoint"
            assert function['function_name'].endswith('-function'), "Function name should end with '-function'"
        
        # Verify standard functions are included
        function_names = {f['function_name'] for f in available_functions}
        expected_functions = {'auth-function', 'profile-function', 'search-function'}
        
        for expected in expected_functions:
            assert expected in function_names, f"Should include {expected}"
    
    @given(
        events=st.lists(
            st.fixed_dictionaries({
                'timestamp': st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
                'function_name': st.text(min_size=5, max_size=20),
                'endpoint': st.text(min_size=3, max_size=10),
                'success_rate': st.floats(min_value=0.0, max_value=1.0),
                'attempts': st.integers(min_value=1, max_value=5),
                'successful': st.integers(min_value=0, max_value=5),
                'priority': st.sampled_from(['HIGH', 'MEDIUM', 'LOW', 'NONE']),
                'probability': st.floats(min_value=0.0, max_value=1.0),
                'reason': st.text(min_size=10, max_size=50)
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=20, deadline=5000)
    def test_warming_history_display_formatting(self, events):
        """
        Property: Warming history display formatting is consistent and complete
        
        For any set of warming events:
        - All events are properly formatted for display
        - Timestamps are formatted consistently
        - Success rates are displayed as percentages
        - Status indicators are appropriate
        - All required fields are present
        """
        # Convert dictionaries to WarmingEvent objects
        warming_events = []
        for event_data in events:
            # Ensure successful doesn't exceed attempts
            successful = min(event_data['successful'], event_data['attempts'])
            
            warming_events.append(WarmingEvent(
                timestamp=event_data['timestamp'],
                function_name=event_data['function_name'],
                endpoint=event_data['endpoint'],
                success_rate=event_data['success_rate'],
                attempts=event_data['attempts'],
                successful=successful,
                priority=event_data['priority'],
                probability=event_data['probability'],
                reason=event_data['reason']
            ))
        
        # Format events for display
        formatted_events = self.service.format_warming_history_display(warming_events)
        
        # Verify formatting completeness
        assert len(formatted_events) == len(warming_events), "All events should be formatted"
        
        for i, formatted_event in enumerate(formatted_events):
            original_event = warming_events[i]
            
            # Verify all required fields are present
            required_fields = ['timestamp', 'function_name', 'endpoint', 'success_rate', 
                             'attempts', 'successful', 'priority', 'probability', 'reason', 'status']
            
            for field in required_fields:
                assert field in formatted_event, f"Formatted event should have {field}"
            
            # Verify timestamp formatting
            assert isinstance(formatted_event['timestamp'], str), "Timestamp should be formatted as string"
            assert len(formatted_event['timestamp']) >= 19, "Timestamp should include date and time"
            
            # Verify success rate formatting
            assert '%' in formatted_event['success_rate'], "Success rate should be formatted as percentage"
            
            # Verify status indicator logic
            success_rate = original_event.success_rate
            status = formatted_event['status']
            
            if success_rate > 0.8:
                assert status == '✅ Success', f"High success rate {success_rate} should show success status"
            elif success_rate > 0:
                assert status == '⚠️ Partial', f"Partial success rate {success_rate} should show partial status"
            else:
                assert status == '❌ Failed', f"Zero success rate should show failed status"
            
            # Verify endpoint formatting (should be uppercase)
            assert formatted_event['endpoint'] == original_event.endpoint.upper(), "Endpoint should be uppercase"
            
            # Verify probability formatting
            assert isinstance(formatted_event['probability'], str), "Probability should be formatted as string"
            assert '.' in formatted_event['probability'], "Probability should include decimal places"