"""
Property-based tests for Performance Display Service
**Feature: cold-start-dashboard, Property 20: Performance Comparison Accuracy**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from services.performance_display import (
    PerformanceDisplayService, PerformanceDisplayData, UptimeStatistics, 
    EfficiencyVisualization
)
from services.cost_analytics import PerformanceMetrics, EfficiencyMetrics


@given(
    cold_start_before=st.floats(min_value=1.0, max_value=50.0),
    cold_start_after=st.floats(min_value=0.0, max_value=10.0),
    response_time_before=st.floats(min_value=500.0, max_value=5000.0),
    response_time_after=st.floats(min_value=50.0, max_value=500.0),
    uptime_before=st.floats(min_value=80.0, max_value=99.0),
    uptime_after=st.floats(min_value=95.0, max_value=100.0)
)
@settings(max_examples=100)
def test_property_performance_comparison_accuracy(cold_start_before, cold_start_after,
                                                response_time_before, response_time_after,
                                                uptime_before, uptime_after):
    """
    **Property 20: Performance Comparison Accuracy**
    For any historical performance data, before/after comparisons should 
    accurately reflect actual system improvements.
    **Validates: Requirements 6.2**
    """
    # Ensure logical constraints (performance should improve or stay same)
    assume(cold_start_before >= cold_start_after)
    assume(response_time_before >= response_time_after)
    assume(uptime_after >= uptime_before)
    
    # Create mock cost analytics service
    mock_cost_analytics = Mock()
    
    # Create performance metrics
    performance_metrics = PerformanceMetrics(
        cold_start_frequency_before=cold_start_before,
        cold_start_frequency_after=cold_start_after,
        average_response_time_before=response_time_before,
        average_response_time_after=response_time_after,
        uptime_before=uptime_before,
        uptime_after=uptime_after,
        improvement_percentage=((cold_start_before - cold_start_after) / cold_start_before * 100) if cold_start_before > 0 else 0
    )
    
    mock_cost_analytics.calculate_performance_comparison.return_value = performance_metrics
    
    # Create service
    service = PerformanceDisplayService(cost_analytics_service=mock_cost_analytics)
    
    # Get performance comparison display
    display_data = service.get_performance_comparison_display()
    
    # Verify display data structure
    assert isinstance(display_data, list), "Should return list of PerformanceDisplayData"
    assert len(display_data) >= 3, "Should have at least 3 performance metrics"
    
    # Find specific metrics
    cold_start_metric = None
    response_time_metric = None
    uptime_metric = None
    
    for metric in display_data:
        assert isinstance(metric, PerformanceDisplayData), "Each item should be PerformanceDisplayData"
        
        if "Cold Start" in metric.metric_name:
            cold_start_metric = metric
        elif "Response Time" in metric.metric_name:
            response_time_metric = metric
        elif "Uptime" in metric.metric_name:
            uptime_metric = metric
    
    # Verify cold start metric accuracy
    if cold_start_metric:
        assert abs(cold_start_metric.before_value - cold_start_before) < 0.01, \
            f"Cold start before value should match input: {cold_start_metric.before_value} vs {cold_start_before}"
        assert abs(cold_start_metric.after_value - cold_start_after) < 0.01, \
            f"Cold start after value should match input: {cold_start_metric.after_value} vs {cold_start_after}"
        
        # Verify improvement calculation
        expected_improvement = ((cold_start_before - cold_start_after) / cold_start_before * 100) if cold_start_before > 0 else 0
        assert abs(cold_start_metric.improvement_percentage - expected_improvement) < 0.01, \
            f"Cold start improvement should be correctly calculated: {cold_start_metric.improvement_percentage} vs {expected_improvement}"
        
        # Verify improvement direction
        assert cold_start_metric.improvement_direction == "decrease", \
            "Cold start improvement direction should be 'decrease'"
        
        # Verify units and format
        assert cold_start_metric.unit == "%", "Cold start unit should be percentage"
        assert cold_start_metric.display_format == "percentage", "Cold start format should be percentage"
    
    # Verify response time metric accuracy
    if response_time_metric:
        assert abs(response_time_metric.before_value - response_time_before) < 0.01, \
            f"Response time before value should match input: {response_time_metric.before_value} vs {response_time_before}"
        assert abs(response_time_metric.after_value - response_time_after) < 0.01, \
            f"Response time after value should match input: {response_time_metric.after_value} vs {response_time_after}"
        
        # Verify improvement calculation
        expected_improvement = ((response_time_before - response_time_after) / response_time_before * 100) if response_time_before > 0 else 0
        assert abs(response_time_metric.improvement_percentage - expected_improvement) < 0.01, \
            f"Response time improvement should be correctly calculated: {response_time_metric.improvement_percentage} vs {expected_improvement}"
        
        # Verify improvement direction
        assert response_time_metric.improvement_direction == "decrease", \
            "Response time improvement direction should be 'decrease'"
        
        # Verify units and format
        assert response_time_metric.unit == "ms", "Response time unit should be milliseconds"
        assert response_time_metric.display_format == "milliseconds", "Response time format should be milliseconds"
    
    # Verify uptime metric accuracy
    if uptime_metric:
        assert abs(uptime_metric.before_value - uptime_before) < 0.01, \
            f"Uptime before value should match input: {uptime_metric.before_value} vs {uptime_before}"
        assert abs(uptime_metric.after_value - uptime_after) < 0.01, \
            f"Uptime after value should match input: {uptime_metric.after_value} vs {uptime_after}"
        
        # Verify improvement calculation (uptime improvement is absolute difference)
        expected_improvement = uptime_after - uptime_before
        assert abs(uptime_metric.improvement_percentage - expected_improvement) < 0.01, \
            f"Uptime improvement should be correctly calculated: {uptime_metric.improvement_percentage} vs {expected_improvement}"
        
        # Verify improvement direction
        assert uptime_metric.improvement_direction == "increase", \
            "Uptime improvement direction should be 'increase'"
        
        # Verify units and format
        assert uptime_metric.unit == "%", "Uptime unit should be percentage"
        assert uptime_metric.display_format == "percentage", "Uptime format should be percentage"
    
    # Verify all metrics have positive or zero improvement when performance improves
    for metric in display_data:
        if metric.improvement_direction == "decrease":
            # For metrics where decrease is better (cold starts, response time)
            if metric.before_value > metric.after_value:
                assert metric.improvement_percentage >= 0, \
                    f"Improvement percentage should be non-negative when {metric.metric_name} decreases"
        elif metric.improvement_direction == "increase":
            # For metrics where increase is better (uptime)
            if metric.after_value > metric.before_value:
                assert metric.improvement_percentage >= 0, \
                    f"Improvement percentage should be non-negative when {metric.metric_name} increases"


@given(
    current_uptime=st.floats(min_value=95.0, max_value=100.0),
    historical_uptime=st.floats(min_value=80.0, max_value=95.0),
    downtime_incidents=st.integers(min_value=0, max_value=20),
    mttr_minutes=st.floats(min_value=1.0, max_value=120.0),
    mtbf_hours=st.floats(min_value=24.0, max_value=2000.0)
)
@settings(max_examples=100)
def test_uptime_statistics_accuracy(current_uptime, historical_uptime, downtime_incidents, 
                                  mttr_minutes, mtbf_hours):
    """
    Test that uptime statistics are calculated and displayed accurately
    """
    # Ensure logical constraints
    assume(current_uptime >= historical_uptime)  # Uptime should improve
    
    # Create mock system monitoring service
    mock_system_monitoring = Mock()
    mock_system_health = Mock()
    mock_system_health.uptime_percentage = current_uptime
    mock_system_monitoring.get_system_health.return_value = mock_system_health
    
    # Create service
    service = PerformanceDisplayService(system_monitoring_service=mock_system_monitoring)
    
    # Set the baseline uptime for testing
    service.set_baseline_uptime(historical_uptime)
    
    # Mock the internal calculation methods
    with patch.object(service, '_calculate_downtime_incidents', return_value=downtime_incidents), \
         patch.object(service, '_calculate_mttr', return_value=mttr_minutes), \
         patch.object(service, '_calculate_mtbf', return_value=mtbf_hours):
        
        uptime_stats = service.get_uptime_statistics()
    
    # Verify uptime statistics structure
    assert isinstance(uptime_stats, UptimeStatistics), "Should return UptimeStatistics object"
    
    # Verify uptime values
    assert abs(uptime_stats.current_uptime - current_uptime) < 0.01, \
        f"Current uptime should match input: {uptime_stats.current_uptime} vs {current_uptime}"
    assert abs(uptime_stats.historical_uptime - historical_uptime) < 0.01, \
        f"Historical uptime should match expected: {uptime_stats.historical_uptime} vs {historical_uptime}"
    
    # Verify uptime improvement calculation
    expected_improvement = current_uptime - historical_uptime
    assert abs(uptime_stats.uptime_improvement - expected_improvement) < 0.01, \
        f"Uptime improvement should be correctly calculated: {uptime_stats.uptime_improvement} vs {expected_improvement}"
    
    # Verify SLA compliance logic
    assert uptime_stats.availability_sla == 99.0, "SLA should be 99%"
    expected_compliance = current_uptime >= 99.0
    assert uptime_stats.sla_compliance == expected_compliance, \
        f"SLA compliance should be correctly determined: {uptime_stats.sla_compliance} vs {expected_compliance}"
    
    # Verify reliability metrics
    assert uptime_stats.downtime_incidents == downtime_incidents, \
        f"Downtime incidents should match: {uptime_stats.downtime_incidents} vs {downtime_incidents}"
    assert abs(uptime_stats.mttr_minutes - mttr_minutes) < 0.01, \
        f"MTTR should match: {uptime_stats.mttr_minutes} vs {mttr_minutes}"
    assert abs(uptime_stats.mtbf_hours - mtbf_hours) < 0.01, \
        f"MTBF should match: {uptime_stats.mtbf_hours} vs {mtbf_hours}"
    
    # Verify logical relationships
    assert uptime_stats.current_uptime >= 0 and uptime_stats.current_uptime <= 100, \
        "Current uptime should be between 0 and 100"
    assert uptime_stats.historical_uptime >= 0 and uptime_stats.historical_uptime <= 100, \
        "Historical uptime should be between 0 and 100"
    assert uptime_stats.downtime_incidents >= 0, "Downtime incidents should be non-negative"
    assert uptime_stats.mttr_minutes > 0, "MTTR should be positive"
    assert uptime_stats.mtbf_hours > 0, "MTBF should be positive"


@given(
    call_reduction=st.floats(min_value=80.0, max_value=99.9),
    batch_efficiency=st.floats(min_value=90.0, max_value=99.9),
    cost_savings=st.floats(min_value=70.0, max_value=99.9),
    resource_utilization=st.floats(min_value=50.0, max_value=95.0)
)
@settings(max_examples=100)
def test_efficiency_visualization_accuracy(call_reduction, batch_efficiency, 
                                         cost_savings, resource_utilization):
    """
    Test that efficiency visualizations accurately represent system efficiency
    """
    # Create mock cost analytics service
    mock_cost_analytics = Mock()
    
    efficiency_metrics = EfficiencyMetrics(
        sagemaker_calls_before=1000,
        sagemaker_calls_after=int(1000 * (100 - call_reduction) / 100),
        call_reduction_percentage=call_reduction,
        batch_processing_efficiency=batch_efficiency,
        cost_per_prediction_before=0.002,
        cost_per_prediction_after=0.002 * (100 - cost_savings) / 100,
        efficiency_gain_percentage=cost_savings
    )
    
    mock_cost_analytics.calculate_efficiency_metrics.return_value = efficiency_metrics
    
    # Create service
    service = PerformanceDisplayService(cost_analytics_service=mock_cost_analytics)
    
    # Mock resource utilization calculation
    with patch.object(service, '_calculate_resource_utilization', return_value=resource_utilization):
        efficiency_viz = service.get_efficiency_visualizations()
    
    # Verify efficiency visualizations structure
    assert isinstance(efficiency_viz, list), "Should return list of EfficiencyVisualization"
    assert len(efficiency_viz) >= 3, "Should have at least 3 efficiency visualizations"
    
    # Find specific visualizations
    call_reduction_viz = None
    batch_efficiency_viz = None
    cost_savings_viz = None
    resource_viz = None
    
    for viz in efficiency_viz:
        assert isinstance(viz, EfficiencyVisualization), "Each item should be EfficiencyVisualization"
        
        if "Call Reduction" in viz.metric_name:
            call_reduction_viz = viz
        elif "Batch Processing" in viz.metric_name:
            batch_efficiency_viz = viz
        elif "Cost Per Prediction" in viz.metric_name:
            cost_savings_viz = viz
        elif "Resource Utilization" in viz.metric_name:
            resource_viz = viz
    
    # Verify call reduction visualization
    if call_reduction_viz:
        assert abs(call_reduction_viz.current_value - call_reduction) < 0.01, \
            f"Call reduction current value should match: {call_reduction_viz.current_value} vs {call_reduction}"
        assert call_reduction_viz.target_value == 95.0, "Call reduction target should be 95%"
        
        expected_achievement = (call_reduction / 95.0) * 100
        assert abs(call_reduction_viz.achievement_percentage - expected_achievement) < 0.01, \
            f"Call reduction achievement should be correctly calculated: {call_reduction_viz.achievement_percentage} vs {expected_achievement}"
        
        assert call_reduction_viz.visualization_type == "gauge", "Call reduction should use gauge visualization"
    
    # Verify batch efficiency visualization
    if batch_efficiency_viz:
        assert abs(batch_efficiency_viz.current_value - batch_efficiency) < 0.01, \
            f"Batch efficiency current value should match: {batch_efficiency_viz.current_value} vs {batch_efficiency}"
        assert batch_efficiency_viz.target_value == 98.0, "Batch efficiency target should be 98%"
        
        expected_achievement = (batch_efficiency / 98.0) * 100
        assert abs(batch_efficiency_viz.achievement_percentage - expected_achievement) < 0.01, \
            f"Batch efficiency achievement should be correctly calculated: {batch_efficiency_viz.achievement_percentage} vs {expected_achievement}"
        
        assert batch_efficiency_viz.visualization_type == "gauge", "Batch efficiency should use gauge visualization"
    
    # Verify cost savings visualization
    if cost_savings_viz:
        assert abs(cost_savings_viz.current_value - cost_savings) < 0.01, \
            f"Cost savings current value should match: {cost_savings_viz.current_value} vs {cost_savings}"
        assert cost_savings_viz.target_value == 90.0, "Cost savings target should be 90%"
        
        expected_achievement = (cost_savings / 90.0) * 100
        assert abs(cost_savings_viz.achievement_percentage - expected_achievement) < 0.01, \
            f"Cost savings achievement should be correctly calculated: {cost_savings_viz.achievement_percentage} vs {expected_achievement}"
        
        assert cost_savings_viz.visualization_type == "bar", "Cost savings should use bar visualization"
    
    # Verify resource utilization visualization
    if resource_viz:
        assert abs(resource_viz.current_value - resource_utilization) < 0.01, \
            f"Resource utilization current value should match: {resource_viz.current_value} vs {resource_utilization}"
        assert resource_viz.target_value == 80.0, "Resource utilization target should be 80%"
        
        expected_achievement = (resource_utilization / 80.0) * 100
        assert abs(resource_viz.achievement_percentage - expected_achievement) < 0.01, \
            f"Resource utilization achievement should be correctly calculated: {resource_viz.achievement_percentage} vs {expected_achievement}"
        
        assert resource_viz.visualization_type == "line", "Resource utilization should use line visualization"
    
    # Verify all visualizations have valid properties
    for viz in efficiency_viz:
        assert viz.current_value >= 0, f"Current value should be non-negative for {viz.metric_name}"
        assert viz.target_value > 0, f"Target value should be positive for {viz.metric_name}"
        assert viz.achievement_percentage >= 0, f"Achievement percentage should be non-negative for {viz.metric_name}"
        assert viz.trend_direction in ["improving", "stable", "declining"], \
            f"Trend direction should be valid for {viz.metric_name}"
        assert viz.visualization_type in ["gauge", "bar", "line"], \
            f"Visualization type should be valid for {viz.metric_name}"


@given(
    performance_scores=st.lists(st.floats(min_value=0.0, max_value=100.0), min_size=3, max_size=5),
    uptime_percentage=st.floats(min_value=95.0, max_value=100.0),
    efficiency_achievements=st.lists(st.floats(min_value=80.0, max_value=120.0), min_size=2, max_size=4)
)
@settings(max_examples=50)
def test_overall_performance_score_calculation(performance_scores, uptime_percentage, efficiency_achievements):
    """
    Test that overall performance score is calculated correctly from component metrics
    """
    # Create service
    service = PerformanceDisplayService()
    
    # Create mock performance display data
    performance_display = []
    for i, score in enumerate(performance_scores):
        performance_display.append(PerformanceDisplayData(
            metric_name=f"Metric {i}",
            before_value=100.0,
            after_value=100.0 - score,
            improvement_percentage=score,
            improvement_direction="decrease",
            unit="%",
            display_format="percentage"
        ))
    
    # Create mock uptime statistics
    uptime_stats = UptimeStatistics(
        current_uptime=uptime_percentage,
        historical_uptime=90.0,
        uptime_improvement=uptime_percentage - 90.0,
        availability_sla=99.0,
        sla_compliance=uptime_percentage >= 99.0,
        downtime_incidents=1,
        mttr_minutes=10.0,
        mtbf_hours=500.0
    )
    
    # Create mock efficiency visualizations
    efficiency_viz = []
    for i, achievement in enumerate(efficiency_achievements):
        efficiency_viz.append(EfficiencyVisualization(
            metric_name=f"Efficiency {i}",
            current_value=achievement,
            target_value=100.0,
            achievement_percentage=achievement,
            trend_direction="stable",
            visualization_type="gauge"
        ))
    
    # Calculate overall performance score
    overall_score = service._calculate_overall_performance_score(
        performance_display, uptime_stats, efficiency_viz
    )
    
    # Verify score properties
    assert isinstance(overall_score, float), "Overall score should be a float"
    assert 0.0 <= overall_score <= 100.0, f"Overall score should be between 0 and 100: {overall_score}"
    
    # Verify score calculation logic
    improvement_score = sum(performance_scores) / len(performance_scores) if performance_scores else 0
    efficiency_score = sum(efficiency_achievements) / len(efficiency_achievements) if efficiency_achievements else 0
    
    # Expected weighted average (uptime 40%, improvements 35%, efficiency 25%)
    expected_score = (uptime_percentage * 0.4 + improvement_score * 0.35 + efficiency_score * 0.25)
    expected_score = min(100.0, max(0.0, expected_score))
    
    assert abs(overall_score - expected_score) < 0.5, \
        f"Overall score should match weighted calculation: {overall_score} vs {expected_score}"


def test_performance_summary_completeness():
    """
    Test that performance summary contains all required fields
    """
    service = PerformanceDisplayService()
    
    # Mock all dependencies
    with patch.object(service, 'get_performance_comparison_display', return_value=[]), \
         patch.object(service, 'get_uptime_statistics'), \
         patch.object(service, 'get_efficiency_visualizations', return_value=[]):
        
        summary = service.format_performance_summary()
    
    # Verify summary structure
    assert isinstance(summary, dict), "Summary should be a dictionary"
    
    # Check for required top-level keys
    required_keys = ['overall_performance_score', 'key_improvements', 'reliability_status', 
                    'efficiency_highlights', 'performance_trends', 'recommendations']
    
    for key in required_keys:
        assert key in summary, f"Summary should contain '{key}' field"
    
    # Verify data types
    assert isinstance(summary['overall_performance_score'], (int, float)), \
        "Overall performance score should be numeric"
    assert isinstance(summary['key_improvements'], list), \
        "Key improvements should be a list"
    assert isinstance(summary['reliability_status'], dict), \
        "Reliability status should be a dictionary"
    assert isinstance(summary['efficiency_highlights'], list), \
        "Efficiency highlights should be a list"
    assert isinstance(summary['performance_trends'], dict), \
        "Performance trends should be a dictionary"
    assert isinstance(summary['recommendations'], list), \
        "Recommendations should be a list"


def test_display_data_consistency():
    """
    Test that display data maintains consistency across multiple calls
    """
    service = PerformanceDisplayService()
    
    # Get display data multiple times
    display1 = service.get_performance_comparison_display()
    display2 = service.get_performance_comparison_display()
    
    # Should be identical due to caching
    assert len(display1) == len(display2), "Display data length should be consistent"
    
    for i, (d1, d2) in enumerate(zip(display1, display2)):
        assert d1.metric_name == d2.metric_name, f"Metric name should be consistent at index {i}"
        assert d1.before_value == d2.before_value, f"Before value should be consistent at index {i}"
        assert d1.after_value == d2.after_value, f"After value should be consistent at index {i}"
        assert d1.improvement_percentage == d2.improvement_percentage, f"Improvement should be consistent at index {i}"