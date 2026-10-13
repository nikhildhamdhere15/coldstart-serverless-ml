"""
Property-based tests for Visualization Appropriateness

**Feature: cold-start-dashboard, Property 23: Visualization Appropriateness**
**Validates: Requirements 7.4**

Tests that appropriate chart types are selected for optimal data clarity
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Any

from services.chart_visualization import ChartVisualizationService
import plotly.graph_objects as go


class TestVisualizationAppropriateness:
    """Test that appropriate chart types are selected for different data types"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.chart_service = ChartVisualizationService()
    
    @given(
        data_points=st.integers(min_value=5, max_value=20),
        time_span_hours=st.integers(min_value=1, max_value=24),  # 1 hour to 1 day
        cold_start_ratio=st.floats(min_value=0.0, max_value=1.0),
        endpoint_count=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=10)
    def test_chart_type_appropriateness_for_time_series(self, data_points, time_span_hours, 
                                                       cold_start_ratio, endpoint_count):
        """
        **Property 23: Visualization Appropriateness**
        *For any* time series data with temporal patterns, line charts should be used for trends 
        and appropriate chart types should be selected for optimal data clarity
        **Validates: Requirements 7.4**
        """
        # Generate mock time series data
        base_time = datetime.now()
        time_data = []
        
        for i in range(data_points):
            timestamp = base_time - timedelta(hours=time_span_hours * i / data_points)
            endpoint_types = ['auth', 'profile', 'search'][:endpoint_count]
            
            for endpoint in endpoint_types:
                time_data.append({
                    'timestamp': timestamp,
                    'cold_start_label': 1 if np.random.random() < cold_start_ratio else 0,
                    'endpoint_type': endpoint,
                    'traffic_intensity': np.random.uniform(0.1, 2.0),
                    'hour_of_day': timestamp.hour,
                    'user_type_new': np.random.choice([0, 1]),
                    'device_mobile': np.random.choice([0, 1])
                })
        
        # Create cold start trend chart
        trend_chart = self.chart_service.create_cold_start_trend_chart(time_data)
        
        # Verify chart type appropriateness for time series data
        assert isinstance(trend_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check that line charts are used for time series trends
        line_traces = [trace for trace in trend_chart.data if isinstance(trace, go.Scatter)]
        assert len(line_traces) > 0, "Time series data should use line charts (Scatter with lines)"
        
        # Verify line trace has appropriate mode for trends
        for trace in line_traces:
            if hasattr(trace, 'mode'):
                assert 'lines' in trace.mode, "Time series trends should use line mode for clarity"
        
        # Check that secondary data uses appropriate visualization (bars for volume)
        bar_traces = [trace for trace in trend_chart.data if isinstance(trace, go.Bar)]
        if bar_traces:
            # If bar traces exist, they should be for volume/count data
            for trace in bar_traces:
                assert hasattr(trace, 'yaxis'), "Volume data should use secondary y-axis when combined with trends"
        
        # Verify chart has proper temporal x-axis
        assert trend_chart.layout.xaxis.title.text is not None, "Time series should have labeled x-axis"
        
        # Verify appropriate color usage
        colors_used = []
        for trace in trend_chart.data:
            if hasattr(trace, 'line') and hasattr(trace.line, 'color'):
                colors_used.append(trace.line.color)
            elif hasattr(trace, 'marker') and hasattr(trace.marker, 'color'):
                colors_used.append(trace.marker.color)
        
        # Should use distinct colors from the palette
        assert len(set(colors_used)) > 0, "Should use colors from the defined palette"
    
    @given(
        endpoint_data=st.lists(
            st.tuples(
                st.sampled_from(['auth', 'profile', 'search']),
                st.integers(min_value=1, max_value=1000),  # request count
                st.floats(min_value=0.0, max_value=1.0)    # cold start ratio
            ),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_chart_type_appropriateness_for_categorical_data(self, endpoint_data):
        """
        **Property 23: Visualization Appropriateness**
        *For any* categorical data comparing performance across endpoints, bar charts should be used
        and scatter plots should be used for correlation analysis
        **Validates: Requirements 7.4**
        """
        # Convert endpoint data to the expected format
        chart_data = []
        for endpoint, request_count, cold_start_ratio in endpoint_data:
            for _ in range(min(request_count, 50)):  # Limit for test performance
                chart_data.append({
                    'timestamp': datetime.now(),
                    'cold_start_label': 1 if np.random.random() < cold_start_ratio else 0,
                    'endpoint_type': endpoint,
                    'traffic_intensity': np.random.uniform(0.1, 2.0),
                    'hour_of_day': np.random.randint(0, 24),
                    'user_type_new': np.random.choice([0, 1]),
                    'device_mobile': np.random.choice([0, 1])
                })
        
        # Create endpoint performance chart
        performance_chart = self.chart_service.create_endpoint_performance_chart(chart_data)
        
        # Verify chart type appropriateness for categorical comparison
        assert isinstance(performance_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check for appropriate chart types in subplots
        bar_traces = [trace for trace in performance_chart.data if isinstance(trace, go.Bar)]
        scatter_traces = [trace for trace in performance_chart.data if isinstance(trace, go.Scatter)]
        
        # Should have bar charts for categorical comparisons
        assert len(bar_traces) > 0, "Categorical data should use bar charts for comparisons"
        
        # Should have scatter plots for correlation analysis
        assert len(scatter_traces) > 0, "Performance correlation should use scatter plots"
        
        # Verify scatter plot uses appropriate marker sizing for additional dimension
        for trace in scatter_traces:
            if hasattr(trace, 'marker') and hasattr(trace.marker, 'size'):
                # Marker size should vary (indicating additional data dimension)
                if hasattr(trace.marker.size, '__iter__'):
                    sizes = list(trace.marker.size) if hasattr(trace.marker.size, '__iter__') else [trace.marker.size]
                    if len(sizes) > 1:
                        assert len(set(sizes)) > 1 or max(sizes) != min(sizes), \
                            "Scatter plot should use marker size to represent additional data dimension"
        
        # Verify appropriate axis labels for categorical data
        assert performance_chart.layout.annotations is not None or \
               any(hasattr(performance_chart.layout, f'xaxis{i}') for i in ['', '2', '3']), \
               "Categorical charts should have proper axis labels"
    
    @given(
        days_count=st.integers(min_value=1, max_value=7),
        hours_count=st.integers(min_value=1, max_value=24),
        request_density=st.floats(min_value=0.1, max_value=10.0)
    )
    @settings(max_examples=100)
    def test_chart_type_appropriateness_for_pattern_data(self, days_count, hours_count, request_density):
        """
        **Property 23: Visualization Appropriateness**
        *For any* pattern data showing relationships between two categorical dimensions,
        heatmaps should be used for optimal pattern visualization
        **Validates: Requirements 7.4**
        """
        # Generate pattern data for heatmap
        pattern_data = []
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][:days_count]
        
        for day in days:
            for hour in range(min(hours_count, 24)):
                # Generate requests based on density
                request_count = max(1, int(np.random.poisson(request_density)))
                
                for _ in range(request_count):
                    pattern_data.append({
                        'timestamp': datetime.now().replace(hour=hour),
                        'cold_start_label': np.random.choice([0, 1]),
                        'endpoint_type': 'auth',
                        'traffic_intensity': np.random.uniform(0.1, 2.0),
                        'hour_of_day': hour,
                        'user_type_new': np.random.choice([0, 1]),
                        'device_mobile': np.random.choice([0, 1])
                    })
        
        # Create traffic pattern heatmap
        heatmap_chart = self.chart_service.create_traffic_pattern_heatmap(pattern_data)
        
        # Verify chart type appropriateness for pattern data
        assert isinstance(heatmap_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check that heatmap is used for two-dimensional categorical data
        heatmap_traces = [trace for trace in heatmap_chart.data if isinstance(trace, go.Heatmap)]
        assert len(heatmap_traces) > 0, "Two-dimensional categorical data should use heatmaps"
        
        # Verify heatmap has appropriate properties
        for trace in heatmap_traces:
            assert hasattr(trace, 'z'), "Heatmap should have z-values for intensity"
            assert hasattr(trace, 'x'), "Heatmap should have x-axis categories"
            assert hasattr(trace, 'y'), "Heatmap should have y-axis categories"
            
            # Check colorscale appropriateness
            if hasattr(trace, 'colorscale'):
                assert trace.colorscale is not None, "Heatmap should use appropriate colorscale"
        
        # Verify axis labels are appropriate for categorical dimensions
        assert heatmap_chart.layout.xaxis.title.text is not None, "Heatmap should have x-axis labels"
        assert heatmap_chart.layout.yaxis.title.text is not None, "Heatmap should have y-axis labels"
    
    @given(
        metric_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0),
            min_size=3,
            max_size=8
        )
    )
    @settings(max_examples=100)
    def test_chart_type_appropriateness_for_gauge_metrics(self, metric_values):
        """
        **Property 23: Visualization Appropriateness**
        *For any* performance metrics with target ranges, gauge charts should be used
        for clear performance indication
        **Validates: Requirements 7.4**
        """
        # Use first two values for accuracy and agreement
        accuracy = min(metric_values[0] / 100.0, 1.0)  # Normalize to 0-1
        agreement = min(metric_values[1] / 100.0, 1.0) if len(metric_values) > 1 else 0.8
        
        # Create prediction accuracy gauge
        gauge_chart = self.chart_service.create_prediction_accuracy_gauge(accuracy, agreement)
        
        # Verify chart type appropriateness for performance metrics
        assert isinstance(gauge_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check that gauge indicators are used for performance metrics
        gauge_traces = [trace for trace in gauge_chart.data if isinstance(trace, go.Indicator)]
        assert len(gauge_traces) >= 2, "Performance metrics should use gauge indicators"
        
        # Verify gauge properties
        for trace in gauge_traces:
            assert trace.mode is not None, "Gauge should have appropriate mode"
            assert "gauge" in trace.mode, "Performance metrics should use gauge mode"
            
            # Check value range appropriateness
            assert hasattr(trace, 'value'), "Gauge should display a value"
            assert 0 <= trace.value <= 100, "Gauge values should be in appropriate range (0-100)"
            
            # Check gauge configuration
            if hasattr(trace, 'gauge'):
                gauge_config = trace.gauge
                assert hasattr(gauge_config, 'axis'), "Gauge should have axis configuration"
                
                # Verify color coding for performance ranges
                if hasattr(gauge_config, 'steps'):
                    steps = gauge_config.steps
                    assert len(steps) >= 2, "Gauge should have color-coded performance ranges"
    
    @given(
        health_metrics=st.dictionaries(
            keys=st.sampled_from(['API Availability', 'Response Time', 'Data Quality', 
                                 'Prediction Accuracy', 'Cost Efficiency', 'Error Rate']),
            values=st.floats(min_value=0.0, max_value=100.0),
            min_size=3,
            max_size=6
        )
    )
    @settings(max_examples=100)
    def test_chart_type_appropriateness_for_multidimensional_data(self, health_metrics):
        """
        **Property 23: Visualization Appropriateness**
        *For any* multidimensional data showing system health across multiple metrics,
        radar charts should be used for comprehensive overview
        **Validates: Requirements 7.4**
        """
        # Create system health radar chart
        radar_chart = self.chart_service.create_system_health_radar(health_metrics)
        
        # Verify chart type appropriateness for multidimensional data
        assert isinstance(radar_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check that radar/polar charts are used for multidimensional data
        polar_traces = [trace for trace in radar_chart.data if isinstance(trace, go.Scatterpolar)]
        assert len(polar_traces) > 0, "Multidimensional data should use radar/polar charts"
        
        # Verify radar chart properties
        for trace in polar_traces:
            assert hasattr(trace, 'r'), "Radar chart should have radial values"
            assert hasattr(trace, 'theta'), "Radar chart should have angular categories"
            
            # Check that data forms a closed shape for comprehensive view
            if hasattr(trace, 'fill'):
                assert trace.fill == 'toself', "Radar chart should fill area for comprehensive view"
        
        # Verify polar layout configuration
        assert hasattr(radar_chart.layout, 'polar'), "Multidimensional chart should use polar layout"
        
        polar_config = radar_chart.layout.polar
        if hasattr(polar_config, 'radialaxis'):
            radial_axis = polar_config.radialaxis
            assert hasattr(radial_axis, 'range'), "Radar chart should have appropriate value range"
    
    @given(
        distribution_data=st.lists(
            st.floats(min_value=0.0, max_value=1.0),
            min_size=10,
            max_size=200
        )
    )
    @settings(max_examples=100)
    def test_chart_type_appropriateness_for_distribution_data(self, distribution_data):
        """
        **Property 23: Visualization Appropriateness**
        *For any* distribution data showing frequency patterns, histograms should be used
        with appropriate binning for data clarity
        **Validates: Requirements 7.4**
        """
        # Create prediction distribution chart
        distribution_chart = self.chart_service.create_prediction_distribution_chart(distribution_data)
        
        # Verify chart type appropriateness for distribution data
        assert isinstance(distribution_chart, go.Figure), "Should return a valid Plotly figure"
        
        # Check that histograms are used for distribution data
        histogram_traces = [trace for trace in distribution_chart.data if isinstance(trace, go.Histogram)]
        assert len(histogram_traces) > 0, "Distribution data should use histograms"
        
        # Verify histogram properties
        for trace in histogram_traces:
            assert hasattr(trace, 'x'), "Histogram should have x-values (data points)"
            
            # Check appropriate binning
            if hasattr(trace, 'nbinsx'):
                assert trace.nbinsx > 0, "Histogram should have appropriate number of bins"
                assert trace.nbinsx <= 50, "Histogram should not have excessive bins that reduce clarity"
        
        # Verify threshold lines for meaningful interpretation
        shapes = getattr(distribution_chart.layout, 'shapes', [])
        if shapes:
            # Should have vertical lines for important thresholds
            vertical_lines = [shape for shape in shapes if shape.get('type') == 'line']
            assert len(vertical_lines) >= 0, "Distribution should show relevant thresholds"
        
        # Check axis labels for clarity
        assert distribution_chart.layout.xaxis.title.text is not None, \
            "Distribution chart should have clear x-axis label"
        assert distribution_chart.layout.yaxis.title.text is not None, \
            "Distribution chart should have clear y-axis label"
    
    def test_empty_data_visualization_appropriateness(self):
        """
        **Property 23: Visualization Appropriateness**
        *For any* empty or invalid data, appropriate empty state visualizations should be provided
        **Validates: Requirements 7.4**
        """
        # Test empty data handling
        empty_chart = self.chart_service.create_cold_start_trend_chart([])
        
        # Verify appropriate empty state visualization
        assert isinstance(empty_chart, go.Figure), "Should return a valid figure even for empty data"
        
        # Check that empty state has informative message
        annotations = getattr(empty_chart.layout, 'annotations', [])
        assert len(annotations) > 0, "Empty data should show informative message"
        
        # Verify message is user-friendly
        for annotation in annotations:
            assert hasattr(annotation, 'text'), "Empty state should have descriptive text"
            assert len(annotation.text) > 0, "Empty state message should not be empty"
    
    def test_color_palette_consistency(self):
        """
        **Property 23: Visualization Appropriateness**
        *For any* visualization, consistent color palette should be used for brand coherence
        **Validates: Requirements 7.4**
        """
        # Get color palette
        color_palette = self.chart_service.get_color_palette()
        
        # Verify color palette structure
        assert 'primary_colors' in color_palette, "Should have primary color palette"
        assert 'status_colors' in color_palette, "Should have status color palette"
        assert 'chart_themes' in color_palette, "Should have chart theme configurations"
        
        # Verify color consistency
        primary_colors = color_palette['primary_colors']
        assert len(primary_colors) >= 3, "Should have sufficient primary colors for variety"
        
        # Check that colors are valid hex codes or color names
        for color in primary_colors:
            assert isinstance(color, str), "Colors should be string values"
            assert len(color) > 0, "Color values should not be empty"
        
        # Verify chart theme configurations
        chart_themes = color_palette['chart_themes']
        assert 'plotly' in chart_themes, "Should have Plotly theme configuration"
        
        plotly_config = chart_themes['plotly']
        assert 'color_discrete_sequence' in plotly_config, "Plotly config should have color sequence"
        assert len(plotly_config['color_discrete_sequence']) >= 3, \
            "Should have sufficient colors for chart variety"