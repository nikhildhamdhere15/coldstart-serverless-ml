"""
AWS Client Initialization Module
Handles initialization and management of AWS service clients with proper error handling
"""

import boto3
import logging
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from config import config_manager
from services.error_handling import error_handler

# Configure logging
logger = logging.getLogger(__name__)

class AWSClientError(Exception):
    """Custom exception for AWS client initialization errors"""
    pass

class AWSClientManager:
    """
    Manages AWS service clients with proper initialization, error handling, and connection testing
    """
    
    def __init__(self):
        """Initialize the AWS client manager"""
        self._session = None
        self._clients = {}
        self._connection_status = {}
        
    def initialize_clients(self) -> Dict[str, Any]:
        """
        Initialize all required AWS service clients with comprehensive error handling
        
        Returns:
            Dict containing initialized clients
            
        Raises:
            AWSClientError: If client initialization fails
        """
        def _init_clients():
            # Create AWS session
            self._session = config_manager.get_aws_session()
            
            # Initialize clients
            return {
                'dynamodb': self._create_dynamodb_client(),
                'sagemaker': self._create_sagemaker_client(),
                'lambda': self._create_lambda_client(),
                'cloudwatch': self._create_cloudwatch_client()
            }
        
        try:
            # Use error handler with retry logic
            clients, error_info = error_handler.retry_with_backoff(
                _init_clients, 'aws_clients'
            )
            
            if error_info:
                # Initialization failed after retries
                error_msg = f"Failed to initialize AWS clients after retries: {error_info.message}"
                logger.error(error_msg)
                raise AWSClientError(error_msg)
            
            self._clients = clients
            logger.info("Successfully initialized all AWS clients")
            
            # Cache successful initialization
            error_handler.cache_successful_data('clients', 'aws_clients', clients)
            
            return self._clients
            
        except Exception as e:
            # Handle any unexpected errors
            error_info = error_handler.handle_aws_error(e, 'aws_clients', 'initialize_clients')
            error_msg = f"AWS client initialization failed: {error_info.message}"
            logger.error(error_msg)
            raise AWSClientError(error_msg)
    
    def _create_dynamodb_client(self):
        """Create DynamoDB client and resource"""
        try:
            client = self._session.client('dynamodb')
            resource = self._session.resource('dynamodb')
            
            return {
                'client': client,
                'resource': resource,
                'table': resource.Table(config_manager.aws_config.dynamodb_table_name)
            }
        except Exception as e:
            logger.error(f"Failed to create DynamoDB client: {str(e)}")
            raise
    
    def _create_sagemaker_client(self):
        """Create SageMaker runtime client"""
        try:
            return self._session.client('sagemaker-runtime')
        except Exception as e:
            logger.error(f"Failed to create SageMaker client: {str(e)}")
            raise
    
    def _create_lambda_client(self):
        """Create Lambda client"""
        try:
            return self._session.client('lambda')
        except Exception as e:
            logger.error(f"Failed to create Lambda client: {str(e)}")
            raise
    
    def _create_cloudwatch_client(self):
        """Create CloudWatch client"""
        try:
            return self._session.client('cloudwatch')
        except Exception as e:
            logger.error(f"Failed to create CloudWatch client: {str(e)}")
            raise
    
    def test_connections(self) -> Dict[str, bool]:
        """
        Test connections to all AWS services with enhanced error handling
        
        Returns:
            Dict with service names as keys and connection status as values
        """
        if not self._clients:
            raise AWSClientError("Clients not initialized. Call initialize_clients() first.")
        
        # Test each service with error handling
        test_results = {}
        
        for service_name in ['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']:
            test_method = getattr(self, f'_test_{service_name}_connection')
            
            try:
                # Use retry logic for connection tests
                result, error_info = error_handler.retry_with_backoff(
                    test_method, service_name
                )
                
                if error_info:
                    test_results[service_name] = False
                    logger.warning(f"{service_name} connection test failed: {error_info.message}")
                else:
                    test_results[service_name] = result
                    if result:
                        # Cache successful connection
                        error_handler.cache_successful_data('connection_test', service_name, True)
                
            except Exception as e:
                error_handler.handle_aws_error(e, service_name, 'connection_test')
                test_results[service_name] = False
        
        self._connection_status = test_results
        return test_results
    
    def _test_dynamodb_connection(self) -> bool:
        """Test DynamoDB connection and table access"""
        try:
            # Test table existence and access
            table = self._clients['dynamodb']['table']
            table.load()
            
            # Test basic query capability
            response = table.scan(Limit=1)
            logger.info("DynamoDB connection test successful")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"DynamoDB table '{config_manager.aws_config.dynamodb_table_name}' not found")
            else:
                logger.error(f"DynamoDB connection test failed: {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"DynamoDB connection test failed: {str(e)}")
            return False
    
    def _test_sagemaker_connection(self) -> bool:
        """Test SageMaker endpoint availability"""
        try:
            client = self._clients['sagemaker']
            
            # Test XGBoost endpoint
            xgb_available = self._test_sagemaker_endpoint(
                client, config_manager.aws_config.xgboost_endpoint
            )
            
            # Test Random Forest endpoint
            rf_available = self._test_sagemaker_endpoint(
                client, config_manager.aws_config.random_forest_endpoint
            )
            
            success = xgb_available and rf_available
            if success:
                logger.info("SageMaker endpoints connection test successful")
            else:
                logger.warning("One or more SageMaker endpoints unavailable")
            
            return success
            
        except Exception as e:
            logger.error(f"SageMaker connection test failed: {str(e)}")
            return False
    
    def _test_sagemaker_endpoint(self, client, endpoint_name: str) -> bool:
        """Test individual SageMaker endpoint availability"""
        try:
            # Create a minimal test payload
            test_payload = "[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]"
            
            response = client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='text/csv',
                Body=test_payload
            )
            
            # Check if we got a valid response
            result = response['Body'].read()
            logger.debug(f"SageMaker endpoint '{endpoint_name}' test successful")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ValidationException':
                # Endpoint exists but may not like our test payload - that's OK
                logger.debug(f"SageMaker endpoint '{endpoint_name}' exists (validation error expected)")
                return True
            else:
                logger.error(f"SageMaker endpoint '{endpoint_name}' test failed: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"SageMaker endpoint '{endpoint_name}' test failed: {str(e)}")
            return False
    
    def _test_lambda_connection(self) -> bool:
        """Test Lambda service connection"""
        try:
            client = self._clients['lambda']
            
            # Test by listing functions (this verifies permissions and connectivity)
            response = client.list_functions(MaxItems=1)
            
            # Optionally test specific function existence
            functions_to_check = [
                config_manager.aws_config.traffic_generator_function,
                config_manager.aws_config.data_aggregator_function,
                config_manager.aws_config.intelligent_warmer_function
            ]
            
            all_functions_exist = True
            for func_name in functions_to_check:
                try:
                    client.get_function(FunctionName=func_name)
                    logger.debug(f"Lambda function '{func_name}' exists")
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        logger.warning(f"Lambda function '{func_name}' not found")
                        all_functions_exist = False
            
            if all_functions_exist:
                logger.info("Lambda connection test successful - all functions found")
            else:
                logger.warning("Lambda connection successful but some functions missing")
            
            return True  # Return True if we can connect, even if some functions are missing
            
        except Exception as e:
            logger.error(f"Lambda connection test failed: {str(e)}")
            return False
    
    def _test_cloudwatch_connection(self) -> bool:
        """Test CloudWatch service connection"""
        try:
            client = self._clients['cloudwatch']
            
            # Test by listing metrics (this verifies permissions and connectivity)
            response = client.list_metrics(MaxRecords=1)
            
            logger.info("CloudWatch connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"CloudWatch connection test failed: {str(e)}")
            return False
    
    def get_client(self, service_name: str):
        """
        Get a specific AWS client
        
        Args:
            service_name: Name of the AWS service ('dynamodb', 'sagemaker', 'lambda', 'cloudwatch')
            
        Returns:
            The requested AWS client
            
        Raises:
            AWSClientError: If client not initialized or service not found
        """
        if not self._clients:
            raise AWSClientError("Clients not initialized. Call initialize_clients() first.")
        
        if service_name not in self._clients:
            raise AWSClientError(f"Unknown service: {service_name}")
        
        return self._clients[service_name]
    
    def get_connection_status(self) -> Dict[str, bool]:
        """
        Get the last connection test results
        
        Returns:
            Dict with service names as keys and connection status as values
        """
        return self._connection_status.copy()
    
    def is_healthy(self) -> bool:
        """
        Check if all services are healthy
        
        Returns:
            True if all services are connected, False otherwise
        """
        if not self._connection_status:
            return False
        
        return all(self._connection_status.values())

# Global AWS client manager instance
aws_client_manager = AWSClientManager()