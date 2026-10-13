"""
User-Friendly Error Messages Service
Provides clear, actionable error messages and diagnostic information for users
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from services.error_handling import ErrorInfo, ErrorSeverity, ServiceStatus
from services.cloudwatch_logger import cloudwatch_logger

class UserMessageService:
    """
    Service for creating user-friendly error messages with clear actions and diagnostic information
    """
    
    def __init__(self):
        """Initialize the user message service"""
        self.message_templates = self._initialize_message_templates()
        self.action_templates = self._initialize_action_templates()
    
    def create_user_friendly_error_message(self, error_info: ErrorInfo, 
                                         include_technical_details: bool = False) -> Dict[str, Any]:
        """
        Create a user-friendly error message from ErrorInfo
        
        Args:
            error_info: ErrorInfo object with error details
            include_technical_details: Whether to include technical diagnostic information
            
        Returns:
            Dictionary with user-friendly message components
        """
        # Log the error for diagnostics
        cloudwatch_logger.log_error({
            'service_name': error_info.service_name,
            'error_type': error_info.error_type,
            'error_code': error_info.error_code,
            'message': error_info.message,
            'severity': error_info.severity.value,
            'operation': error_info.diagnostic_info.get('operation', 'unknown'),
            'retry_count': error_info.retry_count,
            'diagnostic_info': error_info.diagnostic_info,
            'suggested_action': error_info.suggested_action
        })
        
        # Get message template based on error type and service
        template_key = f"{error_info.service_name}_{error_info.error_type}"
        if template_key not in self.message_templates:
            template_key = f"generic_{error_info.error_type}"
        if template_key not in self.message_templates:
            template_key = "generic_error"
        
        template = self.message_templates[template_key]
        
        # Create user-friendly message
        user_message = {
            'title': self._format_error_title(error_info),
            'message': self._format_error_message(error_info, template),
            'severity': self._get_user_severity(error_info.severity),
            'icon': self._get_severity_icon(error_info.severity),
            'actions': self._get_suggested_actions(error_info),
            'timestamp': error_info.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'service_affected': error_info.service_name.title(),
            'can_retry': error_info.retry_count < error_info.max_retries,
            'retry_info': self._get_retry_info(error_info) if error_info.retry_count > 0 else None
        }
        
        # Add technical details if requested
        if include_technical_details:
            user_message['technical_details'] = {
                'error_type': error_info.error_type,
                'error_code': error_info.error_code,
                'diagnostic_info': error_info.diagnostic_info,
                'original_message': error_info.message
            }
        
        return user_message
    
    def create_service_status_message(self, service_name: str, status: ServiceStatus, 
                                    recent_errors: List[ErrorInfo] = None) -> Dict[str, Any]:
        """
        Create user-friendly service status message
        
        Args:
            service_name: Name of the service
            status: Current service status
            recent_errors: List of recent errors for this service
            
        Returns:
            Dictionary with service status message
        """
        if recent_errors is None:
            recent_errors = []
        
        status_messages = {
            ServiceStatus.HEALTHY: {
                'title': f'{service_name.title()} Service is Healthy',
                'message': f'The {service_name} service is operating normally with no recent issues.',
                'icon': '✅',
                'color': 'success',
                'actions': []
            },
            ServiceStatus.DEGRADED: {
                'title': f'{service_name.title()} Service is Experiencing Issues',
                'message': f'The {service_name} service is partially functional but experiencing some problems.',
                'icon': '⚠️',
                'color': 'warning',
                'actions': ['Check service logs', 'Monitor performance', 'Consider retry operations']
            },
            ServiceStatus.UNAVAILABLE: {
                'title': f'{service_name.title()} Service is Unavailable',
                'message': f'The {service_name} service is currently unavailable and cannot process requests.',
                'icon': '❌',
                'color': 'error',
                'actions': ['Check AWS service status', 'Verify credentials', 'Contact support if issue persists']
            },
            ServiceStatus.UNKNOWN: {
                'title': f'{service_name.title()} Service Status Unknown',
                'message': f'Unable to determine the current status of the {service_name} service.',
                'icon': '❓',
                'color': 'info',
                'actions': ['Run connection test', 'Check configuration', 'Verify network connectivity']
            }
        }
        
        base_message = status_messages[status].copy()
        
        # Add recent error information
        if recent_errors:
            error_count = len(recent_errors)
            latest_error = recent_errors[0]  # Assuming sorted by timestamp
            
            base_message['recent_errors'] = {
                'count': error_count,
                'latest_error_time': latest_error.timestamp.strftime('%H:%M:%S'),
                'latest_error_type': latest_error.error_type,
                'summary': f'{error_count} error(s) in the last hour'
            }
            
            # Add specific actions based on recent errors
            if any(e.error_code == 'AccessDenied' for e in recent_errors):
                base_message['actions'].insert(0, 'Check IAM permissions and AWS credentials')
            
            if any(e.error_code == 'ThrottlingException' for e in recent_errors):
                base_message['actions'].insert(0, 'Reduce request rate to avoid throttling')
        
        return base_message
    
    def create_connection_test_message(self, service_name: str, success: bool, 
                                     error_details: Optional[str] = None) -> Dict[str, Any]:
        """
        Create user-friendly connection test result message
        
        Args:
            service_name: Name of the service tested
            success: Whether the connection test succeeded
            error_details: Error details if connection failed
            
        Returns:
            Dictionary with connection test message
        """
        if success:
            return {
                'title': f'{service_name.title()} Connection Successful',
                'message': f'Successfully connected to {service_name} service. All operations should work normally.',
                'icon': '✅',
                'color': 'success',
                'actions': []
            }
        else:
            actions = [
                'Check internet connectivity',
                f'Verify {service_name} service configuration',
                'Check AWS credentials and permissions',
                'Try again in a few moments'
            ]
            
            # Add specific actions based on error details
            if error_details:
                if 'credentials' in error_details.lower():
                    actions.insert(0, 'Configure AWS credentials using AWS CLI or environment variables')
                elif 'region' in error_details.lower():
                    actions.insert(0, 'Verify AWS region configuration')
                elif 'timeout' in error_details.lower():
                    actions.insert(0, 'Check network connectivity and firewall settings')
            
            return {
                'title': f'{service_name.title()} Connection Failed',
                'message': f'Unable to connect to {service_name} service. Some features may not work properly.',
                'icon': '❌',
                'color': 'error',
                'actions': actions,
                'error_details': error_details
            }
    
    def create_fallback_data_message(self, data_type: str, service_name: str, 
                                   fallback_source: str, is_stale: bool = False) -> Dict[str, Any]:
        """
        Create message explaining fallback data usage
        
        Args:
            data_type: Type of data being shown
            service_name: Service that's unavailable
            fallback_source: Source of fallback data ('cache', 'default', 'mock')
            is_stale: Whether the fallback data is stale
            
        Returns:
            Dictionary with fallback data message
        """
        source_descriptions = {
            'cache': 'recent cached data',
            'default': 'default placeholder data',
            'mock': 'simulated data for demonstration'
        }
        
        source_desc = source_descriptions.get(fallback_source, 'alternative data')
        
        if fallback_source == 'cache' and not is_stale:
            return {
                'title': f'Showing Recent {data_type.title()} Data',
                'message': f'The {service_name} service is temporarily unavailable. Displaying {source_desc} from the last successful request.',
                'icon': 'ℹ️',
                'color': 'info',
                'actions': ['Refresh page to retry', 'Check service status']
            }
        elif fallback_source == 'cache' and is_stale:
            return {
                'title': f'Showing Older {data_type.title()} Data',
                'message': f'The {service_name} service is unavailable. Displaying older cached data that may not reflect current conditions.',
                'icon': '⚠️',
                'color': 'warning',
                'actions': ['Check service status', 'Try refreshing in a few minutes']
            }
        else:
            return {
                'title': f'Service Temporarily Unavailable',
                'message': f'The {service_name} service is currently unavailable. Displaying {source_desc} until service is restored.',
                'icon': '⚠️',
                'color': 'warning',
                'actions': ['Check AWS service status', 'Verify configuration', 'Try again later']
            }
    
    def create_recovery_suggestions(self, service_name: str, error_history: List[ErrorInfo]) -> List[Dict[str, Any]]:
        """
        Create recovery suggestions based on error history
        
        Args:
            service_name: Name of the service
            error_history: List of recent errors for the service
            
        Returns:
            List of recovery suggestion dictionaries
        """
        suggestions = []
        
        if not error_history:
            return [{
                'title': 'No Recent Issues',
                'description': f'The {service_name} service has no recent error history.',
                'priority': 'info',
                'actions': ['Continue normal operation']
            }]
        
        # Analyze error patterns
        error_codes = [e.error_code for e in error_history if e.error_code]
        error_types = [e.error_type for e in error_history]
        
        # Credential issues
        if any(code in ['AccessDenied', 'UnauthorizedOperation'] for code in error_codes):
            suggestions.append({
                'title': 'Fix Authentication Issues',
                'description': 'Multiple authentication errors detected. AWS credentials may be invalid or insufficient.',
                'priority': 'high',
                'actions': [
                    'Run "aws configure" to set up credentials',
                    'Check IAM permissions for the service',
                    'Verify AWS access keys are not expired'
                ]
            })
        
        # Throttling issues
        if any(code in ['ThrottlingException', 'RequestLimitExceeded'] for code in error_codes):
            suggestions.append({
                'title': 'Reduce Request Rate',
                'description': 'Service is being throttled due to high request rate.',
                'priority': 'medium',
                'actions': [
                    'Implement exponential backoff in retry logic',
                    'Reduce frequency of dashboard refreshes',
                    'Consider request batching where possible'
                ]
            })
        
        # Connection issues
        if any(error_type in ['EndpointConnectionError', 'ConnectTimeoutError'] for error_type in error_types):
            suggestions.append({
                'title': 'Fix Connectivity Issues',
                'description': 'Network connectivity problems detected.',
                'priority': 'high',
                'actions': [
                    'Check internet connection',
                    'Verify firewall and proxy settings',
                    'Test connectivity to AWS endpoints'
                ]
            })
        
        # Resource not found
        if any(code == 'ResourceNotFoundException' for code in error_codes):
            suggestions.append({
                'title': 'Verify Resource Configuration',
                'description': 'Some AWS resources could not be found.',
                'priority': 'high',
                'actions': [
                    f'Check {service_name} resource names in configuration',
                    'Verify resources exist in the correct AWS region',
                    'Confirm resource permissions'
                ]
            })
        
        # Service-specific suggestions
        if service_name == 'sagemaker':
            suggestions.append({
                'title': 'Check SageMaker Endpoints',
                'description': 'Verify SageMaker endpoints are deployed and in service.',
                'priority': 'medium',
                'actions': [
                    'Check endpoint status in SageMaker console',
                    'Verify endpoint names match configuration',
                    'Ensure endpoints are in the correct region'
                ]
            })
        
        elif service_name == 'dynamodb':
            suggestions.append({
                'title': 'Verify DynamoDB Table',
                'description': 'Check DynamoDB table configuration and status.',
                'priority': 'medium',
                'actions': [
                    'Confirm table exists and is active',
                    'Check table name matches configuration',
                    'Verify read/write permissions'
                ]
            })
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    def _initialize_message_templates(self) -> Dict[str, Dict[str, str]]:
        """Initialize error message templates"""
        return {
            'sagemaker_ClientError': {
                'title_template': 'ML Prediction Service Issue',
                'message_template': 'The machine learning prediction service encountered an error. This may affect live predictions and model accuracy displays.'
            },
            'dynamodb_ClientError': {
                'title_template': 'Data Storage Service Issue',
                'message_template': 'The data storage service is experiencing problems. Recent request data and statistics may not be available.'
            },
            'lambda_ClientError': {
                'title_template': 'Function Execution Service Issue',
                'message_template': 'The function execution service has encountered an error. Traffic generation and warming operations may be affected.'
            },
            'cloudwatch_ClientError': {
                'title_template': 'Monitoring Service Issue',
                'message_template': 'The monitoring service is having problems. System metrics and health information may not be current.'
            },
            'generic_ClientError': {
                'title_template': 'AWS Service Issue',
                'message_template': 'An AWS service is experiencing problems. Some dashboard features may not work properly.'
            },
            'generic_NoCredentialsError': {
                'title_template': 'Authentication Required',
                'message_template': 'AWS credentials are not configured. Please set up your AWS credentials to access cloud services.'
            },
            'generic_EndpointConnectionError': {
                'title_template': 'Connection Problem',
                'message_template': 'Unable to connect to AWS services. Please check your internet connection and try again.'
            },
            'generic_error': {
                'title_template': 'Unexpected Error',
                'message_template': 'An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.'
            }
        }
    
    def _initialize_action_templates(self) -> Dict[str, List[str]]:
        """Initialize suggested action templates"""
        return {
            'credentials': [
                'Configure AWS credentials using "aws configure"',
                'Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables',
                'Verify IAM permissions for the required services'
            ],
            'connectivity': [
                'Check your internet connection',
                'Verify firewall and proxy settings',
                'Try refreshing the page'
            ],
            'throttling': [
                'Wait a moment before trying again',
                'Reduce the frequency of requests',
                'Check AWS service limits'
            ],
            'configuration': [
                'Verify service configuration settings',
                'Check resource names and regions',
                'Confirm all required resources exist'
            ]
        }
    
    def _format_error_title(self, error_info: ErrorInfo) -> str:
        """Format user-friendly error title"""
        service_names = {
            'sagemaker': 'ML Prediction Service',
            'dynamodb': 'Data Storage Service',
            'lambda': 'Function Execution Service',
            'cloudwatch': 'Monitoring Service'
        }
        
        service_display = service_names.get(error_info.service_name, error_info.service_name.title())
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            return f'🚨 Critical Issue with {service_display}'
        elif error_info.severity == ErrorSeverity.HIGH:
            return f'❌ {service_display} Error'
        elif error_info.severity == ErrorSeverity.MEDIUM:
            return f'⚠️ {service_display} Warning'
        else:
            return f'ℹ️ {service_display} Notice'
    
    def _format_error_message(self, error_info: ErrorInfo, template: Dict[str, str]) -> str:
        """Format user-friendly error message"""
        base_message = template.get('message_template', error_info.message)
        
        # Add specific error code information if available
        if error_info.error_code:
            code_explanations = {
                'AccessDenied': 'You do not have permission to perform this operation.',
                'ThrottlingException': 'Too many requests are being made. Please slow down.',
                'ResourceNotFoundException': 'The requested resource could not be found.',
                'ValidationException': 'The request contains invalid parameters.',
                'ServiceUnavailable': 'The service is temporarily unavailable.',
                'InternalError': 'An internal service error occurred.'
            }
            
            if error_info.error_code in code_explanations:
                base_message += f' {code_explanations[error_info.error_code]}'
        
        return base_message
    
    def _get_user_severity(self, severity: ErrorSeverity) -> str:
        """Convert ErrorSeverity to user-friendly severity"""
        mapping = {
            ErrorSeverity.CRITICAL: 'critical',
            ErrorSeverity.HIGH: 'error',
            ErrorSeverity.MEDIUM: 'warning',
            ErrorSeverity.LOW: 'info'
        }
        return mapping.get(severity, 'info')
    
    def _get_severity_icon(self, severity: ErrorSeverity) -> str:
        """Get icon for error severity"""
        mapping = {
            ErrorSeverity.CRITICAL: '🚨',
            ErrorSeverity.HIGH: '❌',
            ErrorSeverity.MEDIUM: '⚠️',
            ErrorSeverity.LOW: 'ℹ️'
        }
        return mapping.get(severity, 'ℹ️')
    
    def _get_suggested_actions(self, error_info: ErrorInfo) -> List[str]:
        """Get suggested actions for error"""
        actions = []
        
        # Add the primary suggested action
        if error_info.suggested_action:
            actions.append(error_info.suggested_action)
        
        # Add specific actions based on error code
        if error_info.error_code:
            if error_info.error_code in ['AccessDenied', 'UnauthorizedOperation']:
                actions.extend(self.action_templates['credentials'])
            elif error_info.error_code in ['ThrottlingException', 'RequestLimitExceeded']:
                actions.extend(self.action_templates['throttling'])
            elif error_info.error_code == 'ResourceNotFoundException':
                actions.extend(self.action_templates['configuration'])
        
        # Add connectivity actions for connection errors
        if error_info.error_type in ['EndpointConnectionError', 'ConnectTimeoutError']:
            actions.extend(self.action_templates['connectivity'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_actions = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)
        
        return unique_actions[:5]  # Limit to 5 actions
    
    def _get_retry_info(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Get retry information for display"""
        return {
            'current_attempt': error_info.retry_count,
            'max_attempts': error_info.max_retries,
            'can_retry_more': error_info.retry_count < error_info.max_retries,
            'progress_percentage': (error_info.retry_count / error_info.max_retries) * 100 if error_info.max_retries > 0 else 0
        }

# Global user message service instance
user_message_service = UserMessageService()