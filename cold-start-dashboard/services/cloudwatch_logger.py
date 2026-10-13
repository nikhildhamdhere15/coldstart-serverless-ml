"""
CloudWatch Logging Service
Provides error logging to CloudWatch with structured logging and user-friendly messages
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from config import config_manager

class CloudWatchLogger:
    """
    Service for logging errors and events to CloudWatch with structured formatting
    """
    
    def __init__(self, log_group_name: str = None):
        """
        Initialize CloudWatch logger
        
        Args:
            log_group_name: CloudWatch log group name. If None, uses default from config.
        """
        self.log_group_name = log_group_name or f"/aws/dashboard/{config_manager.dashboard_config.title.lower().replace(' ', '-')}"
        self.log_stream_name = f"dashboard-{datetime.now().strftime('%Y-%m-%d')}"
        
        try:
            self.cloudwatch_logs = boto3.client('logs', region_name=config_manager.aws_config.region)
            self._ensure_log_group_exists()
            self._ensure_log_stream_exists()
        except Exception as e:
            # Fallback to local logging if CloudWatch is unavailable
            logging.warning(f"CloudWatch logging unavailable, falling back to local logging: {str(e)}")
            self.cloudwatch_logs = None
    
    def log_error(self, error_info: Dict[str, Any], user_context: Dict[str, Any] = None):
        """
        Log error information to CloudWatch with structured format
        
        Args:
            error_info: Error information dictionary
            user_context: Additional user context information
        """
        if user_context is None:
            user_context = {}
        
        # Create structured log entry
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'service': error_info.get('service_name', 'unknown'),
            'error_type': error_info.get('error_type', 'UnknownError'),
            'error_code': error_info.get('error_code'),
            'message': error_info.get('message', 'No message provided'),
            'severity': error_info.get('severity', 'medium'),
            'operation': error_info.get('operation', 'unknown'),
            'retry_count': error_info.get('retry_count', 0),
            'user_context': user_context,
            'diagnostic_info': error_info.get('diagnostic_info', {}),
            'suggested_action': error_info.get('suggested_action', 'No action suggested')
        }
        
        # Log to CloudWatch if available
        if self.cloudwatch_logs:
            try:
                self._send_to_cloudwatch(log_entry)
            except Exception as e:
                # Fallback to local logging
                logging.error(f"Failed to send to CloudWatch: {str(e)}")
                self._log_locally(log_entry)
        else:
            self._log_locally(log_entry)
    
    def log_event(self, event_type: str, message: str, details: Dict[str, Any] = None):
        """
        Log general events to CloudWatch
        
        Args:
            event_type: Type of event (e.g., 'user_action', 'system_event')
            message: Event message
            details: Additional event details
        """
        if details is None:
            details = {}
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'event_type': event_type,
            'message': message,
            'details': details
        }
        
        if self.cloudwatch_logs:
            try:
                self._send_to_cloudwatch(log_entry)
            except Exception:
                self._log_locally(log_entry)
        else:
            self._log_locally(log_entry)
    
    def log_user_action(self, action: str, user_id: str = None, details: Dict[str, Any] = None):
        """
        Log user actions for audit and debugging
        
        Args:
            action: Action performed by user
            user_id: User identifier (if available)
            details: Additional action details
        """
        if details is None:
            details = {}
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'event_type': 'user_action',
            'action': action,
            'user_id': user_id or 'anonymous',
            'details': details
        }
        
        if self.cloudwatch_logs:
            try:
                self._send_to_cloudwatch(log_entry)
            except Exception:
                self._log_locally(log_entry)
        else:
            self._log_locally(log_entry)
    
    def _ensure_log_group_exists(self):
        """Ensure CloudWatch log group exists"""
        try:
            self.cloudwatch_logs.describe_log_groups(logGroupNamePrefix=self.log_group_name)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create log group
                self.cloudwatch_logs.create_log_group(logGroupName=self.log_group_name)
                
                # Set retention policy (30 days)
                self.cloudwatch_logs.put_retention_policy(
                    logGroupName=self.log_group_name,
                    retentionInDays=30
                )
    
    def _ensure_log_stream_exists(self):
        """Ensure CloudWatch log stream exists"""
        try:
            self.cloudwatch_logs.describe_log_streams(
                logGroupName=self.log_group_name,
                logStreamNamePrefix=self.log_stream_name
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create log stream
                self.cloudwatch_logs.create_log_stream(
                    logGroupName=self.log_group_name,
                    logStreamName=self.log_stream_name
                )
    
    def _send_to_cloudwatch(self, log_entry: Dict[str, Any]):
        """Send log entry to CloudWatch"""
        log_events = [{
            'timestamp': int(datetime.now().timestamp() * 1000),
            'message': json.dumps(log_entry, default=str)
        }]
        
        self.cloudwatch_logs.put_log_events(
            logGroupName=self.log_group_name,
            logStreamName=self.log_stream_name,
            logEvents=log_events
        )
    
    def _log_locally(self, log_entry: Dict[str, Any]):
        """Fallback to local logging"""
        level = log_entry.get('level', 'INFO')
        message = json.dumps(log_entry, default=str, indent=2)
        
        if level == 'ERROR':
            logging.error(message)
        elif level == 'WARNING':
            logging.warning(message)
        else:
            logging.info(message)

# Global CloudWatch logger instance
cloudwatch_logger = CloudWatchLogger()