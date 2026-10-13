"""
Chart Visualization Service - Interactive charts and graphs for the Cold Start Dashboard
Provides comprehensive data visualization using Plotly and Matplotlib
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import streamlit as st
from services.ui_styling import ui_style_manager

class ChartVisualizationService:
    """Service for creating interactive charts and visualizations"""
    
    def __init__(self):
        """Initialize the chart visualization service"""
        self.color_palette = ui_style_manager.get_color_palette()
        self.chart_config = ui_style_manager.apply_chart_styling("plotly")
    
    def create_cold_start_trend_chart(self, data: List[Dict]) -> go.Figure:
        """Create an interactive cold start trend chart over time"""
        
        if not data:
            return self._create_empty_chart("No data available for cold start trends")
        
        # Convert data to DataFrame for easier manipulation
        # Handle both dict and object data
        if hasattr(data[0], '__dict__'):
            # Convert objects to dictionaries
            data = [vars(item) if hasattr(item, '__dict__') else item for item in data]
        
        df = pd.DataFrame(data)
        
        # Ensure timestamp column exists
        if 'timestamp' not in df.columns:
            return self._create_empty_chart("No timestamp data available")
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Group by hour and calculate cold start ratio
        df['hour'] = df['timestamp'].dt.floor('H')
        hourly_stats = df.groupby('hour').agg({
            'cold_start_label': ['count', 'sum'],
            'timestamp': 'count'
        }).reset_index()
        
        hourly_stats.columns = ['hour', 'total_requests', 'cold_starts', 'request_count']
        hourly_stats['cold_start_ratio'] = (hourly_stats['cold_starts'] / hourly_stats['total_requests']) * 100
        
        # Create the figure
        fig = go.Figure()
        
        # Add cold start ratio line
        fig.add_trace(go.Scatter(
            x=hourly_stats['hour'],
            y=hourly_stats['cold_start_ratio'],
            mode='lines+markers',
            name='Cold Start Ratio (%)',
            line=dict(color=self.color_palette['primary_colors'][0], width=3),
            marker=dict(size=8, color=self.color_palette['primary_colors'][0]),
            hovertemplate='<b>%{x}</b><br>Cold Start Ratio: %{y:.1f}%<extra></extra>'
        ))
        
        # Add request volume as secondary y-axis
        fig.add_trace(go.Bar(
            x=hourly_stats['hour'],
            y=hourly_stats['total_requests'],
            name='Total Requests',
            yaxis='y2',
            opacity=0.3,
            marker_color=self.color_palette['primary_colors'][1],
            hovertemplate='<b>%{x}</b><br>Total Requests: %{y}<extra></extra>'
        ))
        
        # Update layout
        fig.update_layout(
            title={
                'text': '📈 Cold Start Trends Over Time',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            xaxis_title='Time',
            yaxis_title='Cold Start Ratio (%)',
            yaxis2=dict(
                title='Total Requests',
                overlaying='y',
                side='right'
            ),
            hovermode='x unified',
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_endpoint_performance_chart(self, data: List[Dict]) -> go.Figure:
        """Create a performance comparison chart by endpoint"""
        
        if not data:
            return self._create_empty_chart("No data available for endpoint performance")
        
        # Handle both dict and object data
        if hasattr(data[0], '__dict__'):
            data = [vars(item) if hasattr(item, '__dict__') else item for item in data]
        
        # Process data by endpoint
        df = pd.DataFrame(data)
        
        # Ensure required columns exist
        if 'endpoint_type' not in df.columns or 'cold_start_label' not in df.columns:
            return self._create_empty_chart("Missing required data for endpoint performance")
            
        endpoint_stats = df.groupby('endpoint_type').agg({
            'cold_start_label': ['count', 'sum'],
            'traffic_intensity': 'mean'
        }).reset_index()
        
        endpoint_stats.columns = ['endpoint', 'total_requests', 'cold_starts', 'avg_traffic']
        endpoint_stats['cold_start_ratio'] = (endpoint_stats['cold_starts'] / endpoint_stats['total_requests']) * 100
        endpoint_stats['performance_score'] = 100 - endpoint_stats['cold_start_ratio']
        
        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Cold Start Ratio by Endpoint', 'Performance Score vs Traffic'),
            specs=[[{"secondary_y": False}, {"secondary_y": True}]]
        )
        
        # Cold start ratio bar chart
        fig.add_trace(
            go.Bar(
                x=endpoint_stats['endpoint'],
                y=endpoint_stats['cold_start_ratio'],
                name='Cold Start Ratio (%)',
                marker_color=self.color_palette['primary_colors'][0],
                text=endpoint_stats['cold_start_ratio'].round(1),
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>Cold Start Ratio: %{y:.1f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Performance score scatter plot
        fig.add_trace(
            go.Scatter(
                x=endpoint_stats['avg_traffic'],
                y=endpoint_stats['performance_score'],
                mode='markers+text',
                name='Performance Score',
                marker=dict(
                    size=endpoint_stats['total_requests'] / 10,  # Size based on request count
                    color=self.color_palette['primary_colors'][2],
                    opacity=0.7,
                    line=dict(width=2, color='white')
                ),
                text=endpoint_stats['endpoint'],
                textposition='top center',
                hovertemplate='<b>%{text}</b><br>Avg Traffic: %{x:.2f}<br>Performance Score: %{y:.1f}%<extra></extra>'
            ),
            row=1, col=2
        )
        
        # Update layout
        fig.update_layout(
            title={
                'text': '🎯 Endpoint Performance Analysis',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            showlegend=False,
            **self.chart_config['layout']
        )
        
        fig.update_xaxes(title_text="Endpoint", row=1, col=1)
        fig.update_yaxes(title_text="Cold Start Ratio (%)", row=1, col=1)
        fig.update_xaxes(title_text="Average Traffic Intensity", row=1, col=2)
        fig.update_yaxes(title_text="Performance Score (%)", row=1, col=2)
        
        return fig
    
    def create_traffic_pattern_heatmap(self, data: List[Dict]) -> go.Figure:
        """Create a heatmap showing traffic patterns by hour and day"""
        
        if not data:
            return self._create_empty_chart("No data available for traffic patterns")
        
        # Handle both dict and object data
        if hasattr(data[0], '__dict__'):
            data = [vars(item) if hasattr(item, '__dict__') else item for item in data]
        
        # Process data for heatmap
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['hour'] = df['timestamp'].dt.hour
        df['day_name'] = df['timestamp'].dt.day_name()
        
        # Create pivot table for heatmap
        heatmap_data = df.groupby(['day_name', 'hour']).size().reset_index(name='request_count')
        heatmap_pivot = heatmap_data.pivot(index='day_name', columns='hour', values='request_count').fillna(0)
        
        # Reorder days
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_pivot = heatmap_pivot.reindex([day for day in day_order if day in heatmap_pivot.index])
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=[f"{hour:02d}:00" for hour in heatmap_pivot.columns],
            y=heatmap_pivot.index,
            colorscale='Blues',
            hoverongaps=False,
            hovertemplate='<b>%{y}</b> at <b>%{x}</b><br>Requests: %{z}<extra></extra>'
        ))
        
        fig.update_layout(
            title={
                'text': '🕒 Traffic Patterns by Day and Hour',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            xaxis_title='Hour of Day',
            yaxis_title='Day of Week',
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_prediction_accuracy_gauge(self, accuracy: float, model_agreement: float) -> go.Figure:
        """Create gauge charts for prediction accuracy and model agreement"""
        
        # Create subplot with two gauges
        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=('Prediction Accuracy', 'Model Agreement')
        )
        
        # Accuracy gauge
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=accuracy * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Accuracy (%)"},
            delta={'reference': 90, 'increasing': {'color': self.color_palette['status_colors']['healthy']}},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': self.color_palette['primary_colors'][0]},
                'steps': [
                    {'range': [0, 70], 'color': self.color_palette['status_colors']['error']},
                    {'range': [70, 85], 'color': self.color_palette['status_colors']['warning']},
                    {'range': [85, 100], 'color': self.color_palette['status_colors']['healthy']}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 95
                }
            }
        ), row=1, col=1)
        
        # Model agreement gauge
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=model_agreement * 100,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Agreement (%)"},
            delta={'reference': 80, 'increasing': {'color': self.color_palette['status_colors']['healthy']}},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': self.color_palette['primary_colors'][2]},
                'steps': [
                    {'range': [0, 60], 'color': self.color_palette['status_colors']['error']},
                    {'range': [60, 80], 'color': self.color_palette['status_colors']['warning']},
                    {'range': [80, 100], 'color': self.color_palette['status_colors']['healthy']}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ), row=1, col=2)
        
        fig.update_layout(
            title={
                'text': '🎯 ML Model Performance Metrics',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_cost_savings_chart(self, monthly_data: Dict[str, float]) -> go.Figure:
        """Create a cost savings visualization chart"""
        
        # Prepare data
        categories = list(monthly_data.keys())
        values = list(monthly_data.values())
        
        # Create waterfall chart for cost breakdown
        fig = go.Figure(go.Waterfall(
            name="Cost Analysis",
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=categories,
            textposition="outside",
            text=[f"${v:.2f}" for v in values],
            y=values,
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": self.color_palette['status_colors']['healthy']}},
            decreasing={"marker": {"color": self.color_palette['status_colors']['error']}},
            totals={"marker": {"color": self.color_palette['primary_colors'][0]}}
        ))
        
        fig.update_layout(
            title={
                'text': '💰 Monthly Cost Analysis',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            xaxis_title='Cost Categories',
            yaxis_title='Amount ($)',
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_system_health_radar(self, health_metrics: Dict[str, float]) -> go.Figure:
        """Create a radar chart for system health metrics"""
        
        categories = list(health_metrics.keys())
        values = list(health_metrics.values())
        
        # Add the first value at the end to close the radar chart
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill='toself',
            name='System Health',
            line_color=self.color_palette['primary_colors'][0],
            fillcolor=f"rgba({int(self.color_palette['primary_colors'][0][1:3], 16)}, {int(self.color_palette['primary_colors'][0][3:5], 16)}, {int(self.color_palette['primary_colors'][0][5:7], 16)}, 0.3)"
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            title={
                'text': '🏥 System Health Overview',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_real_time_metrics_dashboard(self, metrics_data: Dict[str, Any]) -> go.Figure:
        """Create a real-time metrics dashboard with multiple subplots"""
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Request Volume', 'Response Times', 'Error Rates', 'Resource Utilization'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Request Volume (Line chart)
        if 'request_volume' in metrics_data:
            timestamps = metrics_data['request_volume']['timestamps']
            volumes = metrics_data['request_volume']['values']
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=volumes,
                    mode='lines+markers',
                    name='Requests/min',
                    line=dict(color=self.color_palette['primary_colors'][0], width=2),
                    marker=dict(size=4)
                ),
                row=1, col=1
            )
        
        # Response Times (Box plot)
        if 'response_times' in metrics_data:
            response_times = metrics_data['response_times']
            
            fig.add_trace(
                go.Box(
                    y=response_times,
                    name='Response Time (ms)',
                    marker_color=self.color_palette['primary_colors'][1],
                    boxpoints='outliers'
                ),
                row=1, col=2
            )
        
        # Error Rates (Bar chart)
        if 'error_rates' in metrics_data:
            endpoints = metrics_data['error_rates']['endpoints']
            error_rates = metrics_data['error_rates']['rates']
            
            fig.add_trace(
                go.Bar(
                    x=endpoints,
                    y=error_rates,
                    name='Error Rate (%)',
                    marker_color=self.color_palette['status_colors']['error']
                ),
                row=2, col=1
            )
        
        # Resource Utilization (Pie chart)
        if 'resource_utilization' in metrics_data:
            resources = metrics_data['resource_utilization']['resources']
            utilization = metrics_data['resource_utilization']['values']
            
            fig.add_trace(
                go.Pie(
                    labels=resources,
                    values=utilization,
                    name='Resource Usage',
                    marker_colors=self.color_palette['primary_colors'][:len(resources)]
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            title={
                'text': '📊 Real-Time System Metrics',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            showlegend=False,
            **self.chart_config['layout']
        )
        
        return fig
    
    def create_prediction_distribution_chart(self, predictions: List[float]) -> go.Figure:
        """Create a distribution chart for prediction probabilities"""
        
        if not predictions:
            return self._create_empty_chart("No prediction data available")
        
        # Create histogram
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=predictions,
            nbinsx=20,
            name='Prediction Distribution',
            marker_color=self.color_palette['primary_colors'][0],
            opacity=0.7,
            hovertemplate='Probability Range: %{x}<br>Count: %{y}<extra></extra>'
        ))
        
        # Add vertical lines for risk thresholds
        fig.add_vline(x=0.5, line_dash="dash", line_color=self.color_palette['status_colors']['warning'], 
                     annotation_text="Moderate Risk")
        fig.add_vline(x=0.7, line_dash="dash", line_color=self.color_palette['status_colors']['error'], 
                     annotation_text="High Risk")
        
        fig.update_layout(
            title={
                'text': '📊 Cold Start Prediction Distribution',
                'x': 0.5,
                'font': {'size': 18, 'family': ui_style_manager.FONTS['heading']}
            },
            xaxis_title='Prediction Probability',
            yaxis_title='Frequency',
            **self.chart_config['layout']
        )
        
        return fig
    
    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create an empty chart with a message"""
        
        fig = go.Figure()
        
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor='center', yanchor='middle',
            font=dict(size=16, color=ui_style_manager.COLORS['text_secondary'])
        )
        
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            **self.chart_config['layout']
        )
        
        return fig
    
    def get_chart_config(self) -> Dict[str, Any]:
        """Get the standard chart configuration"""
        return self.chart_config
    
    def render_chart_with_container(self, fig: go.Figure, container_class: str = "chart-container"):
        """Render a chart with proper container styling"""
        
        # Add container styling
        st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True)
        
        # Render the chart
        st.plotly_chart(fig, use_container_width=True, config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
        })
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def generate_appropriate_charts(self, data: List[Dict]) -> Dict[str, go.Figure]:
        """Generate appropriate charts based on data characteristics"""
        charts = {}
        
        if not data:
            charts['empty'] = self._create_empty_chart("No data available")
            return charts
        
        # Handle both dict and object data
        if hasattr(data[0], '__dict__'):
            data = [vars(item) if hasattr(item, '__dict__') else item for item in data]
        
        # Generate different chart types based on data
        charts['trend'] = self.create_cold_start_trend_chart(data)
        charts['endpoint_performance'] = self.create_endpoint_performance_chart(data)
        charts['traffic_heatmap'] = self.create_traffic_pattern_heatmap(data)
        
        # Add prediction distribution if we have prediction data
        try:
            if any(isinstance(item, dict) and 'prediction_probability' in item for item in data):
                predictions = [item.get('prediction_probability', 0) for item in data if isinstance(item, dict)]
                if predictions:
                    charts['prediction_distribution'] = self.create_prediction_distribution_chart(predictions)
        except (TypeError, AttributeError):
            # Skip prediction distribution if data format is incompatible
            pass
        
        return charts

# Global instance for easy access
chart_service = ChartVisualizationService()