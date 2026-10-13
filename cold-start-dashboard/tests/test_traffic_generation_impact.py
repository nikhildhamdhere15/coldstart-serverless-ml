"""
Property-based tests for traffic generation impact tracking
**Feature: cold-start-dashboard, Property 13: Traffic Generation Impact**
**Validates: Requirements 4.3**
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume
from services.traffic_generation import TrafficGenerationController, TrafficImpactMetrics


class TestTrafficGenerationImpact:
    """Property-based tests for traffic generation impact tracking"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_lambda_client = Mock()
        self.mock_dynamodb_table = Mock()
        self.controller = TrafficGenerationController(
            self.mock_lambda_client, 
            self.mock_dynamodb_table
        )
    
    @given(
        baseline_count=st.integers(min_value=0, max_value=1000),
        generated_requests=st.integers(min_value=1, max_value=500),
        window_minutes=st.integers(min_value=5, max_value=60)
    )
    def test_traffic_impact_calculation_accuracy(self, baseline_count, generated_requests, window_minutes):
        """
        Property 13: Traffic Generation Impact
        For any baseline request count and generated requests, the impact calculation should accurately reflect the increase
        **Validates: Requirements 4.3**
        """
        # Mock DynamoDB responses for baseline and post-generation counts
        post_generation_count = baseline_count + generated_requests
        
        # Set up mock responses for the two time windows
        self.mock_dynamodb_table.scan.side_effect = [
            {'Count': baseline_count},  # Baseline count
            {'Count': post_generation_count}  # Post-generation count
        ]
        
        # Capture baseline metrics
        baseline_metrics = self.controller.capture_baseline_metrics(window_minutes)
        
        # Measure traffic impact
        impact_metrics = self.controller.measure_traffic_impact(window_minutes)
        
        # Verify impact calculations are accurate
        assert impact_metrics.baseline_request_count == baseline_count
        assert impact_metrics.post_generation_request_count == post_generation_count
        assert impact_metrics.requests_added == generated_requests
        assert impact_metrics.measurement_window_minutes == window_minutes
        
        # Verify percentage increase calculation
        if baseline_count > 0:
            expected_percentage = (generated_requests / baseline_count) * 100
            assert abs(impact_metrics.percentage_increase - expected_percentage) < 0.01
        else:
            # When baseline is 0, any requests added should show 100% increase
            assert impact_metrics.percentage_increase == 100.0
    
    @given(
        baseline_count=st.integers(min_value=1, max_value=1000),
        multiplier=st.floats(min_value=0.1, max_value=5.0)
    )
    def test_percentage_increase_calculation(self, baseline_count, multiplier):
        """
        Property: Percentage increase should be calculated correctly for any baseline and multiplier
        **Validates: Requirements 4.3**
        """
        generated_requests = int(baseline_count * multiplier)
        post_generation_count = baseline_count + generated_requests
        
        # Mock DynamoDB responses
        self.mock_dynamodb_table.scan.side_effect = [
            {'Count': baseline_count},
            {'Count': post_generation_count}
        ]
        
        # Capture baseline and measure impact
        self.controller.capture_baseline_metrics(15)
        impact_metrics = self.controller.measure_traffic_impact(15)
        
        # Verify percentage calculation
        expected_percentage = (generated_requests / baseline_count) * 100
        assert abs(impact_metrics.percentage_increase - expected_percentage) < 0.01
        assert impact_metrics.requests_added == generated_requests
    
    @given(
        window_minutes=st.integers(min_value=5, max_value=120)
    )
    def test_baseline_capture_completeness(self, window_minutes):
        """
        Property: Baseline capture should include all required metrics for any time window
        **Validates: Requirements 4.3**
        """
        request_count = 42  # Fixed count for this test
        self.mock_dynamodb_table.scan.return_value = {'Count': request_count}
        
        baseline_metrics = self.controller.capture_baseline_metrics(window_minutes)
        
        # Verify all required fields are present
        assert 'request_count' in baseline_metrics
        assert 'timestamp' in baseline_metrics
        assert 'window_minutes' in baseline_metrics
        assert 'start_time' in baseline_metrics
        assert 'end_time' in baseline_metrics
        
        # Verify values are correct
        assert baseline_metrics['request_count'] == request_count
        assert baseline_metrics['window_minutes'] == window_minutes
        
        # Verify time window calculation
        time_diff = baseline_metrics['end_time'] - baseline_metrics['start_time']
        expected_diff = timedelta(minutes=window_minutes)
        assert abs(time_diff.total_seconds() - expected_diff.total_seconds()) < 60  # Allow 1 minute tolerance
    
    @given(
        hours=st.integers(min_value=1, max_value=48),
        hourly_counts=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=48)
    )
    def test_request_trend_calculation(self, hours, hourly_counts):
        """
        Property: Request trend calculation should accurately aggregate hourly data
        **Validates: Requirements 4.3**
        """
        # Limit hourly_counts to match the hours parameter
        hourly_counts = hourly_counts[:hours]
        
        # Mock DynamoDB to return the hourly counts in sequence
        self.mock_dynamodb_table.scan.side_effect = [{'Count': count} for count in hourly_counts]
        
        trend_data = self.controller.get_request_count_trend(hours)
        
        # Verify trend data structure
        assert 'hourly_counts' in trend_data
        assert 'total_requests' in trend_data
        assert 'average_per_hour' in trend_data
        assert 'time_period_hours' in trend_data
        
        # Verify calculations
        expected_total = sum(hourly_counts)
        expected_average = expected_total / len(hourly_counts)
        
        assert trend_data['total_requests'] == expected_total
        assert abs(trend_data['average_per_hour'] - expected_average) < 0.01
        assert trend_data['time_period_hours'] == hours
        assert len(trend_data['hourly_counts']) == len(hourly_counts)
    
    @given(
        baseline_count=st.integers(min_value=0, max_value=1000)
    )
    def test_impact_tracking_without_dynamodb(self, baseline_count):
        """
        Property: Impact tracking should handle missing DynamoDB gracefully
        **Validates: Requirements 4.3**
        """
        # Create controller without DynamoDB table
        controller_no_db = TrafficGenerationController(self.mock_lambda_client, None)
        
        # Capture baseline metrics
        baseline_metrics = controller_no_db.capture_baseline_metrics(15)
        
        # Measure impact
        impact_metrics = controller_no_db.measure_traffic_impact(15)
        
        # Verify graceful handling
        assert baseline_metrics['request_count'] == 0
        assert impact_metrics.baseline_request_count == 0
        assert impact_metrics.post_generation_request_count == 0
        assert impact_metrics.requests_added == 0
        assert impact_metrics.percentage_increase == 0.0
    
    def test_impact_metrics_reset(self):
        """
        Property: Resetting impact tracking should clear baseline metrics
        **Validates: Requirements 4.3**
        """
        # Set up initial baseline
        self.mock_dynamodb_table.scan.return_value = {'Count': 100}
        self.controller.capture_baseline_metrics(15)
        
        # Verify baseline is set
        assert self.controller._baseline_metrics is not None
        
        # Reset impact tracking
        self.controller.reset_impact_tracking()
        
        # Verify baseline is cleared
        assert self.controller._baseline_metrics is None
    
    @given(
        duration_minutes=st.integers(min_value=1, max_value=60),
        requests_per_minute=st.integers(min_value=1, max_value=100)
    )
    def test_impact_estimation_accuracy(self, duration_minutes, requests_per_minute):
        """
        Property: Impact estimation should calculate expected values correctly
        **Validates: Requirements 4.3**
        """
        impact_estimate = self.controller.estimate_impact(duration_minutes, requests_per_minute)
        
        expected_total = duration_minutes * requests_per_minute
        expected_cold_starts = int(expected_total * 0.15)  # 15% cold start rate
        expected_warm_starts = expected_total - expected_cold_starts
        
        # Verify all calculations
        assert impact_estimate['total_requests_estimated'] == expected_total
        assert impact_estimate['estimated_cold_starts'] == expected_cold_starts
        assert impact_estimate['estimated_warm_starts'] == expected_warm_starts
        assert impact_estimate['duration_minutes'] == duration_minutes
        assert impact_estimate['requests_per_minute'] == requests_per_minute
        assert impact_estimate['estimated_data_points'] == expected_total