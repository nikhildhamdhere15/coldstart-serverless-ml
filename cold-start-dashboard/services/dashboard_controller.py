"""
Dashboard Controller - Main orchestrator for the Cold Start Dashboard
Coordinates all services and manages the overall dashboard state
"""

import streamlit as st
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

from config import config_manager
from services.aws_clients import aws_client_manager
from services.live_prediction import LivePredictionService
from services.system_monitoring import SystemMonitoringService
from services.data_visualization import DataVisualizationService
from services.traffic_generation import TrafficGenerationController
from services.warming_system import WarmingSystemService
from services.cost_analytics import CostAnalyticsService
from services.performance_display import PerformanceDisplayService
from services.chart_visualization import chart_service
from services.ui_styling import ui_style_manager
from services.session_management import get_concurrent_user_handler
from services.external_access import external_access_service
from services.error_handling import error_handler
from services.error_display import get_error_display_service
from services.user_messages import user_message_service
from services.cloudwatch_logger import cloudwatch_logger


class DashboardController:
    """
    Main dashboard controller that orchestrates all services and manages state
    """
    
    def __init__(self):
        """Initialize the dashboard controller with all required services"""
        self.logger = logging.getLogger(__name__)
        
        # Core configuration
        self.config = config_manager
        
        # Initialize session management
        self.session_handler = get_concurrent_user_handler(config_manager.dashboard_config)
        
        # Initialize error handling
        self.error_handler = error_handler
        self.error_display_service = get_error_display_service(error_handler)
        
        # Service instances (initialized lazily)
        self._aws_clients = None
        self._live_prediction_service = None
        self._system_monitoring_service = None
        self._data_visualization_service = None
        self._traffic_generation_controller = None
        self._warming_system_service = None
        self._cost_analytics_service = None
        self._performance_display_service = None
        
        # Dashboard state
        self._initialization_status = {}
        self._last_health_check = None
        self._health_check_interval = 300  # 5 minutes
        
        # Performance tracking
        self._page_load_times = {}
        self._service_response_times = {}
        
    @property
    def aws_clients(self) -> Dict[str, Any]:
        """Get AWS clients, initializing if necessary"""
        if self._aws_clients is None:
            try:
                self._aws_clients = aws_client_manager.initialize_clients()
                self._initialization_status['aws_clients'] = True
                cloudwatch_logger.log_event('system_event', 'AWS clients initialized successfully')
            except Exception as e:
                self._initialization_status['aws_clients'] = False
                error_info = self.error_handler.handle_aws_error(e, 'aws_clients', 'initialize_clients')
                self.logger.error(f"Failed to initialize AWS clients: {error_info}")
                raise
        return self._aws_clients
    
    @property
    def live_prediction_service(self) -> LivePredictionService:
        """Get live prediction service, initializing if necessary"""
        if self._live_prediction_service is None:
            try:
                sagemaker_client = self.aws_clients.get('sagemaker')
                self._live_prediction_service = LivePredictionService(sagemaker_client)
                self._initialization_status['live_prediction'] = True
            except Exception as e:
                self._initialization_status['live_prediction'] = False
                error_info = self.error_handler.handle_aws_error(e, 'live_prediction', 'initialize_service')
                self.logger.error(f"Failed to initialize live prediction service: {error_info}")
                raise
        return self._live_prediction_service
    
    @property
    def system_monitoring_service(self) -> SystemMonitoringService:
        """Get system monitoring service, initializing if necessary"""
        if self._system_monitoring_service is None:
            try:
                cloudwatch_client = self.aws_clients.get('cloudwatch')
                lambda_client = self.aws_clients.get('lambda')
                sagemaker_client = self.aws_clients.get('sagemaker')
                
                self._system_monitoring_service = SystemMonitoringService(
                    cloudwatch_client, lambda_client, sagemaker_client
                )
                self._initialization_status['system_monitoring'] = True
            except Exception as e:
                self._initialization_status['system_monitoring'] = False
                error_info = self.error_handler.handle_aws_error(e, 'system_monitoring', 'initialize_service')
                self.logger.error(f"Failed to initialize system monitoring service: {error_info}")
                raise
        return self._system_monitoring_service
    
    @property
    def data_visualization_service(self) -> DataVisualizationService:
        """Get data visualization service, initializing if necessary"""
        if self._data_visualization_service is None:
            try:
                dynamodb_resource = self.aws_clients.get('dynamodb', {}).get('resource')
                self._data_visualization_service = DataVisualizationService(dynamodb_resource)
                self._initialization_status['data_visualization'] = True
            except Exception as e:
                self._initialization_status['data_visualization'] = False
                error_info = self.error_handler.handle_aws_error(e, 'data_visualization', 'initialize_service')
                self.logger.error(f"Failed to initialize data visualization service: {error_info}")
                raise
        return self._data_visualization_service
    
    @property
    def traffic_generation_controller(self) -> TrafficGenerationController:
        """Get traffic generation controller, initializing if necessary"""
        if self._traffic_generation_controller is None:
            try:
                lambda_client = self.aws_clients.get('lambda')
                self._traffic_generation_controller = TrafficGenerationController(lambda_client)
                self._initialization_status['traffic_generation'] = True
            except Exception as e:
                self._initialization_status['traffic_generation'] = False
                error_info = self.error_handler.handle_aws_error(e, 'traffic_generation', 'initialize_service')
                self.logger.error(f"Failed to initialize traffic generation controller: {error_info}")
                raise
        return self._traffic_generation_controller
    
    @property
    def warming_system_service(self) -> WarmingSystemService:
        """Get warming system service, initializing if necessary"""
        if self._warming_system_service is None:
            try:
                self._warming_system_service = WarmingSystemService(self.config.aws_config)
                self._initialization_status['warming_system'] = True
            except Exception as e:
                self._initialization_status['warming_system'] = False
                error_info = self.error_handler.handle_aws_error(e, 'warming_system', 'initialize_service')
                self.logger.error(f"Failed to initialize warming system service: {error_info}")
                raise
        return self._warming_system_service
    
    @property
    def cost_analytics_service(self) -> CostAnalyticsService:
        """Get cost analytics service, initializing if necessary"""
        if self._cost_analytics_service is None:
            try:
                cloudwatch_client = self.aws_clients.get('cloudwatch')
                dynamodb_resource = self.aws_clients.get('dynamodb', {}).get('resource')
                self._cost_analytics_service = CostAnalyticsService(cloudwatch_client, dynamodb_resource)
                self._initialization_status['cost_analytics'] = True
            except Exception as e:
                self._initialization_status['cost_analytics'] = False
                error_info = self.error_handler.handle_aws_error(e, 'cost_analytics', 'initialize_service')
                self.logger.error(f"Failed to initialize cost analytics service: {error_info}")
                raise
        return self._cost_analytics_service
    
    @property
    def performance_display_service(self) -> PerformanceDisplayService:
        """Get performance display service, initializing if necessary"""
        if self._performance_display_service is None:
            try:
                # PerformanceDisplayService takes cost_analytics and system_monitoring services
                self._performance_display_service = PerformanceDisplayService()
                self._initialization_status['performance_display'] = True
            except Exception as e:
                self._initialization_status['performance_display'] = False
                error_info = self.error_handler.handle_aws_error(e, 'performance_display', 'initialize_service')
                self.logger.error(f"Failed to initialize performance display service: {error_info}")
                raise
        return self._performance_display_service
    
    def initialize_dashboard(self) -> bool:
        """
        Initialize the dashboard and all required services
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Initialize session management first
            if not self.session_handler.initialize_session():
                self.logger.error("Failed to initialize session management")
                return False
            
            # Initialize AWS clients
            _ = self.aws_clients
            
            # Test basic connectivity
            connection_status = aws_client_manager.test_connections()
            if not any(connection_status.values()):
                self.logger.error("No AWS services are accessible")
                return False
            
            # Log successful initialization
            cloudwatch_logger.log_event('system_event', 'Dashboard controller initialized successfully')
            
            return True
            
        except Exception as e:
            error_info = self.error_handler.handle_aws_error(e, 'dashboard_controller', 'initialize_dashboard')
            self.logger.error(f"Dashboard initialization failed: {error_info}")
            return False
    
    def get_initialization_status(self) -> Dict[str, bool]:
        """Get the initialization status of all services"""
        return self._initialization_status.copy()
    
    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all services
        
        Returns:
            Dict containing health status of all components
        """
        current_time = datetime.now()
        
        # Check if we need to perform health check
        if (self._last_health_check is None or 
            (current_time - self._last_health_check).total_seconds() > self._health_check_interval):
            
            health_status = {
                'timestamp': current_time,
                'overall_health': 'healthy',
                'services': {},
                'aws_connectivity': {},
                'performance_metrics': {}
            }
            
            try:
                # Test AWS connectivity
                health_status['aws_connectivity'] = aws_client_manager.test_connections()
                
                # Check system monitoring service
                try:
                    system_health = self.system_monitoring_service.get_system_health()
                    health_status['services']['system_monitoring'] = {
                        'status': 'healthy',
                        'api_status': system_health.api_status,
                        'uptime': system_health.uptime_percentage
                    }
                except Exception as e:
                    health_status['services']['system_monitoring'] = {
                        'status': 'error',
                        'error': str(e)
                    }
                
                # Check data visualization service
                if self._initialization_status.get('data_visualization', False):
                    try:
                        # Test data fetch
                        recent_data = self.data_visualization_service.get_recent_requests(limit=1)
                        health_status['services']['data_visualization'] = {
                            'status': 'healthy',
                            'data_available': len(recent_data) > 0
                        }
                    except Exception as e:
                        health_status['services']['data_visualization'] = {
                            'status': 'error',
                            'error': str(e)
                        }
                
                # Check live prediction service
                if self._initialization_status.get('live_prediction', False):
                    try:
                        endpoint_status = self.live_prediction_service.get_endpoint_status()
                        health_status['services']['live_prediction'] = {
                            'status': 'healthy',
                            'endpoints': endpoint_status
                        }
                    except Exception as e:
                        health_status['services']['live_prediction'] = {
                            'status': 'error',
                            'error': str(e)
                        }
                
                # Determine overall health
                service_errors = [s for s in health_status['services'].values() if s.get('status') == 'error']
                aws_connectivity_issues = [k for k, v in health_status['aws_connectivity'].items() if not v]
                
                if service_errors or len(aws_connectivity_issues) > 2:
                    health_status['overall_health'] = 'critical'
                elif aws_connectivity_issues:
                    health_status['overall_health'] = 'degraded'
                
                self._last_health_check = current_time
                
            except Exception as e:
                health_status['overall_health'] = 'critical'
                health_status['error'] = str(e)
                self.logger.error(f"Health check failed: {e}")
            
            # Cache the health status
            st.session_state['dashboard_health_status'] = health_status
            
        else:
            # Return cached health status
            health_status = st.session_state.get('dashboard_health_status', {
                'overall_health': 'unknown',
                'timestamp': current_time
            })
        
        return health_status
    
    def create_sidebar_navigation(self):
        """Create comprehensive sidebar navigation with all dashboard sections"""
        with st.sidebar:
            # Enhanced branding section
            ui_style_manager.create_enhanced_logo_section(show_version=True, show_description=False)
            
            st.markdown("---")
            
            # Main navigation sections
            st.markdown('<div class="nav-section">', unsafe_allow_html=True)
            st.markdown('<h3>🧭 Navigation</h3>', unsafe_allow_html=True)
            
            page = st.selectbox(
                "Select Dashboard Section",
                [
                    "🏠 Overview",
                    "🤖 Live Predictions", 
                    "📊 System Monitoring",
                    "📈 Data Visualization",
                    "🚦 Traffic Generation",
                    "🔥 Warming System",
                    "💰 Cost Analytics",
                    "🌐 External Access"
                ]
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Enhanced settings section
            st.markdown('<div class="nav-section">', unsafe_allow_html=True)
            st.markdown('<h3>⚙️ Settings</h3>', unsafe_allow_html=True)
            
            # Get performance settings from session manager
            performance_settings = self.session_handler.get_performance_settings()
            
            auto_refresh = st.checkbox("Auto Refresh", value=performance_settings.get("real_time_updates", True))
            
            if auto_refresh:
                refresh_interval = st.slider(
                    "Refresh Interval (seconds)",
                    min_value=10,
                    max_value=120,
                    value=performance_settings.get("auto_refresh_interval", self.config.dashboard_config.auto_refresh_interval),
                    step=10
                )
            else:
                refresh_interval = None
            
            # Enhanced manual refresh button
            if st.button("🔄 Refresh Now", type="primary"):
                self.clear_all_caches()
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Enhanced system status section
            self.create_system_status_display()
            
            # Session management display
            self.session_handler.session_manager.create_session_status_display()
            
            st.markdown("---")
            
            # Enhanced footer information
            st.caption(f"Last Updated: {datetime.now().strftime('%H:%M:%S')}")
            st.caption(f"{ui_style_manager.BRAND['name']} {ui_style_manager.BRAND['version']}")
            
            return page, auto_refresh, refresh_interval
    
    def create_system_status_display(self):
        """Create enhanced system status display in sidebar"""
        st.markdown('<div class="nav-section">', unsafe_allow_html=True)
        st.markdown('<h3>🔍 System Status</h3>', unsafe_allow_html=True)
        
        # Configuration validation
        config_status = self.config.validate_configuration()
        
        if all(config_status.values()):
            ui_style_manager.create_enhanced_status_indicator("healthy", "✅ Configuration Valid")
        else:
            ui_style_manager.create_enhanced_status_indicator("error", "❌ Configuration Issues")
            with st.expander("View Issues"):
                for item, status in config_status.items():
                    icon = "✅" if status else "❌"
                    st.write(f"{icon} {item.replace('_', ' ').title()}")
        
        # Health check status
        health_status = self.perform_health_check()
        overall_health = health_status.get('overall_health', 'unknown')
        
        if overall_health == 'healthy':
            ui_style_manager.create_enhanced_status_indicator("healthy", "✅ All Systems Operational")
        elif overall_health == 'degraded':
            ui_style_manager.create_enhanced_status_indicator("warning", "⚠️ Some Issues Detected")
        elif overall_health == 'critical':
            ui_style_manager.create_enhanced_status_indicator("error", "❌ Critical Issues")
        else:
            ui_style_manager.create_enhanced_status_indicator("info", "🔄 Checking Status...")
        
        # Service initialization status
        init_status = self.get_initialization_status()
        if init_status:
            with st.expander("Service Status"):
                for service, status in init_status.items():
                    icon = "✅" if status else "❌"
                    service_name = service.replace('_', ' ').title()
                    st.write(f"{icon} {service_name}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def clear_all_caches(self):
        """Clear all service caches to force data refresh"""
        try:
            # Clear data visualization cache
            if self._data_visualization_service:
                self._data_visualization_service.clear_cache()
            
            # Clear session state caches
            cache_keys = [k for k in st.session_state.keys() if k.endswith('_cache')]
            for key in cache_keys:
                del st.session_state[key]
            
            # Clear health check cache
            self._last_health_check = None
            
            cloudwatch_logger.log_event('system_event', 'All caches cleared')
            
        except Exception as e:
            self.logger.error(f"Failed to clear caches: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get dashboard performance metrics"""
        session_metrics = self.session_handler.session_manager.get_session_metrics()
        return {
            'page_load_times': self._page_load_times.copy(),
            'service_response_times': self._service_response_times.copy(),
            'initialization_status': self._initialization_status.copy(),
            'last_health_check': self._last_health_check,
            'session_count': session_metrics.active_sessions
        }
    
    def track_page_load_time(self, page_name: str, load_time: float):
        """Track page load time for performance monitoring"""
        if page_name not in self._page_load_times:
            self._page_load_times[page_name] = []
        
        self._page_load_times[page_name].append({
            'timestamp': datetime.now(),
            'load_time': load_time
        })
        
        # Keep only last 10 measurements per page
        self._page_load_times[page_name] = self._page_load_times[page_name][-10:]
    
    def handle_service_error(self, service_name: str, operation: str, error: Exception) -> Dict[str, Any]:
        """
        Handle service errors with comprehensive error information
        
        Args:
            service_name: Name of the service that failed
            operation: Operation that was being performed
            error: The exception that occurred
            
        Returns:
            Dict containing error information and user-friendly messages
        """
        error_info = self.error_handler.handle_aws_error(error, service_name, operation)
        user_message = user_message_service.create_user_friendly_error_message(error_info)
        
        # Log the error
        self.logger.error(f"Service error in {service_name}.{operation}: {error}")
        cloudwatch_logger.log_event('error_event', f"{service_name}.{operation} failed: {str(error)}")
        
        # Update service status
        self._initialization_status[service_name] = False
        
        return {
            'error_info': error_info,
            'user_message': user_message,
            'service_name': service_name,
            'operation': operation
        }
    
    def create_error_display(self, error_data: Dict[str, Any]):
        """Create user-friendly error display"""
        user_message = error_data['user_message']
        
        st.error(f"{user_message['icon']} {user_message['title']}")
        st.error(user_message['message'])
        
        if user_message.get('actions'):
            st.info("**What you can do:**")
            for action in user_message['actions']:
                st.write(f"• {action}")
        
        # Show fallback options if available
        service_name = error_data['service_name']
        fallback_message = user_message_service.create_fallback_data_message(
            'dashboard', service_name, 'default'
        )
        
        if fallback_message:
            st.warning(f"{fallback_message['icon']} {fallback_message['message']}")


# Global dashboard controller instance
dashboard_controller = DashboardController()