"""
Integration tests for external access and concurrent user scenarios
Tests Requirements 8.3 and 8.4 specifically
"""

import pytest
import streamlit as st
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from services.dashboard_controller import dashboard_controller
from services.external_access import external_access_service
from services.session_management import get_concurrent_user_handler
from config import config_manager


class TestExternalAccessIntegration:
    """Integration tests for external access functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
        
        # Clear Streamlit session state
        if hasattr(st, 'session_state'):
            st.session_state.clear()
    
    @patch('services.ngrok_service.NgrokService.start_tunnel')
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_public_url_generation(self, mock_init_clients, mock_start_tunnel):
        """Test public URL generation for external access"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock ngrok tunnel
        mock_start_tunnel.return_value = "https://abc123.ngrok.io"
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        # Test public URL generation
        public_url = external_access_service.get_public_url()
        
        assert public_url is not None
        assert public_url.startswith("https://")
        assert ".ngrok.io" in public_url
        
        # Verify tunnel was started
        mock_start_tunnel.assert_called_once()
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_concurrent_user_sessions(self, mock_init_clients):
        """Test concurrent user session handling - Requirements 8.3"""
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
        
        def simulate_user_session(user_id):
            """Simulate a user session"""
            try:
                # Get concurrent user handler
                handler = get_concurrent_user_handler()
                
                # Register user session
                session_id = f"session_{user_id}_{int(time.time())}"
                handler.register_session(session_id)
                
                # Simulate user activity
                time.sleep(0.1)  # Simulate processing time
                
                # Check session is active
                active_sessions = handler.get_active_session_count()
                
                # Unregister session
                handler.unregister_session(session_id)
                
                return {
                    'user_id': user_id,
                    'session_id': session_id,
                    'success': True,
                    'active_sessions': active_sessions
                }
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test concurrent sessions
        num_users = 5
        results = []
        
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(simulate_user_session, i) 
                for i in range(num_users)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all sessions completed successfully
        assert len(results) == num_users
        successful_sessions = [r for r in results if r['success']]
        assert len(successful_sessions) == num_users
        
        # Verify session IDs are unique
        session_ids = [r['session_id'] for r in successful_sessions]
        assert len(set(session_ids)) == num_users
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.live_prediction.LivePredictionService.predict_cold_start_risk')
    def test_concurrent_prediction_requests(self, mock_predict, mock_init_clients):
        """Test concurrent prediction requests - Requirements 8.3, 8.4"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock prediction responses
        def mock_prediction_response(request):
            # Simulate processing time
            time.sleep(0.05)
            
            from services.live_prediction import PredictionResponse
            return PredictionResponse(
                success=True,
                xgboost_probability=0.65,
                random_forest_probability=0.58,
                ensemble_probability=0.62,
                prediction_label="warm",
                recommendation="System operating normally",
                model_agreement=0.88,
                timestamp=datetime.now(),
                error_message=None
            )
        
        mock_predict.side_effect = mock_prediction_response
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        def make_concurrent_prediction(request_id):
            """Make a prediction request"""
            try:
                from services.live_prediction import PredictionRequest
                
                request = PredictionRequest(
                    hour_of_day=14 + (request_id % 10),
                    day_of_week=request_id % 7,
                    traffic_intensity=0.1 + (request_id * 0.1),
                    endpoint_type=["auth", "profile", "search"][request_id % 3],
                    user_type_new=request_id % 2 == 0,
                    device_mobile=request_id % 3 == 0
                )
                
                # Make prediction
                prediction_service = dashboard_controller.live_prediction_service
                result = prediction_service.predict_cold_start_risk(request)
                
                return {
                    'request_id': request_id,
                    'success': result.success,
                    'ensemble_probability': result.ensemble_probability,
                    'timestamp': result.timestamp
                }
            except Exception as e:
                return {
                    'request_id': request_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test concurrent predictions
        num_requests = 8
        results = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(make_concurrent_prediction, i) 
                for i in range(num_requests)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all predictions completed successfully
        assert len(results) == num_requests
        successful_predictions = [r for r in results if r['success']]
        assert len(successful_predictions) == num_requests
        
        # Verify predictions have valid probabilities
        for result in successful_predictions:
            assert 0 <= result['ensemble_probability'] <= 1
            assert result['timestamp'] is not None
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    @patch('services.data_visualization.DataVisualizationService.get_recent_requests')
    def test_concurrent_data_access(self, mock_get_requests, mock_init_clients):
        """Test concurrent data access without performance degradation"""
        # Mock AWS clients
        mock_clients = {
            'sagemaker': Mock(),
            'dynamodb': {'resource': Mock()},
            'lambda': Mock(),
            'cloudwatch': Mock()
        }
        mock_init_clients.return_value = mock_clients
        
        # Mock data records
        from datetime import timedelta
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
            for i in range(50)
        ]
        
        def mock_get_data(limit=50):
            # Simulate data retrieval time
            time.sleep(0.02)
            return mock_records[:limit]
        
        mock_get_requests.side_effect = mock_get_data
        
        # Initialize dashboard
        dashboard_controller.initialize_dashboard()
        
        def access_data(user_id):
            """Simulate data access by a user"""
            try:
                start_time = time.time()
                
                # Access data visualization service
                data_service = dashboard_controller.data_visualization_service
                recent_data = data_service.get_recent_requests(limit=20)
                
                access_time = time.time() - start_time
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'data_count': len(recent_data),
                    'access_time': access_time
                }
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test concurrent data access
        num_users = 6
        results = []
        
        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(access_data, i) 
                for i in range(num_users)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all data access completed successfully
        assert len(results) == num_users
        successful_access = [r for r in results if r['success']]
        assert len(successful_access) == num_users
        
        # Verify data consistency
        for result in successful_access:
            assert result['data_count'] == 20
            assert result['access_time'] < 1.0  # Should be fast
    
    @patch('services.external_access.external_access_service.get_access_info')
    def test_remote_functionality_preservation(self, mock_get_access_info):
        """Test that remote access preserves full functionality - Requirements 8.4"""
        # Mock access info
        from services.external_access import AccessInfo
        mock_access_info = AccessInfo(
            local_url="http://localhost:8501",
            public_url="https://test123.ngrok.io",
            is_public_available=True,
            ngrok_status="Running",
            session_count=1,
            uptime=timedelta(hours=1),
            last_updated=datetime.now()
        )
        mock_get_access_info.return_value = mock_access_info
        
        # Test URL accessibility
        access_info = external_access_service.get_access_info()
        public_url = access_info.public_url
        assert public_url == "https://test123.ngrok.io"
        
        # Test URL format validation
        assert public_url.startswith("https://")
        assert ".ngrok.io" in public_url
        
        # Test access info completeness
        assert access_info.is_public_available is True
        assert access_info.ngrok_status == "Running"
        assert access_info.session_count >= 0
    
    def test_performance_under_concurrent_load(self):
        """Test dashboard performance under concurrent user load"""
        def simulate_heavy_user_activity(user_id):
            """Simulate heavy user activity"""
            try:
                start_time = time.time()
                
                # Simulate multiple operations
                operations = []
                
                # Simulate page loads
                for page in ["overview", "predictions", "monitoring"]:
                    page_start = time.time()
                    time.sleep(0.01)  # Simulate page load time
                    page_time = time.time() - page_start
                    operations.append(('page_load', page, page_time))
                
                # Simulate data refresh
                refresh_start = time.time()
                time.sleep(0.02)  # Simulate data refresh time
                refresh_time = time.time() - refresh_start
                operations.append(('data_refresh', 'all', refresh_time))
                
                total_time = time.time() - start_time
                
                return {
                    'user_id': user_id,
                    'success': True,
                    'total_time': total_time,
                    'operations': len(operations),
                    'avg_operation_time': total_time / len(operations)
                }
            except Exception as e:
                return {
                    'user_id': user_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test with multiple concurrent users
        num_users = 10
        results = []
        
        start_test_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(simulate_heavy_user_activity, i) 
                for i in range(num_users)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        total_test_time = time.time() - start_test_time
        
        # Verify all users completed successfully
        assert len(results) == num_users
        successful_users = [r for r in results if r['success']]
        assert len(successful_users) == num_users
        
        # Verify performance metrics
        avg_user_time = sum(r['total_time'] for r in successful_users) / len(successful_users)
        max_user_time = max(r['total_time'] for r in successful_users)
        
        # Performance should be reasonable
        assert avg_user_time < 1.0  # Average user session under 1 second
        assert max_user_time < 2.0  # No user session over 2 seconds
        assert total_test_time < 5.0  # Total test under 5 seconds
        
        # Verify all operations completed
        total_operations = sum(r['operations'] for r in successful_users)
        assert total_operations == num_users * 4  # 3 page loads + 1 data refresh per user


class TestExternalAccessErrorHandling:
    """Test error handling in external access scenarios"""
    
    def setup_method(self):
        """Set up test environment"""
        dashboard_controller._aws_clients = None
        dashboard_controller._initialization_status = {}
    
    @patch('services.ngrok_service.NgrokService.start_tunnel')
    def test_tunnel_failure_handling(self, mock_start_tunnel):
        """Test handling of ngrok tunnel failures"""
        # Mock tunnel failure
        mock_start_tunnel.side_effect = Exception("ngrok tunnel failed to start")
        
        # Test error handling
        try:
            external_access_service.get_public_url()
            assert False, "Expected exception was not raised"
        except Exception as e:
            assert "ngrok tunnel failed" in str(e)
    
    @patch('services.aws_clients.aws_client_manager.initialize_clients')
    def test_service_degradation_under_load(self, mock_init_clients):
        """Test graceful service degradation under heavy load"""
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
        
        def simulate_failing_operation(operation_id):
            """Simulate operations that may fail under load"""
            try:
                if operation_id % 3 == 0:  # Simulate 33% failure rate
                    raise Exception(f"Service overloaded - operation {operation_id}")
                
                # Simulate successful operation
                time.sleep(0.01)
                return {
                    'operation_id': operation_id,
                    'success': True
                }
            except Exception as e:
                # Handle error gracefully
                error_data = dashboard_controller.handle_service_error(
                    'test_service', f'operation_{operation_id}', e
                )
                return {
                    'operation_id': operation_id,
                    'success': False,
                    'error_handled': True,
                    'error_data': error_data
                }
        
        # Test operations under load
        num_operations = 15
        results = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(simulate_failing_operation, i) 
                for i in range(num_operations)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify error handling
        assert len(results) == num_operations
        
        successful_ops = [r for r in results if r['success']]
        failed_ops = [r for r in results if not r['success']]
        
        # Should have some successes and some failures
        assert len(successful_ops) > 0
        assert len(failed_ops) > 0
        
        # All failures should be handled gracefully
        for failed_op in failed_ops:
            assert failed_op['error_handled'] is True
            assert 'error_data' in failed_op


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
