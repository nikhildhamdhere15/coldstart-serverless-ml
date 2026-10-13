"""
Property-based tests for Cost Analytics Service
**Feature: cold-start-dashboard, Property 19: Cost Calculation Accuracy**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from services.cost_analytics import CostAnalyticsService, CostMetrics, PerformanceMetrics, EfficiencyMetrics


@given(
    sagemaker_invocations=st.integers(min_value=0, max_value=100000),
    lambda_invocations=st.integers(min_value=0, max_value=100000),
    dynamodb_reads=st.integers(min_value=0, max_value=1000000),
    dynamodb_writes=st.integers(min_value=0, max_value=100000),
    cloudwatch_metrics=st.integers(min_value=0, max_value=1000)
)
@settings(max_examples=100)
def test_property_cost_calculation_accuracy(sagemaker_invocations, lambda_invocations, 
                                          dynamodb_reads, dynamodb_writes, cloudwatch_metrics):
    """
    **Property 19: Cost Calculation Accuracy**
    For any usage data, cost calculations should be mathematically correct 
    using standard AWS pricing formulas.
    **Validates: Requirements 6.1, 6.4**
    """
    # Create mock CloudWatch client
    mock_cloudwatch = Mock()
    
    # Create service
    service = CostAnalyticsService(cloudwatch_client=mock_cloudwatch)
    
    # Mock the usage metrics method to return our test data
    usage_metrics = {
        'sagemaker_invocations': sagemaker_invocations,
        'lambda_invocations': lambda_invocations,
        'dynamodb_reads': dynamodb_reads,
        'dynamodb_writes': dynamodb_writes,
        'cloudwatch_metrics': cloudwatch_metrics
    }
    
    with patch.object(service, '_get_monthly_usage_metrics', return_value=usage_metrics):
        # Calculate costs
        cost_metrics = service.calculate_monthly_costs()
        
        # Verify cost metrics structure
        assert isinstance(cost_metrics, CostMetrics), "Should return CostMetrics object"
        
        # Verify all costs are non-negative
        assert cost_metrics.monthly_sagemaker_cost >= 0, "SageMaker cost should be non-negative"
        assert cost_metrics.monthly_lambda_cost >= 0, "Lambda cost should be non-negative"
        assert cost_metrics.monthly_dynamodb_cost >= 0, "DynamoDB cost should be non-negative"
        assert cost_metrics.monthly_cloudwatch_cost >= 0, "CloudWatch cost should be non-negative"
        assert cost_metrics.total_monthly_cost >= 0, "Total cost should be non-negative"
        
        # Verify total cost is sum of individual costs
        expected_total = (cost_metrics.monthly_sagemaker_cost + 
                         cost_metrics.monthly_lambda_cost + 
                         cost_metrics.monthly_dynamodb_cost + 
                         cost_metrics.monthly_cloudwatch_cost)
        
        assert abs(cost_metrics.total_monthly_cost - expected_total) < 0.01, \
            f"Total cost should equal sum of individual costs: {cost_metrics.total_monthly_cost} vs {expected_total}"
        
        # Verify cost without optimization is higher than optimized cost
        assert cost_metrics.cost_without_optimization >= cost_metrics.total_monthly_cost, \
            "Cost without optimization should be >= optimized cost"
        
        # Verify savings calculation
        expected_savings = cost_metrics.cost_without_optimization - cost_metrics.total_monthly_cost
        assert abs(cost_metrics.monthly_savings - expected_savings) < 0.01, \
            "Monthly savings should equal difference between unoptimized and optimized costs"
        
        # Verify ROI calculation
        if cost_metrics.total_monthly_cost > 0:
            expected_roi = (cost_metrics.monthly_savings / cost_metrics.total_monthly_cost) * 100
            assert abs(cost_metrics.roi_percentage - expected_roi) < 0.01, \
                "ROI percentage should be correctly calculated"
        else:
            assert cost_metrics.roi_percentage == 0, "ROI should be 0 when total cost is 0"
        
        # Verify mathematical relationships for SageMaker costs
        if sagemaker_invocations > 0:
            assert cost_metrics.monthly_sagemaker_cost > 0, \
                "SageMaker cost should be positive when there are invocations"
            
            # Verify cost scales with usage
            double_usage = usage_metrics.copy()
            double_usage['sagemaker_invocations'] = sagemaker_invocations * 2
            
            with patch.object(service, '_get_monthly_usage_metrics', return_value=double_usage):
                double_cost_metrics = service.calculate_monthly_costs()
                
                # SageMaker cost should approximately double (within 10% tolerance for rounding)
                cost_ratio = double_cost_metrics.monthly_sagemaker_cost / cost_metrics.monthly_sagemaker_cost
                assert 1.8 <= cost_ratio <= 2.2, \
                    f"SageMaker cost should approximately double with double usage: {cost_ratio}"
        
        # Verify Lambda cost scaling
        if lambda_invocations > 0:
            assert cost_metrics.monthly_lambda_cost > 0, \
                "Lambda cost should be positive when there are invocations"
        
        # Verify DynamoDB cost components
        if dynamodb_reads > 0 or dynamodb_writes > 0:
            assert cost_metrics.monthly_dynamodb_cost > 0, \
                "DynamoDB cost should be positive when there are operations"
        
        # Verify CloudWatch cost scaling
        if cloudwatch_metrics > 0:
            assert cost_metrics.monthly_cloudwatch_cost >= 0, \
                "CloudWatch cost should be non-negative when there are metrics"


@given(
    cold_start_before=st.floats(min_value=0.1, max_value=50.0),
    cold_start_after=st.floats(min_value=0.0, max_value=10.0),
    response_time_before=st.floats(min_value=100.0, max_value=5000.0),
    response_time_after=st.floats(min_value=50.0, max_value=500.0),
    uptime_before=st.floats(min_value=80.0, max_value=99.0),
    uptime_after=st.floats(min_value=95.0, max_value=100.0)
)
@settings(max_examples=100)
def test_property_performance_calculation_accuracy(cold_start_before, cold_start_after,
                                                 response_time_before, response_time_after,
                                                 uptime_before, uptime_after):
    """
    **Property 20: Performance Comparison Accuracy**
    For any historical performance data, before/after comparisons should 
    accurately reflect actual system improvements.
    **Validates: Requirements 6.2**
    """
    # Ensure logical constraints
    assume(cold_start_before >= cold_start_after)  # Performance should improve
    assume(response_time_before >= response_time_after)  # Response time should improve
    assume(uptime_after >= uptime_before)  # Uptime should improve
    
    # Create service
    service = CostAnalyticsService()
    
    # Mock performance metrics
    current_metrics = {
        'cold_start_frequency': cold_start_after,
        'response_time': response_time_after,
        'uptime': uptime_after
    }
    
    baseline_metrics = {
        'cold_start_frequency': cold_start_before,
        'response_time': response_time_before,
        'uptime': uptime_before
    }
    
    with patch.object(service, '_get_current_performance_metrics', return_value=current_metrics), \
         patch.object(service, '_get_baseline_performance_metrics', return_value=baseline_metrics):
        
        performance_metrics = service.calculate_performance_comparison()
        
        # Verify performance metrics structure
        assert isinstance(performance_metrics, PerformanceMetrics), "Should return PerformanceMetrics object"
        
        # Verify before/after values are preserved
        assert abs(performance_metrics.cold_start_frequency_before - cold_start_before) < 0.01, \
            "Before cold start frequency should be preserved"
        assert abs(performance_metrics.cold_start_frequency_after - cold_start_after) < 0.01, \
            "After cold start frequency should be preserved"
        assert abs(performance_metrics.average_response_time_before - response_time_before) < 0.01, \
            "Before response time should be preserved"
        assert abs(performance_metrics.average_response_time_after - response_time_after) < 0.01, \
            "After response time should be preserved"
        assert abs(performance_metrics.uptime_before - uptime_before) < 0.01, \
            "Before uptime should be preserved"
        assert abs(performance_metrics.uptime_after - uptime_after) < 0.01, \
            "After uptime should be preserved"
        
        # Verify improvement calculation accuracy
        expected_improvement = ((cold_start_before - cold_start_after) / cold_start_before) * 100
        assert abs(performance_metrics.improvement_percentage - expected_improvement) < 0.01, \
            f"Improvement percentage should be correctly calculated: {performance_metrics.improvement_percentage} vs {expected_improvement}"
        
        # Verify improvement is positive when performance improves
        if cold_start_before > cold_start_after:
            assert performance_metrics.improvement_percentage > 0, \
                "Improvement percentage should be positive when cold starts decrease"
        
        # Verify improvement bounds
        assert 0 <= performance_metrics.improvement_percentage <= 100, \
            "Improvement percentage should be between 0 and 100"


@given(
    calls_before=st.integers(min_value=100, max_value=10000),
    calls_after=st.integers(min_value=1, max_value=100),
    daily_requests=st.integers(min_value=100, max_value=10000)
)
@settings(max_examples=100)
def test_property_efficiency_calculation_accuracy(calls_before, calls_after, daily_requests):
    """
    **Property 21: Efficiency Calculation Correctness**
    For any SageMaker call statistics, efficiency calculations should accurately 
    reflect the reduction in API calls through batch processing.
    **Validates: Requirements 6.3**
    """
    # Ensure logical constraints
    assume(calls_before >= calls_after)  # Optimization should reduce calls
    
    # Create service
    service = CostAnalyticsService()
    
    # Mock SageMaker usage statistics
    usage_stats = {
        'daily_requests': daily_requests,
        'daily_sagemaker_calls': calls_after
    }
    
    with patch.object(service, '_get_sagemaker_usage_statistics', return_value=usage_stats):
        efficiency_metrics = service.calculate_efficiency_metrics()
        
        # Verify efficiency metrics structure
        assert isinstance(efficiency_metrics, EfficiencyMetrics), "Should return EfficiencyMetrics object"
        
        # Verify call counts
        assert efficiency_metrics.sagemaker_calls_before == daily_requests, \
            "Calls before should equal daily requests (1:1 ratio without batching)"
        assert efficiency_metrics.sagemaker_calls_after == calls_after, \
            "Calls after should match usage statistics"
        
        # Verify call reduction calculation
        expected_reduction = ((daily_requests - calls_after) / daily_requests) * 100
        assert abs(efficiency_metrics.call_reduction_percentage - expected_reduction) < 0.01, \
            f"Call reduction should be correctly calculated: {efficiency_metrics.call_reduction_percentage} vs {expected_reduction}"
        
        # Verify reduction is positive
        assert efficiency_metrics.call_reduction_percentage >= 0, \
            "Call reduction should be non-negative"
        
        # Verify reduction bounds
        assert efficiency_metrics.call_reduction_percentage <= 100, \
            "Call reduction should not exceed 100%"
        
        # Verify batch processing efficiency is as specified in requirements (98%)
        assert efficiency_metrics.batch_processing_efficiency == 98.0, \
            "Batch processing efficiency should be 98% as specified in requirements"
        
        # Verify cost per prediction calculations
        assert efficiency_metrics.cost_per_prediction_before >= efficiency_metrics.cost_per_prediction_after, \
            "Cost per prediction should decrease with optimization"
        
        if efficiency_metrics.cost_per_prediction_before > 0:
            expected_efficiency_gain = (
                (efficiency_metrics.cost_per_prediction_before - efficiency_metrics.cost_per_prediction_after) /
                efficiency_metrics.cost_per_prediction_before * 100
            )
            assert abs(efficiency_metrics.efficiency_gain_percentage - expected_efficiency_gain) < 0.01, \
                "Efficiency gain should be correctly calculated"
        
        # Verify efficiency gain bounds
        assert 0 <= efficiency_metrics.efficiency_gain_percentage <= 100, \
            "Efficiency gain should be between 0 and 100%"


@given(
    usage_multiplier=st.floats(min_value=0.1, max_value=10.0)
)
@settings(max_examples=50)
def test_cost_scaling_linearity(usage_multiplier):
    """
    Test that costs scale linearly with usage (mathematical property)
    """
    # Create service
    service = CostAnalyticsService()
    
    # Base usage metrics
    base_usage = {
        'sagemaker_invocations': 1000,
        'lambda_invocations': 2000,
        'dynamodb_reads': 3000,
        'dynamodb_writes': 1000,
        'cloudwatch_metrics': 50
    }
    
    # Scaled usage metrics
    scaled_usage = {k: int(v * usage_multiplier) for k, v in base_usage.items()}
    
    with patch.object(service, '_get_monthly_usage_metrics', return_value=base_usage):
        base_costs = service.calculate_monthly_costs()
    
    with patch.object(service, '_get_monthly_usage_metrics', return_value=scaled_usage):
        scaled_costs = service.calculate_monthly_costs()
    
    # Verify linear scaling (within 5% tolerance for rounding and fixed costs)
    if base_costs.monthly_sagemaker_cost > 0:
        sagemaker_ratio = scaled_costs.monthly_sagemaker_cost / base_costs.monthly_sagemaker_cost
        assert abs(sagemaker_ratio - usage_multiplier) / usage_multiplier < 0.05, \
            f"SageMaker costs should scale linearly: {sagemaker_ratio} vs {usage_multiplier}"
    
    if base_costs.monthly_lambda_cost > 0:
        lambda_ratio = scaled_costs.monthly_lambda_cost / base_costs.monthly_lambda_cost
        assert abs(lambda_ratio - usage_multiplier) / usage_multiplier < 0.05, \
            f"Lambda costs should scale linearly: {lambda_ratio} vs {usage_multiplier}"


def test_zero_usage_costs():
    """
    Test that zero usage results in minimal or zero costs
    """
    service = CostAnalyticsService()
    
    zero_usage = {
        'sagemaker_invocations': 0,
        'lambda_invocations': 0,
        'dynamodb_reads': 0,
        'dynamodb_writes': 0,
        'cloudwatch_metrics': 0
    }
    
    with patch.object(service, '_get_monthly_usage_metrics', return_value=zero_usage):
        cost_metrics = service.calculate_monthly_costs()
        
        # SageMaker and Lambda costs should be zero with no usage
        assert cost_metrics.monthly_sagemaker_cost == 0, "SageMaker cost should be 0 with no invocations"
        assert cost_metrics.monthly_lambda_cost == 0, "Lambda cost should be 0 with no invocations"
        
        # DynamoDB and CloudWatch may have minimal fixed costs
        assert cost_metrics.monthly_dynamodb_cost >= 0, "DynamoDB cost should be non-negative"
        assert cost_metrics.monthly_cloudwatch_cost >= 0, "CloudWatch cost should be non-negative"


def test_cost_breakdown_summary_completeness():
    """
    Test that cost breakdown summary contains all required fields
    """
    service = CostAnalyticsService()
    
    # Create mock return values with proper structure
    mock_cost_metrics = CostMetrics(
        monthly_sagemaker_cost=10.0,
        monthly_lambda_cost=5.0,
        monthly_dynamodb_cost=3.0,
        monthly_cloudwatch_cost=2.0,
        total_monthly_cost=20.0,
        cost_without_optimization=100.0,
        monthly_savings=80.0,
        roi_percentage=400.0
    )
    
    mock_performance_metrics = PerformanceMetrics(
        cold_start_frequency_before=25.0,
        cold_start_frequency_after=5.0,
        average_response_time_before=2500.0,
        average_response_time_after=150.0,
        uptime_before=92.0,
        uptime_after=99.2,
        improvement_percentage=80.0
    )
    
    mock_efficiency_metrics = EfficiencyMetrics(
        sagemaker_calls_before=1000,
        sagemaker_calls_after=20,
        call_reduction_percentage=98.0,
        batch_processing_efficiency=98.0,
        cost_per_prediction_before=0.002,
        cost_per_prediction_after=0.00004,
        efficiency_gain_percentage=98.0
    )
    
    with patch.object(service, 'calculate_monthly_costs', return_value=mock_cost_metrics), \
         patch.object(service, 'calculate_performance_comparison', return_value=mock_performance_metrics), \
         patch.object(service, 'calculate_efficiency_metrics', return_value=mock_efficiency_metrics):
        
        summary = service.get_cost_breakdown_summary()
        
        # Verify summary structure
        assert isinstance(summary, dict), "Summary should be a dictionary"
        
        # Check for required top-level keys
        required_keys = ['monthly_costs', 'savings', 'performance', 'efficiency']
        for key in required_keys:
            assert key in summary, f"Summary should contain '{key}' section"
        
        # Verify monthly_costs section
        monthly_costs = summary.get('monthly_costs', {})
        cost_keys = ['sagemaker', 'lambda', 'dynamodb', 'cloudwatch', 'total']
        for key in cost_keys:
            assert key in monthly_costs, f"Monthly costs should contain '{key}'"
        
        # Verify savings section
        savings = summary.get('savings', {})
        savings_keys = ['monthly_savings', 'roi_percentage', 'cost_without_optimization']
        for key in savings_keys:
            assert key in savings, f"Savings should contain '{key}'"
        
        # Verify performance section
        performance = summary.get('performance', {})
        performance_keys = ['cold_start_improvement', 'uptime_improvement', 'response_time_improvement']
        for key in performance_keys:
            assert key in performance, f"Performance should contain '{key}'"
        
        # Verify efficiency section
        efficiency = summary.get('efficiency', {})
        efficiency_keys = ['sagemaker_call_reduction', 'batch_processing_efficiency', 'cost_per_prediction_savings']
        for key in efficiency_keys:
            assert key in efficiency, f"Efficiency should contain '{key}'"