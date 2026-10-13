"""
Comprehensive Error Handling Service
Provides graceful degradation, retry logic, and fallback displays for AWS service outages
"""

import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import boto3
from botocore.exceptions import (
    ClientError, NoCredentialsError, PartialCredentialsError,
    EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError,
    BotoCoreError
)
from config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ServiceStatus(Enum):
    """Service status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"

@dataclass
class ErrorInfo:
    """Comprehensive error information"""
    error_type: str
    error_code: Optional[str]
    message: str
    severity: ErrorSeverity
    service_name: str
    timestamp: datetime
    retry_count: int = 0
    max_retries: int = 3
    suggested_action: str = ""
    diagnostic_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.diagnostic_info is None:
            self.diagnostic_info = {}

@dataclass
class FallbackData:
    """Fallback data for when services are unavailable"""
    data_type: str
    data: Any
    timestamp: datetime
    source: str  # 'cache', 'default', 'mock'
    is_stale: bool = False
    
class RetryConfig:
    """Configuration for retry logic"""
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, exponential_base: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for exponential backoff"""
        delay = self.base_delay * (self.exponential_base ** retry_count)
        return min(delay, self.max_delay)

class ErrorHandlingService:
    """
    Comprehensive error handling service with graceful degradation,
    retry logic, and fallback displays
    """
    
    def __init__(self):
        """Initialize the error handling service"""
        self._error_history: List[ErrorInfo] = []
        self._service_status: Dict[str, ServiceStatus] = {}
        self._fallback_cache: Dict[str, FallbackData] = {}
        self._retry_configs: Dict[str, RetryConfig] = {
            'default': RetryConfig(),
            'sagemaker': RetryConfig(max_retries=2, base_delay=2.0),
            'dynamodb': RetryConfig(max_retries=3, base_delay=1.0),
            'lambda': RetryConfig(max_retries=2, base_delay=1.5),
            'cloudwatch': RetryConfig(max_retries=3, base_delay=0.5)
        }
        
        # Initialize fallback data
        self._initialize_fallback_data()
    
    def handle_aws_error(self, error: Exception, service_name: str, 
                        operation: str, context: Dict[str, Any] = None) -> ErrorInfo:
        """
        Handle AWS service errors with comprehensive error analysis
        
        Args:
            error: The exception that occurred
            service_name: Name of the AWS service
            operation: The operation that failed
            context: Additional context information
            
        Returns:
            ErrorInfo object with comprehensive error details
        """
        if context is None:
            context = {}
        
        # Analyze the error
        error_info = self._analyze_error(error, service_name, operation, context)
        
        # Add to error history
        self._error_history.append(error_info)
        
        # Update service status
        self._update_service_status(service_name, error_info)
        
        # Log the error with appropriate level
        self._log_error(error_info)
        
        return error_info
    
    def retry_with_backoff(self, func: Callable, service_name: str, 
                          *args, **kwargs) -> Tuple[Any, Optional[ErrorInfo]]:
        """
        Execute function with exponential backoff retry logic
        
        Args:
            func: Function to execute
            service_name: Name of the service for retry configuration
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Tuple of (result, error_info). If successful, error_info is None.
        """
        retry_config = self._retry_configs.get(service_name, self._retry_configs['default'])
        last_error = None
        
        for attempt in range(retry_config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # Success - update service status if it was degraded
                if self._service_status.get(service_name) != ServiceStatus.HEALTHY:
                    self._service_status[service_name] = ServiceStatus.HEALTHY
                    logger.info(f"Service {service_name} recovered after {attempt} retries")
                
                return result, None
                
            except Exception as e:
                last_error = e
                
                # Handle the error
                error_info = self.handle_aws_error(e, service_name, func.__name__)
                error_info.retry_count = attempt
                error_info.max_retries = retry_config.max_retries
                
                # If this is the last attempt, return the error
                if attempt >= retry_config.max_retries:
                    logger.error(f"All retry attempts failed for {service_name}.{func.__name__}")
                    return None, error_info
                
                # Calculate delay and wait
                delay = retry_config.get_delay(attempt)
                logger.warning(f"Retry {attempt + 1}/{retry_config.max_retries} for {service_name}.{func.__name__} in {delay:.1f}s")
                time.sleep(delay)
        
        # This should never be reached, but just in case
        return None, self.handle_aws_error(last_error, service_name, func.__name__)
    
    def get_fallback_data(self, data_type: str, service_name: str) -> Optional[FallbackData]:
        """
        Get fallback data when service is unavailable
        
        Args:
            data_type: Type of data requested
            service_name: Name of the service that's unavailable
            
        Returns:
            FallbackData object or None if no fallback available
        """
        cache_key = f"{service_name}_{data_type}"
        
        # Check if we have cached data
        if cache_key in self._fallback_cache:
            fallback = self._fallback_cache[cache_key]
            
            # Check if data is stale (older than 1 hour)
            if (datetime.now() - fallback.timestamp).total_seconds() > 3600:
                fallback.is_stale = True
            
            return fallback
        
        # Return default fallback data
        return self._get_default_fallback_data(data_type, service_name)
    
    def cache_successful_data(self, data_type: str, service_name: str, data: Any):
        """
        Cache successful data for fallback use
        
        Args:
            data_type: Type of data
            service_name: Name of the service
            data: The data to cache
        """
        cache_key = f"{service_name}_{data_type}"
        
        self._fallback_cache[cache_key] = FallbackData(
            data_type=data_type,
            data=data,
            timestamp=datetime.now(),
            source='cache',
            is_stale=False
        )
        
        logger.debug(f"Cached {data_type} data for {service_name}")
    
    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get current status of a service"""
        return self._service_status.get(service_name, ServiceStatus.UNKNOWN)
    
    def get_all_service_status(self) -> Dict[str, ServiceStatus]:
        """Get status of all services"""
        return self._service_status.copy()
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get error summary for the specified time period
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with error statistics
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [e for e in self._error_history if e.timestamp >= cutoff_time]
        
        if not recent_errors:
            return {
                'total_errors': 0,
                'errors_by_service': {},
                'errors_by_severity': {},
                'most_common_errors': [],
                'service_health_score': 100.0
            }
        
        # Group errors by service
        errors_by_service = {}
        for error in recent_errors:
            if error.service_name not in errors_by_service:
                errors_by_service[error.service_name] = []
            errors_by_service[error.service_name].append(error)
        
        # Group errors by severity
        errors_by_severity = {}
        for error in recent_errors:
            severity = error.severity.value
            if severity not in errors_by_severity:
                errors_by_severity[severity] = 0
            errors_by_severity[severity] += 1
        
        # Find most common error types
        error_types = {}
        for error in recent_errors:
            error_type = error.error_type
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
        
        most_common_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate service health score
        total_operations = len(recent_errors) + 100  # Assume some successful operations
        health_score = max(0, (total_operations - len(recent_errors)) / total_operations * 100)
        
        return {
            'total_errors': len(recent_errors),
            'errors_by_service': {k: len(v) for k, v in errors_by_service.items()},
            'errors_by_severity': errors_by_severity,
            'most_common_errors': most_common_errors,
            'service_health_score': health_score,
            'time_period_hours': hours
        }
    
    def get_diagnostic_info(self, service_name: str) -> Dict[str, Any]:
        """
        Get diagnostic information for a service
        
        Args:
            service_name: Name of the service
            
        Returns:
            Dictionary with diagnostic information
        """
        recent_errors = [e for e in self._error_history 
                        if e.service_name == service_name and 
                        (datetime.now() - e.timestamp).total_seconds() < 3600]
        
        status = self.get_service_status(service_name)
        
        diagnostic_info = {
            'service_name': service_name,
            'current_status': status.value,
            'recent_error_count': len(recent_errors),
            'last_error_time': recent_errors[-1].timestamp if recent_errors else None,
            'common_error_types': {},
            'suggested_actions': [],
            'configuration_check': self._check_service_configuration(service_name)
        }
        
        # Analyze recent errors
        if recent_errors:
            error_types = {}
            for error in recent_errors:
                if error.error_type not in error_types:
                    error_types[error.error_type] = 0
                error_types[error.error_type] += 1
            
            diagnostic_info['common_error_types'] = error_types
            diagnostic_info['suggested_actions'] = self._get_service_suggestions(service_name, recent_errors)
        
        return diagnostic_info
    
    def clear_error_history(self, hours: int = None):
        """
        Clear error history
        
        Args:
            hours: If specified, only clear errors older than this many hours
        """
        if hours is None:
            self._error_history.clear()
            logger.info("Cleared all error history")
        else:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            self._error_history = [e for e in self._error_history if e.timestamp >= cutoff_time]
            logger.info(f"Cleared error history older than {hours} hours")
    
    def _analyze_error(self, error: Exception, service_name: str, 
                      operation: str, context: Dict[str, Any]) -> ErrorInfo:
        """Analyze an error and create ErrorInfo"""
        error_type = type(error).__name__
        error_code = None
        severity = ErrorSeverity.MEDIUM
        suggested_action = "Please try again later"
        diagnostic_info = context.copy()
        
        # Analyze specific error types
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_message = error.response.get('Error', {}).get('Message', str(error))
            
            # Determine severity based on error code
            if error_code in ['ThrottlingException', 'RequestLimitExceeded']:
                severity = ErrorSeverity.HIGH
                suggested_action = "Reduce request rate and implement exponential backoff"
            elif error_code in ['AccessDenied', 'UnauthorizedOperation']:
                severity = ErrorSeverity.CRITICAL
                suggested_action = "Check AWS credentials and IAM permissions"
            elif error_code in ['ResourceNotFoundException', 'ValidationException']:
                severity = ErrorSeverity.MEDIUM
                suggested_action = "Verify resource names and configuration"
            elif error_code in ['ServiceUnavailable', 'InternalError']:
                severity = ErrorSeverity.HIGH
                suggested_action = "AWS service may be experiencing issues. Check AWS status page"
            
            diagnostic_info.update({
                'aws_error_code': error_code,
                'aws_request_id': error.response.get('ResponseMetadata', {}).get('RequestId'),
                'http_status_code': error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            })
            
        elif isinstance(error, (NoCredentialsError, PartialCredentialsError)):
            severity = ErrorSeverity.CRITICAL
            error_message = "AWS credentials not configured properly"
            suggested_action = "Configure AWS credentials using AWS CLI, environment variables, or IAM roles"
            
        elif isinstance(error, (EndpointConnectionError, ConnectTimeoutError)):
            severity = ErrorSeverity.HIGH
            error_message = f"Cannot connect to AWS {service_name} service"
            suggested_action = "Check internet connectivity and AWS service status"
            
        elif isinstance(error, ReadTimeoutError):
            severity = ErrorSeverity.MEDIUM
            error_message = f"Request to {service_name} timed out"
            suggested_action = "Increase timeout settings or check network connectivity"
            
        else:
            error_message = str(error)
            suggested_action = "Check logs for more details and try again"
        
        # Add operation context
        diagnostic_info.update({
            'operation': operation,
            'service_name': service_name,
            'error_class': error_type
        })
        
        return ErrorInfo(
            error_type=error_type,
            error_code=error_code,
            message=error_message,
            severity=severity,
            service_name=service_name,
            timestamp=datetime.now(),
            suggested_action=suggested_action,
            diagnostic_info=diagnostic_info
        )
    
    def _update_service_status(self, service_name: str, error_info: ErrorInfo):
        """Update service status based on error"""
        if error_info.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            self._service_status[service_name] = ServiceStatus.UNAVAILABLE
        else:
            # For medium/low severity errors, mark as degraded
            self._service_status[service_name] = ServiceStatus.DEGRADED
    
    def _log_error(self, error_info: ErrorInfo):
        """Log error with appropriate level"""
        log_message = f"{error_info.service_name}: {error_info.message}"
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def _initialize_fallback_data(self):
        """Initialize default fallback data"""
        # System health fallback
        self._fallback_cache['system_health_default'] = FallbackData(
            data_type='system_health',
            data={
                'api_status': 'unknown',
                'sagemaker_endpoints': {},
                'lambda_functions': {},
                'dynamodb_status': 'unknown',
                'recent_request_count': 0,
                'uptime_percentage': 0.0,
                'last_updated': datetime.now()
            },
            timestamp=datetime.now(),
            source='default'
        )
        
        # Prediction fallback
        self._fallback_cache['prediction_default'] = FallbackData(
            data_type='prediction',
            data={
                'xgboost_probability': 0.5,
                'random_forest_probability': 0.5,
                'ensemble_probability': 0.5,
                'prediction_label': 'unknown',
                'recommendation': 'Service temporarily unavailable. Please try again later.',
                'model_agreement': 0.0,
                'timestamp': datetime.now(),
                'success': False,
                'error_message': 'Prediction service unavailable'
            },
            timestamp=datetime.now(),
            source='default'
        )
        
        # Data visualization fallback
        self._fallback_cache['data_visualization_default'] = FallbackData(
            data_type='data_visualization',
            data=[],  # Empty list for no data
            timestamp=datetime.now(),
            source='default'
        )
    
    def _get_default_fallback_data(self, data_type: str, service_name: str) -> Optional[FallbackData]:
        """Get default fallback data for a data type"""
        default_key = f"{data_type}_default"
        
        if default_key in self._fallback_cache:
            return self._fallback_cache[default_key]
        
        # Create generic fallback
        return FallbackData(
            data_type=data_type,
            data=None,
            timestamp=datetime.now(),
            source='default'
        )
    
    def _check_service_configuration(self, service_name: str) -> Dict[str, Any]:
        """Check service configuration for common issues"""
        config_check = {
            'credentials_configured': True,
            'region_configured': True,
            'endpoints_configured': True,
            'permissions_likely_ok': True,
            'issues': []
        }
        
        try:
            # Check basic AWS configuration
            session = boto3.Session()
            
            # Check credentials
            try:
                session.get_credentials()
            except Exception:
                config_check['credentials_configured'] = False
                config_check['issues'].append('AWS credentials not found')
            
            # Check region
            region = session.region_name
            if not region:
                config_check['region_configured'] = False
                config_check['issues'].append('AWS region not configured')
            
            # Service-specific checks
            if service_name == 'sagemaker':
                if not config_manager.aws_config.xgboost_endpoint:
                    config_check['endpoints_configured'] = False
                    config_check['issues'].append('SageMaker endpoints not configured')
            
            elif service_name == 'dynamodb':
                if not config_manager.aws_config.dynamodb_table_name:
                    config_check['endpoints_configured'] = False
                    config_check['issues'].append('DynamoDB table name not configured')
            
        except Exception as e:
            config_check['issues'].append(f'Configuration check failed: {str(e)}')
        
        return config_check
    
    def _get_service_suggestions(self, service_name: str, recent_errors: List[ErrorInfo]) -> List[str]:
        """Get service-specific suggestions based on recent errors"""
        suggestions = []
        
        # Analyze error patterns
        error_codes = [e.error_code for e in recent_errors if e.error_code]
        error_types = [e.error_type for e in recent_errors]
        
        # Common suggestions based on error patterns
        if 'AccessDenied' in error_codes or 'UnauthorizedOperation' in error_codes:
            suggestions.append(f"Check IAM permissions for {service_name} service")
            suggestions.append("Verify AWS credentials are correctly configured")
        
        if 'ThrottlingException' in error_codes or 'RequestLimitExceeded' in error_codes:
            suggestions.append("Implement request rate limiting")
            suggestions.append("Consider using exponential backoff for retries")
        
        if 'EndpointConnectionError' in error_types or 'ConnectTimeoutError' in error_types:
            suggestions.append("Check internet connectivity")
            suggestions.append(f"Verify {service_name} service is available in your region")
        
        if 'ResourceNotFoundException' in error_codes:
            suggestions.append(f"Verify {service_name} resource names in configuration")
            suggestions.append("Check if resources exist in the correct AWS region")
        
        # Service-specific suggestions
        if service_name == 'sagemaker':
            suggestions.append("Check SageMaker endpoint status in AWS console")
            suggestions.append("Verify endpoint names match configuration")
        
        elif service_name == 'dynamodb':
            suggestions.append("Check DynamoDB table exists and is active")
            suggestions.append("Verify table name matches configuration")
        
        elif service_name == 'lambda':
            suggestions.append("Check Lambda function names and regions")
            suggestions.append("Verify Lambda functions are deployed and active")
        
        return suggestions[:5]  # Limit to top 5 suggestions

# Global error handling service instance
error_handler = ErrorHandlingService()