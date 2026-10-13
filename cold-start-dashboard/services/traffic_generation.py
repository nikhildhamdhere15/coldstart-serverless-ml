"""
Traffic Generation Controller Module
Handles traffic generation Lambda invocation, progress monitoring, and concurrency control
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass
from botocore.exceptions import ClientError
from config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class TrafficGenerationStatus:
    """Status information for traffic generation"""
    is_active: bool
    start_time: Optional[datetime] = None
    estimated_duration: Optional[int] = None  # seconds
    progress_percentage: Optional[float] = None
    requests_generated: Optional[int] = None
    error_message: Optional[str] = None

@dataclass
class TrafficGenerationResult:
    """Result of traffic generation operation"""
    success: bool
    requests_generated: int
    duration_seconds: float
    start_time: datetime
    end_time: datetime
    error_message: Optional[str] = None

@dataclass
class TrafficImpactMetrics:
    """Metrics showing the impact of traffic generation"""
    baseline_request_count: int
    post_generation_request_count: int
    requests_added: int
    percentage_increase: float
    measurement_window_minutes: int
    baseline_timestamp: datetime
    post_generation_timestamp: datetime

class TrafficGenerationError(Exception):
    """Custom exception for traffic generation errors"""
    pass

class TrafficGenerationController:
    """
    Controls traffic generation for demonstration purposes with concurrency control
    and progress monitoring
    """
    
    def __init__(self, lambda_client, dynamodb_table=None):
        """
        Initialize the traffic generation controller
        
        Args:
            lambda_client: AWS Lambda client
            dynamodb_table: DynamoDB table for impact tracking (optional)
        """
        self.lambda_client = lambda_client
        self.dynamodb_table = dynamodb_table
        self.traffic_generator_function = config_manager.aws_config.traffic_generator_function
        self._current_session = None
        self._session_lock = False
        self._baseline_metrics = None
        
    def start_traffic_generation(self, 
                               duration_minutes: int = 5,
                               requests_per_minute: int = 10,
                               endpoint_distribution: Optional[Dict[str, float]] = None) -> bool:
        """
        Start traffic generation with specified parameters
        
        Args:
            duration_minutes: How long to generate traffic (default: 5 minutes)
            requests_per_minute: Rate of request generation (default: 10/minute)
            endpoint_distribution: Distribution of requests across endpoints
                                 (default: equal distribution)
        
        Returns:
            True if traffic generation started successfully, False otherwise
            
        Raises:
            TrafficGenerationError: If generation fails to start
        """
        try:
            # Check for concurrent sessions
            if self._session_lock:
                logger.warning("Traffic generation already in progress")
                return False
            
            # Set default endpoint distribution if not provided
            if endpoint_distribution is None:
                endpoint_distribution = {
                    'auth': 0.4,
                    'profile': 0.3,
                    'search': 0.3
                }
            
            # Validate endpoint distribution
            if not self._validate_endpoint_distribution(endpoint_distribution):
                raise TrafficGenerationError("Invalid endpoint distribution - must sum to 1.0")
            
            # Prepare payload for traffic generator Lambda
            payload = {
                'duration_minutes': duration_minutes,
                'requests_per_minute': requests_per_minute,
                'endpoint_distribution': endpoint_distribution,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Invoke traffic generator Lambda function
            response = self.lambda_client.invoke(
                FunctionName=self.traffic_generator_function,
                InvocationType='Event',  # Asynchronous invocation
                Payload=json.dumps(payload)
            )
            
            # Check response status
            if response['StatusCode'] == 202:  # Accepted for async invocation
                # Set session lock and create status tracking
                self._session_lock = True
                self._current_session = TrafficGenerationStatus(
                    is_active=True,
                    start_time=datetime.utcnow(),
                    estimated_duration=duration_minutes * 60,
                    progress_percentage=0.0,
                    requests_generated=0
                )
                
                logger.info(f"Traffic generation started successfully for {duration_minutes} minutes")
                return True
            else:
                error_msg = f"Unexpected response status: {response['StatusCode']}"
                logger.error(error_msg)
                raise TrafficGenerationError(error_msg)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                error_msg = f"Traffic generator function '{self.traffic_generator_function}' not found"
            else:
                error_msg = f"AWS Lambda error: {str(e)}"
            
            logger.error(error_msg)
            raise TrafficGenerationError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to start traffic generation: {str(e)}"
            logger.error(error_msg)
            raise TrafficGenerationError(error_msg)
    
    def get_generation_status(self) -> TrafficGenerationStatus:
        """
        Get current traffic generation status with progress monitoring
        
        Returns:
            TrafficGenerationStatus object with current status
        """
        if not self._current_session:
            return TrafficGenerationStatus(is_active=False)
        
        # Calculate progress if session is active
        if self._current_session.is_active and self._current_session.start_time:
            elapsed_seconds = (datetime.utcnow() - self._current_session.start_time).total_seconds()
            
            if self._current_session.estimated_duration:
                progress = min(elapsed_seconds / self._current_session.estimated_duration, 1.0)
                self._current_session.progress_percentage = progress * 100
                
                # Check if generation should be complete
                if progress >= 1.0:
                    self._complete_session()
        
        return self._current_session
    
    def stop_traffic_generation(self) -> bool:
        """
        Stop current traffic generation session
        
        Returns:
            True if stopped successfully, False if no active session
        """
        if not self._session_lock or not self._current_session:
            logger.warning("No active traffic generation session to stop")
            return False
        
        try:
            # Note: We can't actually stop an async Lambda invocation once started,
            # but we can mark our local session as stopped
            self._complete_session()
            logger.info("Traffic generation session marked as stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping traffic generation: {str(e)}")
            return False
    
    def is_generation_active(self) -> bool:
        """
        Check if traffic generation is currently active
        
        Returns:
            True if generation is active, False otherwise
        """
        status = self.get_generation_status()
        return status.is_active
    
    def get_estimated_completion_time(self) -> Optional[datetime]:
        """
        Get estimated completion time for current session
        
        Returns:
            Estimated completion datetime, or None if no active session
        """
        if not self._current_session or not self._current_session.start_time:
            return None
        
        if not self._current_session.estimated_duration:
            return None
        
        return self._current_session.start_time + timedelta(
            seconds=self._current_session.estimated_duration
        )
    
    def _validate_endpoint_distribution(self, distribution: Dict[str, float]) -> bool:
        """
        Validate that endpoint distribution sums to 1.0
        
        Args:
            distribution: Dictionary of endpoint names to probability values
            
        Returns:
            True if valid, False otherwise
        """
        if not distribution:
            return False
        
        total = sum(distribution.values())
        return abs(total - 1.0) < 0.001  # Allow small floating point errors
    
    def _complete_session(self):
        """Complete the current traffic generation session"""
        if self._current_session:
            self._current_session.is_active = False
            self._current_session.progress_percentage = 100.0
        
        self._session_lock = False
        logger.info("Traffic generation session completed")
    
    def get_session_history(self) -> list:
        """
        Get history of recent traffic generation sessions
        
        Returns:
            List of recent session results (placeholder for future implementation)
        """
        # Placeholder for future implementation
        # This would query CloudWatch logs or a database for historical data
        return []
    
    def estimate_impact(self, 
                       duration_minutes: int,
                       requests_per_minute: int) -> Dict[str, Any]:
        """
        Estimate the impact of traffic generation on system metrics
        
        Args:
            duration_minutes: Duration of traffic generation
            requests_per_minute: Rate of request generation
            
        Returns:
            Dictionary with estimated impact metrics
        """
        total_requests = duration_minutes * requests_per_minute
        
        # Estimate cold start probability based on current system state
        # This is a simplified estimation - real implementation would use ML models
        estimated_cold_starts = int(total_requests * 0.15)  # Assume 15% cold start rate
        
        return {
            'total_requests_estimated': total_requests,
            'estimated_cold_starts': estimated_cold_starts,
            'estimated_warm_starts': total_requests - estimated_cold_starts,
            'duration_minutes': duration_minutes,
            'requests_per_minute': requests_per_minute,
            'estimated_data_points': total_requests  # Each request generates a data point
        }
    
    def capture_baseline_metrics(self, window_minutes: int = 15) -> Dict[str, Any]:
        """
        Capture baseline request metrics before traffic generation
        
        Args:
            window_minutes: Time window for baseline measurement (default: 15 minutes)
            
        Returns:
            Dictionary with baseline metrics
        """
        try:
            if not self.dynamodb_table:
                logger.warning("DynamoDB table not configured for impact tracking")
                return {'request_count': 0, 'timestamp': datetime.utcnow(), 'window_minutes': window_minutes}
            
            # Calculate time window for baseline
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=window_minutes)
            
            # Query DynamoDB for requests in the baseline window
            request_count = self._count_requests_in_window(start_time, end_time)
            
            baseline_metrics = {
                'request_count': request_count,
                'timestamp': end_time,
                'window_minutes': window_minutes,
                'start_time': start_time,
                'end_time': end_time
            }
            
            # Store baseline for later comparison
            self._baseline_metrics = baseline_metrics
            
            logger.info(f"Captured baseline metrics: {request_count} requests in {window_minutes} minutes")
            return baseline_metrics
            
        except Exception as e:
            logger.error(f"Failed to capture baseline metrics: {str(e)}")
            return {'request_count': 0, 'timestamp': datetime.utcnow(), 'window_minutes': window_minutes}
    
    def measure_traffic_impact(self, window_minutes: int = 15) -> TrafficImpactMetrics:
        """
        Measure the impact of traffic generation by comparing before/after metrics
        
        Args:
            window_minutes: Time window for post-generation measurement (default: 15 minutes)
            
        Returns:
            TrafficImpactMetrics object with comparison data
        """
        try:
            if not self._baseline_metrics:
                logger.warning("No baseline metrics available - capturing current state as baseline")
                self.capture_baseline_metrics(window_minutes)
            
            # Capture post-generation metrics
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=window_minutes)
            
            if self.dynamodb_table:
                post_count = self._count_requests_in_window(start_time, end_time)
            else:
                post_count = 0
                logger.warning("DynamoDB table not configured - using placeholder values")
            
            baseline_count = self._baseline_metrics.get('request_count', 0)
            requests_added = max(0, post_count - baseline_count)
            
            # Calculate percentage increase
            if baseline_count > 0:
                percentage_increase = (requests_added / baseline_count) * 100
            else:
                percentage_increase = 100.0 if requests_added > 0 else 0.0
            
            impact_metrics = TrafficImpactMetrics(
                baseline_request_count=baseline_count,
                post_generation_request_count=post_count,
                requests_added=requests_added,
                percentage_increase=percentage_increase,
                measurement_window_minutes=window_minutes,
                baseline_timestamp=self._baseline_metrics.get('timestamp', datetime.utcnow()),
                post_generation_timestamp=end_time
            )
            
            logger.info(f"Traffic impact: {requests_added} requests added ({percentage_increase:.1f}% increase)")
            return impact_metrics
            
        except Exception as e:
            logger.error(f"Failed to measure traffic impact: {str(e)}")
            # Return empty metrics on error
            return TrafficImpactMetrics(
                baseline_request_count=0,
                post_generation_request_count=0,
                requests_added=0,
                percentage_increase=0.0,
                measurement_window_minutes=window_minutes,
                baseline_timestamp=datetime.utcnow(),
                post_generation_timestamp=datetime.utcnow()
            )
    
    def get_request_count_trend(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get request count trend over specified time period
        
        Args:
            hours: Number of hours to analyze (default: 24)
            
        Returns:
            Dictionary with trend data
        """
        try:
            if not self.dynamodb_table:
                logger.warning("DynamoDB table not configured for trend analysis")
                return {'hourly_counts': [], 'total_requests': 0, 'average_per_hour': 0}
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            # Get hourly request counts
            hourly_counts = []
            current_hour = start_time.replace(minute=0, second=0, microsecond=0)
            
            while current_hour < end_time:
                next_hour = current_hour + timedelta(hours=1)
                count = self._count_requests_in_window(current_hour, next_hour)
                
                hourly_counts.append({
                    'hour': current_hour.isoformat(),
                    'count': count
                })
                
                current_hour = next_hour
            
            total_requests = sum(item['count'] for item in hourly_counts)
            average_per_hour = total_requests / len(hourly_counts) if hourly_counts else 0
            
            return {
                'hourly_counts': hourly_counts,
                'total_requests': total_requests,
                'average_per_hour': average_per_hour,
                'time_period_hours': hours
            }
            
        except Exception as e:
            logger.error(f"Failed to get request count trend: {str(e)}")
            return {'hourly_counts': [], 'total_requests': 0, 'average_per_hour': 0}
    
    def _count_requests_in_window(self, start_time: datetime, end_time: datetime) -> int:
        """
        Count requests in DynamoDB within specified time window
        
        Args:
            start_time: Start of time window
            end_time: End of time window
            
        Returns:
            Number of requests in the time window
        """
        try:
            if not self.dynamodb_table:
                return 0
            
            # Convert datetime to timestamp strings for DynamoDB query
            start_timestamp = start_time.isoformat()
            end_timestamp = end_time.isoformat()
            
            # Query DynamoDB table for records in time window
            # Note: This assumes the table has a timestamp field for filtering
            response = self.dynamodb_table.scan(
                FilterExpression='#ts BETWEEN :start_time AND :end_time',
                ExpressionAttributeNames={
                    '#ts': 'timestamp'  # Adjust field name as needed
                },
                ExpressionAttributeValues={
                    ':start_time': start_timestamp,
                    ':end_time': end_timestamp
                },
                Select='COUNT'
            )
            
            return response.get('Count', 0)
            
        except Exception as e:
            logger.error(f"Failed to count requests in time window: {str(e)}")
            return 0
    
    def reset_impact_tracking(self):
        """Reset baseline metrics for new impact measurement"""
        self._baseline_metrics = None
        logger.info("Impact tracking baseline reset")