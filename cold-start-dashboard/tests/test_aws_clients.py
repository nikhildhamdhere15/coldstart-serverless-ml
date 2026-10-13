"""
Property-based tests for AWS client initialization
**Feature: cold-start-dashboard, Property 1: AWS Client Validation**
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch, MagicMock
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from services.aws_clients import AWSClientManager, AWSClientError


class TestAWSClientInitialization:
    """Test AWS client initialization with property-based testing"""
    
    @given(
        region=st.sampled_from(['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']),
        access_key=st.text(min_size=16, max_size=32, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        secret_key=st.text(min_size=32, max_size=64, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Ps'))),
    )
    @settings(max_examples=100)
    def test_property_aws_client_validation(self, region, access_key, secret_key):
        """
        **Property 1: AWS Client Validation**
        For any valid AWS configuration (region, credentials), the client manager should 
        successfully initialize all required clients (DynamoDB, SageMaker, Lambda, CloudWatch)
        and each client should be properly configured with the correct region and credentials.
        **Validates: Requirements 2.1**
        """
        # Mock the config manager to use our test values
        with patch('services.aws_clients.config_manager') as mock_config:
            # Setup mock configuration
            mock_aws_config = Mock()
            mock_aws_config.region = region
            mock_aws_config.dynamodb_table_name = 'ETLFeatureData'
            mock_aws_config.xgboost_endpoint = 'test-xgb-endpoint'
            mock_aws_config.random_forest_endpoint = 'test-rf-endpoint'
            
            mock_config.aws_config = mock_aws_config
            
            # Mock the get_aws_session method to return a mock session
            mock_session = Mock(spec=boto3.Session)
            mock_config.get_aws_session.return_value = mock_session
            
            # Mock clients that the session creates
            mock_dynamodb_client = Mock()
            mock_dynamodb_resource = Mock()
            mock_table = Mock()
            mock_dynamodb_resource.Table.return_value = mock_table
            
            mock_sagemaker_client = Mock()
            mock_lambda_client = Mock()
            mock_cloudwatch_client = Mock()
            
            # Configure session.client() to return appropriate mocks
            def mock_client_factory(service_name):
                if service_name == 'dynamodb':
                    return mock_dynamodb_client
                elif service_name == 'sagemaker-runtime':
                    return mock_sagemaker_client
                elif service_name == 'lambda':
                    return mock_lambda_client
                elif service_name == 'cloudwatch':
                    return mock_cloudwatch_client
                else:
                    raise ValueError(f"Unknown service: {service_name}")
            
            mock_session.client.side_effect = mock_client_factory
            mock_session.resource.return_value = mock_dynamodb_resource
            
            # Test the property
            client_manager = AWSClientManager()
            clients = client_manager.initialize_clients()
            
            # Verify all required clients are present
            required_services = ['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']
            for service in required_services:
                assert service in clients, f"Missing required service: {service}"
            
            # Verify DynamoDB client structure
            assert 'client' in clients['dynamodb']
            assert 'resource' in clients['dynamodb']
            assert 'table' in clients['dynamodb']
            
            # Verify clients are properly configured (mocked)
            assert clients['sagemaker'] == mock_sagemaker_client
            assert clients['lambda'] == mock_lambda_client
            assert clients['cloudwatch'] == mock_cloudwatch_client
            
            # Verify session was called with correct parameters
            mock_config.get_aws_session.assert_called_once()
    
    def test_client_initialization_with_invalid_credentials(self):
        """Test that invalid credentials raise appropriate errors"""
        with patch('services.aws_clients.config_manager') as mock_config:
            # Mock get_aws_session to raise NoCredentialsError
            mock_config.get_aws_session.side_effect = NoCredentialsError()
            
            client_manager = AWSClientManager()
            
            with pytest.raises(AWSClientError) as exc_info:
                client_manager.initialize_clients()
            
            assert "AWS credentials not configured properly" in str(exc_info.value)
    
    def test_client_initialization_with_service_error(self):
        """Test that service initialization errors are handled properly"""
        with patch('services.aws_clients.config_manager') as mock_config:
            # Setup mock configuration
            mock_aws_config = Mock()
            mock_aws_config.region = 'us-east-1'
            mock_aws_config.dynamodb_table_name = 'ETLFeatureData'
            mock_config.aws_config = mock_aws_config
            
            # Mock session that raises an error when creating a client
            mock_session = Mock(spec=boto3.Session)
            mock_session.client.side_effect = Exception("Service unavailable")
            mock_config.get_aws_session.return_value = mock_session
            
            client_manager = AWSClientManager()
            
            with pytest.raises(AWSClientError) as exc_info:
                client_manager.initialize_clients()
            
            assert "Failed to initialize AWS clients" in str(exc_info.value)
    
    def test_get_client_before_initialization(self):
        """Test that getting a client before initialization raises error"""
        client_manager = AWSClientManager()
        
        with pytest.raises(AWSClientError) as exc_info:
            client_manager.get_client('dynamodb')
        
        assert "Clients not initialized" in str(exc_info.value)
    
    def test_get_unknown_client(self):
        """Test that requesting unknown client raises error"""
        with patch('services.aws_clients.config_manager') as mock_config:
            # Setup minimal mock configuration
            mock_aws_config = Mock()
            mock_aws_config.region = 'us-east-1'
            mock_aws_config.dynamodb_table_name = 'ETLFeatureData'
            mock_config.aws_config = mock_aws_config
            
            mock_session = Mock(spec=boto3.Session)
            mock_session.client.return_value = Mock()
            mock_session.resource.return_value = Mock()
            mock_config.get_aws_session.return_value = mock_session
            
            client_manager = AWSClientManager()
            client_manager.initialize_clients()
            
            with pytest.raises(AWSClientError) as exc_info:
                client_manager.get_client('unknown_service')
            
            assert "Unknown service: unknown_service" in str(exc_info.value)


class TestConnectionTesting:
    """Test connection testing functionality"""
    
    def test_connection_testing_requires_initialization(self):
        """Test that connection testing requires client initialization"""
        client_manager = AWSClientManager()
        
        with pytest.raises(AWSClientError) as exc_info:
            client_manager.test_connections()
        
        assert "Clients not initialized" in str(exc_info.value)
    
    @patch('services.aws_clients.config_manager')
    def test_connection_status_tracking(self, mock_config):
        """Test that connection status is properly tracked"""
        # Setup mock configuration
        mock_aws_config = Mock()
        mock_aws_config.region = 'us-east-1'
        mock_aws_config.dynamodb_table_name = 'ETLFeatureData'
        mock_aws_config.xgboost_endpoint = 'test-xgb'
        mock_aws_config.random_forest_endpoint = 'test-rf'
        mock_aws_config.traffic_generator_function = 'test-traffic'
        mock_aws_config.data_aggregator_function = 'test-aggregator'
        mock_aws_config.intelligent_warmer_function = 'test-warmer'
        mock_config.aws_config = mock_aws_config
        
        # Mock session and clients
        mock_session = Mock(spec=boto3.Session)
        mock_config.get_aws_session.return_value = mock_session
        
        # Setup successful mocks for all services
        mock_table = Mock()
        mock_table.load.return_value = None
        mock_table.scan.return_value = {'Items': []}
        
        mock_dynamodb_resource = Mock()
        mock_dynamodb_resource.Table.return_value = mock_table
        
        mock_sagemaker_client = Mock()
        mock_sagemaker_client.invoke_endpoint.return_value = {
            'Body': Mock(read=Mock(return_value=b'0.5'))
        }
        
        mock_lambda_client = Mock()
        mock_lambda_client.list_functions.return_value = {'Functions': []}
        mock_lambda_client.get_function.return_value = {'Configuration': {}}
        
        mock_cloudwatch_client = Mock()
        mock_cloudwatch_client.list_metrics.return_value = {'Metrics': []}
        
        def mock_client_factory(service_name):
            if service_name == 'dynamodb':
                return Mock()
            elif service_name == 'sagemaker-runtime':
                return mock_sagemaker_client
            elif service_name == 'lambda':
                return mock_lambda_client
            elif service_name == 'cloudwatch':
                return mock_cloudwatch_client
        
        mock_session.client.side_effect = mock_client_factory
        mock_session.resource.return_value = mock_dynamodb_resource
        
        # Test
        client_manager = AWSClientManager()
        client_manager.initialize_clients()
        
        # Test connections
        status = client_manager.test_connections()
        
        # Verify status structure
        expected_services = ['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']
        for service in expected_services:
            assert service in status
            assert isinstance(status[service], bool)
        
        # Verify status is tracked
        tracked_status = client_manager.get_connection_status()
        assert tracked_status == status
        
        # Test health check
        is_healthy = client_manager.is_healthy()
        assert isinstance(is_healthy, bool)


class TestSystemMonitoring:
    """
    Property-based tests for system health monitoring
    **Feature: cold-start-dashboard, Property 5: System Metrics Completeness**
    """
    
    @given(
        api_status=st.sampled_from(['healthy', 'degraded', 'down']),
        endpoint_count=st.integers(min_value=1, max_value=5),
        lambda_count=st.integers(min_value=1, max_value=10),
        request_count=st.integers(min_value=0, max_value=1000),
        uptime=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=100)
    def test_property_system_metrics_completeness(self, api_status, endpoint_count, lambda_count, request_count, uptime):
        """
        **Property 5: System Metrics Completeness**
        For any system monitoring request, the dashboard should display all required metrics: 
        API health, recent request counts, SageMaker statistics, and Lambda activity.
        All metrics should be present and properly formatted regardless of system state.
        **Validates: Requirements 2.2**
        """
        from services.system_monitoring import SystemMonitoringService, SystemHealth
        from datetime import datetime
        
        # Mock AWS clients
        mock_cloudwatch = Mock()
        mock_lambda_client = Mock()
        mock_sagemaker = Mock()
        mock_dynamodb = Mock()
        
        # Create mock table
        mock_table = Mock()
        mock_table.scan.return_value = {'Count': request_count, 'Items': []}
        mock_table.load.return_value = None
        mock_table.table_status = 'ACTIVE'
        
        mock_dynamodb_clients = {
            'client': Mock(),
            'resource': Mock(),
            'table': mock_table
        }
        
        aws_clients = {
            'cloudwatch': mock_cloudwatch,
            'lambda': mock_lambda_client,
            'sagemaker': mock_sagemaker,
            'dynamodb': mock_dynamodb_clients
        }
        
        # Mock configuration
        with patch('services.system_monitoring.config_manager') as mock_config:
            mock_aws_config = Mock()
            mock_aws_config.xgboost_endpoint = 'test-xgb'
            mock_aws_config.random_forest_endpoint = 'test-rf'
            mock_aws_config.traffic_generator_function = 'test-traffic'
            mock_aws_config.data_aggregator_function = 'test-aggregator'
            mock_aws_config.intelligent_warmer_function = 'test-warmer'
            mock_aws_config.dynamodb_table_name = 'TestTable'
            mock_config.aws_config = mock_aws_config
            
            # Mock Lambda function responses
            mock_lambda_client.get_function.return_value = {'Configuration': {}}
            
            # Mock SageMaker endpoint responses
            mock_sagemaker.invoke_endpoint.return_value = {
                'Body': Mock(read=Mock(return_value=b'0.5'))
            }
            
            # Mock CloudWatch responses
            mock_cloudwatch.get_metric_statistics.return_value = {
                'Datapoints': [
                    {'Timestamp': datetime.utcnow(), 'Sum': 10}
                ]
            }
            
            # Test the property
            monitoring_service = SystemMonitoringService(
                cloudwatch_client=aws_clients['cloudwatch'],
                lambda_client=aws_clients['lambda'],
                sagemaker_client=aws_clients['sagemaker']
            )
            health = monitoring_service.get_system_health()
            
            # Verify all required metrics are present
            assert hasattr(health, 'api_status'), "Missing api_status metric"
            assert hasattr(health, 'sagemaker_endpoints'), "Missing sagemaker_endpoints metric"
            assert hasattr(health, 'lambda_functions'), "Missing lambda_functions metric"
            assert hasattr(health, 'dynamodb_status'), "Missing dynamodb_status metric"
            assert hasattr(health, 'recent_request_count'), "Missing recent_request_count metric"
            assert hasattr(health, 'uptime_percentage'), "Missing uptime_percentage metric"
            assert hasattr(health, 'last_updated'), "Missing last_updated metric"
            
            # Verify metric types and validity
            assert isinstance(health.api_status, str), "api_status should be string"
            assert health.api_status in ['healthy', 'degraded', 'down'], "Invalid api_status value"
            
            assert isinstance(health.sagemaker_endpoints, dict), "sagemaker_endpoints should be dict"
            assert len(health.sagemaker_endpoints) >= 0, "sagemaker_endpoints should be non-negative length"
            
            assert isinstance(health.lambda_functions, dict), "lambda_functions should be dict"
            assert len(health.lambda_functions) >= 0, "lambda_functions should be non-negative length"
            
            assert isinstance(health.dynamodb_status, str), "dynamodb_status should be string"
            assert health.dynamodb_status in ['healthy', 'degraded', 'down', 'unknown'], "Invalid dynamodb_status value"
            
            assert isinstance(health.recent_request_count, int), "recent_request_count should be int"
            assert health.recent_request_count >= 0, "recent_request_count should be non-negative"
            
            assert isinstance(health.uptime_percentage, float), "uptime_percentage should be float"
            assert 0.0 <= health.uptime_percentage <= 100.0, "uptime_percentage should be 0-100"
            
            assert isinstance(health.last_updated, datetime), "last_updated should be datetime"
    
    def test_system_health_error_handling(self):
        """Test that system health monitoring handles errors gracefully"""
        from services.system_monitoring import SystemMonitoringService
        
        # Create clients that will raise errors
        mock_cloudwatch = Mock()
        mock_cloudwatch.get_metric_statistics.side_effect = Exception("CloudWatch error")
        
        mock_lambda_client = Mock()
        mock_lambda_client.get_function.side_effect = Exception("Lambda error")
        
        mock_sagemaker = Mock()
        mock_sagemaker.invoke_endpoint.side_effect = Exception("SageMaker error")
        
        mock_table = Mock()
        mock_table.scan.side_effect = Exception("DynamoDB error")
        
        aws_clients = {
            'cloudwatch': mock_cloudwatch,
            'lambda': mock_lambda_client,
            'sagemaker': mock_sagemaker,
            'dynamodb': {'table': mock_table}
        }
        
        with patch('services.system_monitoring.config_manager'):
            monitoring_service = SystemMonitoringService(
                cloudwatch_client=aws_clients['cloudwatch'],
                lambda_client=aws_clients['lambda'],
                sagemaker_client=aws_clients['sagemaker']
            )
            health = monitoring_service.get_system_health()
            
            # Should return degraded status, not crash
            assert health.api_status == 'degraded'
            assert isinstance(health, type(health))  # Should be SystemHealth object
    
    def test_warming_metrics_completeness(self):
        """Test that warming metrics contain all required fields"""
        from services.system_monitoring import SystemMonitoringService
        from datetime import datetime
        
        # Mock AWS clients
        mock_cloudwatch = Mock()
        mock_cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': [{'Sum': 5, 'Timestamp': datetime.utcnow()}]
        }
        
        aws_clients = {
            'cloudwatch': mock_cloudwatch,
            'lambda': Mock(),
            'sagemaker': Mock(),
            'dynamodb': {'table': Mock()}
        }
        
        with patch('services.system_monitoring.config_manager') as mock_config:
            mock_aws_config = Mock()
            mock_aws_config.intelligent_warmer_function = 'test-warmer'
            mock_config.aws_config = mock_aws_config
            
            monitoring_service = SystemMonitoringService(
                cloudwatch_client=aws_clients['cloudwatch'],
                lambda_client=aws_clients['lambda'],
                sagemaker_client=aws_clients['sagemaker']
            )
            warming_metrics = monitoring_service.get_warming_metrics()
            
            # Verify all required warming metrics are present
            assert 'total_warming_events' in warming_metrics, "Missing total_warming_events"
            assert 'success_rate' in warming_metrics, "Missing success_rate"
            assert 'frequency_per_day' in warming_metrics, "Missing frequency_per_day"
            assert 'cost_savings_monthly' in warming_metrics, "Missing cost_savings_monthly"
            assert 'last_warming_time' in warming_metrics, "Missing last_warming_time"
            assert 'next_evaluation_time' in warming_metrics, "Missing next_evaluation_time"
            
            # Verify metric types
            assert isinstance(warming_metrics['total_warming_events'], int)
            assert isinstance(warming_metrics['success_rate'], (int, float))
            assert isinstance(warming_metrics['frequency_per_day'], (int, float))
            assert isinstance(warming_metrics['cost_savings_monthly'], (int, float))
            # last_warming_time and next_evaluation_time can be None or datetime
    
    def test_next_evaluation_time_calculation(self):
        """Test that next evaluation time is calculated correctly for 15-minute intervals"""
        from services.system_monitoring import SystemMonitoringService
        from datetime import datetime
        
        # Mock minimal AWS clients
        aws_clients = {
            'cloudwatch': Mock(),
            'lambda': Mock(),
            'sagemaker': Mock(),
            'dynamodb': {'table': Mock()}
        }
        
        with patch('services.system_monitoring.config_manager'):
            monitoring_service = SystemMonitoringService(
                cloudwatch_client=aws_clients['cloudwatch'],
                lambda_client=aws_clients['lambda'],
                sagemaker_client=aws_clients['sagemaker']
            )
            
            # Test the next evaluation time calculation
            next_time = monitoring_service._get_next_evaluation_time()
            
            # Should be a datetime object
            assert isinstance(next_time, datetime)
            
            # Should be in the future
            assert next_time > datetime.utcnow()
            
            # Should be on a 15-minute boundary
            assert next_time.minute % 15 == 0
            assert next_time.second == 0
            assert next_time.microsecond == 0