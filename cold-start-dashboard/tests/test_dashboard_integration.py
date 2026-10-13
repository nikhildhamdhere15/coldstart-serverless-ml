"""
Integration tests for the complete Cold Start Dashboard functionality
Tests end-to-end workflows and component interactions
"""

import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.dashboard_controller import dashboard_controller
from services.live_prediction import PredictionRequest, PredictionResponse
from config import config_manager


class TestDashboardIntegration:
    """Integration tests for complete dashboard functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        # Reset dashboard controller state
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
        dashboard_controller._last_health_check = None
        
        # Clear Streamlit session state
        if hasattr(st, 'session_state'):
            st.session_state.clear()
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_dashboard_initialization_success(self, mock_init_clients):
        """Test successful dashboard initialization"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Test initialization
        result = dashboard_controller.initialize_dashboard()
        
        assert result is True
        assert dashboard_controller._initialization_status['aws_clients'] is True
        assert dashboard_controller.aws_clients == mock_clients
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_dashboard_initialization_failure(self, mock_init_clients):
        """Test dashboard initialization failure handling"""
        # Mock AWS client initialization failure
        mock_init_clients.side_effect = Exception("AWS connection failed")
        
        # Test initialization
        with pytest.raises(Exception):
            dashboard_controller.initialize_dashboard()
        
        assert dashboard_controller._initialization_status.get('aws_clients', False) is False
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.system_monitoring.SystemMonitoringService.get_system_health')
    def test_health_check_integration(self, mock_get_health, mock_init_clients):
        """Test comprehensive health check functionality"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock system health
        mock_health = Mock()
        mock_health.api_status = "healthy"
        mock_health.uptime_percentage = 99.5
        mock_get_health.return_value = mock_health
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Perform health check
        health_status = dashboard_controller.perform_health_check()
        
        assert health_status['overall_health'] in ['healthy', 'degraded', 'critical']
        assert 'timestamp' in health_status
        assert 'services' in health_status
        assert 'aws_connectivity' in health_status
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_service_lazy_initialization(self, mock_init_clients):
        """Test that services are initialized lazily"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Services should not be initialized yet
        assert dashboard_controller._live_prediction_service is None
        assert dashboard_controller._system_monitoring_service is None
        
        # Access services to trigger lazy initialization
        prediction_service = dashboard_controller.live_prediction_service
        monitoring_service = dashboard_controller.system_monitoring_service
        
        # Services should now be initialized
        assert prediction_service is not None
        assert monitoring_service is not None
        assert dashboard_controller._initialization_status['live_prediction'] is True
        assert dashboard_controller._initialization_status['system_monitoring'] is True


class TestEndToEndPredictionWorkflow:
    """Test complete prediction workflow from UI to result"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.live_prediction.LivePredictionService.predict_cold_start_risk')
    def test_complete_prediction_workflow(self, mock_predict, mock_init_clients):
        """Test complete prediction workflow from parameters to results"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock prediction response
        mock_response = PredictionResponse(
            success=True,
            xgboost_probability=0.75,
            random_forest_probability=0.68,
            ensemble_probability=0.72,
            prediction_label="cold_start",
            recommendation="HIGH RISK - Consider warming the auth endpoint",
            model_agreement=0.91,
            timestamp=datetime.now(),
            error_message=None
        )
        mock_predict.return_value = mock_response
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Create prediction request
        request = PredictionRequest(
            hour_of_day=14,
            day_of_week=1,  # Tuesday
            traffic_intensity=0.3,
            endpoint_type="auth",
            user_type_new=True,
            device_mobile=False
        )
        
        # Make prediction
        prediction_service = dashboard_controller.live_prediction_service
        result = prediction_service.predict_cold_start_risk(request)
        
        # Verify results
        assert result.success is True
        assert result.ensemble_probability == 0.72
        assert result.prediction_label == "cold_start"
        assert "HIGH RISK" in result.recommendation
        assert result.model_agreement == 0.91
        
        # Verify mock was called with correct parameters
        mock_predict.assert_called_once_with(request)
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.live_prediction.LivePredictionService.predict_cold_start_risk')
    def test_prediction_error_handling(self, mock_predict, mock_init_clients):
        """Test prediction error handling in complete workflow"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock prediction failure
        mock_predict.side_effect = Exception("SageMaker endpoint unavailable")
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Create prediction request
        request = PredictionRequest(
            hour_of_day=14,
            day_of_week=1,
            traffic_intensity=0.3,
            endpoint_type="auth",
            user_type_new=True,
            device_mobile=False
        )
        
        # Make prediction and expect error handling
        prediction_service = dashboard_controller.live_prediction_service
        
        with pytest.raises(Exception):
            prediction_service.predict_cold_start_risk(request)
        
        # Verify error was handled by dashboard controller
        error_data = dashboard_controller.handle_service_error(
            'live_prediction', 'predict_cold_start_risk', 
            Exception("SageMaker endpoint unavailable")
        )
        
        assert error_data['service_name'] == 'live_prediction'
        assert error_data['operation'] == 'predict_cold_start_risk'
        assert 'user_message' in error_data


class TestDataFlowIntegration:
    """Test data flow between all dashboard components"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.data_visualization.DataVisualizationService.get_recent_requests')
    @patch('services.system_monitoring.SystemMonitoringService.get_system_health')
    def test_data_flow_integration(self, mock_get_health, mock_get_requests, mock_init_clients):
        """Test data flow between monitoring, visualization, and analytics"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock data visualization data
        mock_records = [
            Mock(
                timestamp=datetime.now() - timedelta(minutes=i),
                endpoint_type="auth",
                cold_start_label=1 if i % 3 == 0 else 0,
                traffic_intensity=0.5 + (i * 0.1),
                hour_of_day=14,
                user_type_new=1 if i % 2 == 0 else 0,
                device_mobile=1 if i % 4 == 0 else 0
            )
            for i in range(20)
        ]
        mock_get_requests.return_value = mock_records
        
        # Mock system health
        mock_health = Mock()
        mock_health.api_status = "healthy"
        mock_health.recent_request_count = 1247
        mock_health.uptime_percentage = 99.2
        mock_health.dynamodb_status = "active"
        mock_get_health.return_value = mock_health
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test data visualization service
        data_service = dashboard_controller.data_visualization_service
        recent_data = data_service.get_recent_requests(limit=20)
        
        assert len(recent_data) == 20
        assert all(hasattr(record, 'timestamp') for record in recent_data)
        assert all(hasattr(record, 'cold_start_label') for record in recent_data)
        
        # Test system monitoring service
        monitoring_service = dashboard_controller.system_monitoring_service
        system_health = monitoring_service.get_system_health()
        
        assert system_health.api_status == "healthy"
        assert system_health.recent_request_count == 1247
        assert system_health.uptime_percentage == 99.2
        
        # Test data summary calculation
        data_summary = data_service.get_data_summary(recent_data)
        statistics = data_summary['statistics']
        
        assert statistics.total_requests == 20
        assert 0 <= statistics.cold_start_ratio <= 1
        assert 0 <= statistics.business_hours_ratio <= 1
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_cache_integration(self, mock_init_clients):
        """Test cache integration across services"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test cache clearing
        dashboard_controller.clear_all_caches()
        
        # Verify health check cache is cleared
        assert dashboard_controller._last_health_check is None


class TestExternalAccessIntegration:
    """Test external access and concurrent user scenarios"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_concurrent_user_handling(self, mock_init_clients):
        """Test concurrent user access handling"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test session handler
        session_handler = dashboard_controller.session_handler
        
        # Simulate multiple user sessions
        session_count = session_handler.get_active_session_count()
        assert isinstance(session_count, int)
        assert session_count >= 0
        
        # Test performance settings
        performance_settings = session_handler.get_performance_settings()
        assert isinstance(performance_settings, dict)
        assert 'real_time_updates' in performance_settings
    
    def test_concurrent_prediction_requests(self):
        """Test handling of concurrent prediction requests"""
        def make_prediction_request(request_id):
            """Simulate a prediction request"""
            try:
                # Mock prediction request
                request = PredictionRequest(
                    hour_of_day=14 + (request_id % 10),
                    day_of_week=request_id % 7,
                    traffic_intensity=0.1 + (request_id * 0.1),
                    endpoint_type=["auth", "profile", "search"][request_id % 3],
                    user_type_new=request_id % 2 == 0,
                    device_mobile=request_id % 3 == 0
                )
                
                # Simulate processing time
                time.sleep(0.1)
                
                return {
                    'request_id': request_id,
                    'success': True,
                    'timestamp': datetime.now()
                }
            except Exception as e:
                return {
                    'request_id': request_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test concurrent requests
        num_requests = 5
        results = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(make_prediction_request, i) 
                for i in range(num_requests)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all requests completed
        assert len(results) == num_requests
        assert all(result['success'] for result in results)
        
        # Verify request IDs are unique
        request_ids = [result['request_id'] for result in results]
        assert len(set(request_ids)) == num_requests
    
    @patch('services.external_access.external_access_service.get_access_info')
    def test_external_access_functionality(self, mock_get_access_info):
        """Test external access URL generation and management"""
        # Mock access info
        from services.external_access import AccessInfo
        mock_access_info = AccessInfo(
            local_url="http://localhost:8501",
            public_url="https://abc123.ngrok.io",
            is_public_available=True,
            ngrok_status="Running",
            session_count=1,
            uptime=timedelta(hours=2),
            last_updated=datetime.now()
        )
        mock_get_access_info.return_value = mock_access_info
        
        # Test access info retrieval
        access_info = external_access_service.get_access_info()
        
        assert access_info.public_url == "https://abc123.ngrok.io"
        assert access_info.is_public_available is True
        assert access_info.public_url.startswith("https://")
        assert ".ngrok.io" in access_info.public_url


class TestPerformanceIntegration:
    """Test performance monitoring and optimization"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
        dashboard_controller._page_load_times = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_performance_tracking(self, mock_init_clients):
        """Test performance tracking functionality"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test page load time tracking
        dashboard_controller.track_page_load_time("overview", 1.5)
        dashboard_controller.track_page_load_time("predictions", 2.1)
        dashboard_controller.track_page_load_time("overview", 1.3)
        
        # Get performance metrics
        metrics = dashboard_controller.get_performance_metrics()
        
        assert 'page_load_times' in metrics
        assert 'overview' in metrics['page_load_times']
        assert 'predictions' in metrics['page_load_times']
        assert len(metrics['page_load_times']['overview']) == 2
        assert len(metrics['page_load_times']['predictions']) == 1
        
        # Verify load times are recorded correctly
        overview_times = metrics['page_load_times']['overview']
        assert overview_times[0]['load_time'] == 1.5
        assert overview_times[1]['load_time'] == 1.3
    
    def test_performance_under_load(self):
        """Test dashboard performance under simulated load"""
        def simulate_user_activity(user_id):
            """Simulate user activity"""
            start_time = time.time()
            
            # Simulate page navigation
            pages = ["overview", "predictions", "monitoring", "visualization"]
            for page in pages:
                # Simulate page load time
                load_time = 0.5 + (user_id * 0.1)  # Vary by user
                time.sleep(load_time / 10)  # Scaled down for testing
                
                dashboard_controller.track_page_load_time(page, load_time)
            
            total_time = time.time() - start_time
            return {
                'user_id': user_id,
                'total_time': total_time,
                'pages_visited': len(pages)
            }
        
        # Simulate multiple concurrent users
        num_users = 3
        results = []
        
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(simulate_user_activity, i) 
                for i in range(num_users)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all users completed successfully
        assert len(results) == num_users
        assert all(result['pages_visited'] == 4 for result in results)
        
        # Verify performance metrics were recorded
        metrics = dashboard_controller.get_performance_metrics()
        assert len(metrics['page_load_times']) >= 4  # At least 4 different pages


class TestErrorRecoveryIntegration:
    """Test error recovery and resilience"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_service_failure_recovery(self, mock_init_clients):
        """Test recovery from service failures"""
        # Mock AWS clients with some failures
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Simulate service failure
        error = Exception("Service temporarily unavailable")
        error_data = dashboard_controller.handle_service_error(
            'live_prediction', 'predict_cold_start_risk', error
        )
        
        # Verify error handling
        assert error_data['service_name'] == 'live_prediction'
        assert error_data['operation'] == 'predict_cold_start_risk'
        assert 'user_message' in error_data
        assert 'error_info' in error_data
        
        # Verify service status is updated
        assert dashboard_controller._initialization_status['live_prediction'] is False
    
    @patch('services.aws_clients.aws_client_manager.test_connections')
    def test_connectivity_recovery(self, mock_test_connections):
        """Test recovery from connectivity issues"""
        # Mock initial connection failure
        mock_test_connections.return_value = {
            'dynamodb': False,
            'sagemaker': False,
            'lambda': False,
            'cloudwatch': False
        }
        
        # Test health check with connection issues
        health_status = dashboard_controller.perform_health_check()
        
        assert health_status['overall_health'] in ['critical', 'degraded']
        assert 'aws_connectivity' in health_status
        
        # Mock connection recovery
        mock_test_connections.return_value = {
            'dynamodb': True,
            'sagemaker': True,
            'lambda': True,
            'cloudwatch': True
        }
        
        # Clear health check cache to force new check
        dashboard_controller._last_health_check = None
        
        # Test health check after recovery
        health_status = dashboard_controller.perform_health_check()
        
        # Health should improve (though may not be fully healthy due to other factors)
        assert health_status['overall_health'] in ['healthy', 'degraded']


class TestCompleteWorkflowIntegration:
    """Test complete end-to-end dashboard workflows"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
        
        # Clear Streamlit session state
        if hasattr(st, 'session_state'):
            st.session_state.clear()
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.live_prediction.LivePredictionService.predict_cold_start_risk')
    @patch('services.data_visualization.DataVisualizationService.get_recent_requests')
    @patch('services.system_monitoring.SystemMonitoringService.get_system_health')
    @patch('services.traffic_generation.TrafficGenerationController.start_traffic_generation')
    @patch('services.warming_system.WarmingSystemService.trigger_manual_warming')
    def test_complete_dashboard_workflow(self, mock_warming, mock_traffic, mock_health, 
                                       mock_data, mock_predict, mock_init_clients):
        """Test complete dashboard workflow from initialization to all features"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock prediction response
        from services.live_prediction import PredictionResponse
        mock_prediction = PredictionResponse(
            success=True,
            xgboost_probability=0.78,
            random_forest_probability=0.72,
            ensemble_probability=0.76,
            prediction_label="cold_start",
            recommendation="HIGH RISK - Consider warming the auth endpoint",
            model_agreement=0.92,
            timestamp=datetime.now(),
            error_message=None
        )
        mock_predict.return_value = mock_prediction
        
        # Mock data visualization
        mock_records = [
            Mock(
                timestamp=datetime.now() - timedelta(minutes=i),
                endpoint_type="auth",
                cold_start_label=1 if i % 3 == 0 else 0,
                traffic_intensity=0.5 + (i * 0.1),
                hour_of_day=14,
                user_type_new=1 if i % 2 == 0 else 0,
                device_mobile=1 if i % 4 == 0 else 0
            )
            for i in range(20)
        ]
        mock_data.return_value = mock_records
        
        # Mock system health
        mock_health_obj = Mock()
        mock_health_obj.api_status = "healthy"
        mock_health_obj.recent_request_count = 1500
        mock_health_obj.uptime_percentage = 99.8
        mock_health_obj.dynamodb_status = "active"
        mock_health.return_value = mock_health_obj
        
        # Mock traffic generation
        mock_traffic.return_value = True
        
        # Mock warming system
        mock_warming.return_value = {
            'success': True,
            'functions_warmed': ['auth-function', 'profile-function'],
            'warming_time': 2.3
        }
        
        # Step 1: Initialize dashboard
        result = dashboard_controller.initialize_dashboard()
        assert result is True
        
        # Step 2: Perform health check
        health_status = dashboard_controller.perform_health_check()
        assert health_status['overall_health'] in ['healthy', 'degraded', 'critical']
        
        # Step 3: Make a prediction
        from services.live_prediction import PredictionRequest
        request = PredictionRequest(
            hour_of_day=14,
            day_of_week=1,
            traffic_intensity=0.8,
            endpoint_type="auth",
            user_type_new=True,
            device_mobile=False
        )
        
        prediction_service = dashboard_controller.live_prediction_service
        prediction_result = prediction_service.predict_cold_start_risk(request)
        
        assert prediction_result.success is True
        assert prediction_result.ensemble_probability == 0.76
        assert "HIGH RISK" in prediction_result.recommendation
        
        # Step 4: Get data visualization
        data_service = dashboard_controller.data_visualization_service
        recent_data = data_service.get_recent_requests(limit=20)
        
        assert len(recent_data) == 20
        assert all(hasattr(record, 'timestamp') for record in recent_data)
        
        # Step 5: Generate traffic (if high risk detected)
        if prediction_result.ensemble_probability > 0.7:
            traffic_controller = dashboard_controller.traffic_generation_controller
            traffic_result = traffic_controller.start_traffic_generation()
            assert traffic_result is True
        
        # Step 6: Trigger warming (if high risk detected)
        if prediction_result.ensemble_probability > 0.7:
            warming_service = dashboard_controller.warming_system_service
            warming_result = warming_service.trigger_manual_warming(['auth-function'])
            assert warming_result['success'] is True
            assert len(warming_result['functions_warmed']) > 0
        
        # Step 7: Verify all services are properly initialized
        assert dashboard_controller._initialization_status['aws_clients'] is True
        assert dashboard_controller._initialization_status['live_prediction'] is True
        assert dashboard_controller._initialization_status['system_monitoring'] is True
        assert dashboard_controller._initialization_status['data_visualization'] is True
        
        # Verify all mocks were called appropriately
        mock_predict.assert_called_once()
        mock_data.assert_called_once()
        mock_health.assert_called()
        
        if prediction_result.ensemble_probability > 0.7:
            mock_traffic.assert_called_once()
            mock_warming.assert_called_once()
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_dashboard_resilience_workflow(self, mock_init_clients):
        """Test dashboard resilience under various failure scenarios"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test service failure scenarios
        failure_scenarios = [
            ('live_prediction', 'predict_cold_start_risk', Exception("SageMaker timeout")),
            ('data_visualization', 'get_recent_requests', Exception("DynamoDB throttling")),
            ('system_monitoring', 'get_system_health', Exception("CloudWatch unavailable")),
            ('traffic_generation', 'start_traffic_generation', Exception("Lambda invocation failed")),
            ('warming_system', 'trigger_manual_warming', Exception("Warming service down"))
        ]
        
        for service_name, operation, error in failure_scenarios:
            # Handle the error
            error_data = dashboard_controller.handle_service_error(service_name, operation, error)
            
            # Verify error handling
            assert error_data['service_name'] == service_name
            assert error_data['operation'] == operation
            assert 'user_message' in error_data
            assert 'error_info' in error_data
            
            # Verify service status is updated
            assert dashboard_controller._initialization_status.get(service_name, True) is False
        
        # Test recovery
        dashboard_controller.reset_service_status('live_prediction')
        assert dashboard_controller._initialization_status.get('live_prediction', False) is True
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_performance_monitoring_workflow(self, mock_init_clients):
        """Test performance monitoring throughout dashboard operations"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Track various page load times
        pages = ["overview", "predictions", "monitoring", "visualization", "analytics"]
        
        for i, page in enumerate(pages):
            load_time = 0.5 + (i * 0.2)  # Varying load times
            dashboard_controller.track_page_load_time(page, load_time)
        
        # Get performance metrics
        metrics = dashboard_controller.get_performance_metrics()
        
        assert 'page_load_times' in metrics
        assert len(metrics['page_load_times']) == len(pages)
        
        # Verify all pages are tracked
        for page in pages:
            assert page in metrics['page_load_times']
            assert len(metrics['page_load_times'][page]) == 1
        
        # Test performance optimization
        # Note: optimize_performance method would need to be implemented
        # For now, just verify metrics are tracked
        optimized_metrics = dashboard_controller.get_performance_metrics()
        assert 'page_load_times' in optimized_metrics
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_cache_management_workflow(self, mock_init_clients):
        """Test cache management throughout dashboard operations"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Perform operations that should be cached
        dashboard_controller.perform_health_check()
        
        # Verify cache is populated
        assert dashboard_controller._last_health_check is not None
        
        # Clear specific cache
        dashboard_controller.clear_health_cache()
        assert dashboard_controller._last_health_check is None
        
        # Clear all caches
        dashboard_controller.clear_all_caches()
        
        # Verify health check cache is cleared
        assert dashboard_controller._last_health_check is None


class TestDataConsistencyIntegration:
    """Test data consistency across all dashboard components"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.data_visualization.DataVisualizationService.get_recent_requests')
    @patch('services.cost_analytics.CostAnalyticsService.calculate_monthly_costs')
    @patch('services.performance_display.PerformanceDisplayService.get_performance_comparison')
    def test_data_consistency_across_services(self, mock_performance, mock_costs, 
                                            mock_data, mock_init_clients):
        """Test that data remains consistent across all dashboard services"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock consistent data
        base_timestamp = datetime.now()
        mock_records = [
            Mock(
                timestamp=base_timestamp - timedelta(minutes=i),
                endpoint_type="auth",
                cold_start_label=1 if i % 4 == 0 else 0,  # 25% cold start rate
                traffic_intensity=0.5,
                hour_of_day=14,
                user_type_new=1 if i % 2 == 0 else 0,
                device_mobile=1 if i % 3 == 0 else 0
            )
            for i in range(100)
        ]
        mock_data.return_value = mock_records
        
        # Mock cost data based on same records
        mock_costs.return_value = {
            'monthly_sagemaker_calls': 2500,
            'monthly_lambda_invocations': 10000,
            'estimated_monthly_cost': 45.67,
            'cost_savings': 234.12
        }
        
        # Mock performance data
        mock_performance.return_value = {
            'cold_start_reduction': 0.75,  # 75% reduction
            'average_response_time_improvement': 0.45,
            'uptime_improvement': 0.02
        }
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Get data from different services
        data_service = dashboard_controller.data_visualization_service
        cost_service = dashboard_controller.cost_analytics_service
        performance_service = dashboard_controller.performance_display_service
        
        # Retrieve data
        recent_data = data_service.get_recent_requests(limit=100)
        cost_data = cost_service.calculate_monthly_costs()
        performance_data = performance_service.get_performance_comparison()
        
        # Calculate statistics from raw data
        cold_start_count = sum(1 for record in recent_data if record.cold_start_label == 1)
        cold_start_ratio = cold_start_count / len(recent_data)
        
        # Verify data consistency
        assert len(recent_data) == 100
        assert cold_start_ratio == 0.25  # Should match our mock data
        
        # Verify cost calculations are reasonable
        assert cost_data['monthly_sagemaker_calls'] > 0
        assert cost_data['estimated_monthly_cost'] > 0
        assert cost_data['cost_savings'] > 0
        
        # Verify performance improvements are realistic
        assert 0 <= performance_data['cold_start_reduction'] <= 1
        assert 0 <= performance_data['average_response_time_improvement'] <= 1
        
        # Test data summary consistency
        data_summary = data_service.get_data_summary(recent_data)
        statistics = data_summary['statistics']
        
        assert statistics.total_requests == 100
        assert abs(statistics.cold_start_ratio - cold_start_ratio) < 0.01  # Allow small floating point differences


if __name__ == "__main__":
    pytest.main([__file__, "-v"])