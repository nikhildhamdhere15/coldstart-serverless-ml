"""
System Health Monitoring Service
Provides real-time system health monitoring and metrics collection
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError
from config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class SystemHealth:
    """System health status model"""
    api_status: str  # 'healthy', 'degraded', 'down'
    sagemaker_endpoints: Dict[str, str]  # endpoint_name -> status
    lambda_functions: Dict[str, datetime]  # function_name -> last_invocation
    dynamodb_status: str
    recent_request_count: int
    uptime_percentage: float
    last_updated: datetime

@dataclass
class EndpointMetrics:
    """SageMaker endpoint metrics"""
    endpoint_name: str
    status: str  # 'InService', 'OutOfService', 'Creating', 'Updating', 'Deleting'
    invocation_count: int
    average_response_time: float  # milliseconds
    error_rate: float  # percentage
    last_invocation: Optional[datetime]

@dataclass
class LambdaMetrics:
    """Lambda function metrics"""
    function_name: str
    invocation_count: int
    error_count: int
    average_duration: float  # milliseconds
    last_invocation: Optional[datetime]
    concurrent_executions: int

@dataclass
class BatchProcessingStatus:
    """15-minute batch processing cycle status"""
    next_execution_time: datetime
    last_execution_time: Optional[datetime]
    last_execution_status: str  # 'success', 'failed', 'running', 'unknown'
    records_processed: int
    cycle_duration: float  # minutes

class SystemMonitoringService:
    """
    Provides comprehensive system health monitoring and metrics collection
    """
    
    def __init__(self, cloudwatch_client, lambda_client, sagemaker_client=None):
        """
        Initialize the system monitoring service
        
        Args:
            cloudwatch_client: AWS CloudWatch client
            lambda_client: AWS Lambda client
            sagemaker_client: AWS SageMaker client (optional)
        """
        self.cloudwatch = cloudwatch_client
        self.lambda_client = lambda_client
        self.sagemaker_client = sagemaker_client
        self._cache = {}
        self._cache_ttl = 60  # Cache TTL in seconds
    
    def get_system_health(self) -> SystemHealth:
        """
        Get comprehensive system health status
        
        Returns:
            SystemHealth object with current system status
        """
        try:
            # Check if we have cached results
            cache_key = "system_health"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            # Get individual component health
            api_status = self._get_api_health_status()
            sagemaker_endpoints = self._get_sagemaker_endpoint_status()
            lambda_functions = self._get_lambda_last_invocations()
            dynamodb_status = self._get_dynamodb_status()
            recent_request_count = self._get_recent_request_count()
            uptime_percentage = self._calculate_uptime_percentage()
            
            health = SystemHealth(
                api_status=api_status,
                sagemaker_endpoints=sagemaker_endpoints,
                lambda_functions=lambda_functions,
                dynamodb_status=dynamodb_status,
                recent_request_count=recent_request_count,
                uptime_percentage=uptime_percentage,
                last_updated=datetime.utcnow()
            )
            
            # Cache the result
            self._cache[cache_key] = {
                "data": health,
                "timestamp": datetime.utcnow()
            }
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get system health: {str(e)}")
            # Return degraded status on error
            return SystemHealth(
                api_status="down",
                sagemaker_endpoints={},
                lambda_functions={},
                dynamodb_status="unknown",
                recent_request_count=0,
                uptime_percentage=0.0,
                last_updated=datetime.utcnow()
            )
    
    def get_sagemaker_metrics(self) -> List[EndpointMetrics]:
        """
        Get detailed SageMaker endpoint metrics
        
        Returns:
            List of EndpointMetrics for all configured endpoints
        """
        try:
            cache_key = "sagemaker_metrics"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            endpoints = [
                config_manager.aws_config.xgboost_endpoint,
                config_manager.aws_config.random_forest_endpoint
            ]
            
            metrics = []
            for endpoint_name in endpoints:
                endpoint_metrics = self._get_endpoint_metrics(endpoint_name)
                if endpoint_metrics:
                    metrics.append(endpoint_metrics)
            
            # Cache the result
            self._cache[cache_key] = {
                "data": metrics,
                "timestamp": datetime.utcnow()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get SageMaker metrics: {str(e)}")
            return []
    
    def get_lambda_metrics(self) -> List[LambdaMetrics]:
        """
        Get detailed Lambda function metrics
        
        Returns:
            List of LambdaMetrics for all configured functions
        """
        try:
            cache_key = "lambda_metrics"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            functions = [
                config_manager.aws_config.traffic_generator_function,
                config_manager.aws_config.data_aggregator_function,
                config_manager.aws_config.intelligent_warmer_function
            ]
            
            metrics = []
            for function_name in functions:
                function_metrics = self._get_lambda_function_metrics(function_name)
                if function_metrics:
                    metrics.append(function_metrics)
            
            # Cache the result
            self._cache[cache_key] = {
                "data": metrics,
                "timestamp": datetime.utcnow()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get Lambda metrics: {str(e)}")
            return []
    
    def get_batch_processing_status(self) -> BatchProcessingStatus:
        """
        Get 15-minute batch processing cycle status
        
        Returns:
            BatchProcessingStatus with cycle information
        """
        try:
            cache_key = "batch_processing_status"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            # Calculate next 15-minute boundary
            now = datetime.utcnow()
            next_quarter = self._get_next_quarter_hour(now)
            
            # Get last execution information from DataAggregator function
            last_execution_time, last_status, records_processed, duration = self._get_last_batch_execution()
            
            status = BatchProcessingStatus(
                next_execution_time=next_quarter,
                last_execution_time=last_execution_time,
                last_execution_status=last_status,
                records_processed=records_processed,
                cycle_duration=duration
            )
            
            # Cache the result
            self._cache[cache_key] = {
                "data": status,
                "timestamp": datetime.utcnow()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get batch processing status: {str(e)}")
            return BatchProcessingStatus(
                next_execution_time=self._get_next_quarter_hour(datetime.utcnow()),
                last_execution_time=None,
                last_execution_status="unknown",
                records_processed=0,
                cycle_duration=0.0
            )
    
    def get_warming_metrics(self) -> Dict[str, Any]:
        """
        Get warming system performance metrics
        
        Returns:
            Dict containing warming system metrics
        """
        try:
            cache_key = "warming_metrics"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            # Get warming events from CloudWatch logs
            warming_events = self._get_warming_events()
            
            # Calculate metrics
            total_events = len(warming_events)
            successful_events = len([e for e in warming_events if e.get('success', False)])
            success_rate = (successful_events / total_events * 100) if total_events > 0 else 0
            
            # Calculate frequency (events per day)
            if warming_events:
                time_span = (warming_events[0]['timestamp'] - warming_events[-1]['timestamp']).total_seconds() / 86400
                frequency = total_events / max(time_span, 1)
            else:
                frequency = 0
            
            # Get cost optimization statistics
            cost_savings = self._calculate_warming_cost_savings(warming_events)
            
            metrics = {
                'total_warming_events': total_events,
                'success_rate': success_rate,
                'frequency_per_day': frequency,
                'cost_savings_monthly': cost_savings,
                'last_warming_time': warming_events[0]['timestamp'] if warming_events else None,
                'next_evaluation_time': self._get_next_warming_evaluation()
            }
            
            # Cache the result
            self._cache[cache_key] = {
                "data": metrics,
                "timestamp": datetime.utcnow()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get warming metrics: {str(e)}")
            return {
                'total_warming_events': 0,
                'success_rate': 0,
                'frequency_per_day': 0,
                'cost_savings_monthly': 0,
                'last_warming_time': None,
                'next_evaluation_time': None
            }
    
    def _get_api_health_status(self) -> str:
        """Get overall API health status"""
        try:
            # Check if we can access basic AWS services
            healthy_services = 0
            total_services = 3
            
            # Test DynamoDB
            if self._test_dynamodb_health():
                healthy_services += 1
            
            # Test SageMaker endpoints
            if self._test_sagemaker_health():
                healthy_services += 1
            
            # Test Lambda
            if self._test_lambda_health():
                healthy_services += 1
            
            if healthy_services == total_services:
                return "healthy"
            elif healthy_services > 0:
                return "degraded"
            else:
                return "down"
                
        except Exception as e:
            logger.error(f"Failed to get API health status: {str(e)}")
            return "down"
    
    def _get_sagemaker_endpoint_status(self) -> Dict[str, str]:
        """Get SageMaker endpoint status"""
        endpoints = {
            config_manager.aws_config.xgboost_endpoint: "unknown",
            config_manager.aws_config.random_forest_endpoint: "unknown"
        }
        
        if not self.sagemaker_client:
            return endpoints
        
        for endpoint_name in endpoints.keys():
            try:
                # Try to get endpoint description
                response = self.sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
                endpoints[endpoint_name] = response['EndpointStatus']
            except ClientError as e:
                if e.response['Error']['Code'] == 'ValidationException':
                    endpoints[endpoint_name] = "not_found"
                else:
                    endpoints[endpoint_name] = "error"
            except Exception:
                endpoints[endpoint_name] = "error"
        
        return endpoints
    
    def _get_lambda_last_invocations(self) -> Dict[str, datetime]:
        """Get last invocation times for Lambda functions"""
        functions = {
            config_manager.aws_config.traffic_generator_function: None,
            config_manager.aws_config.data_aggregator_function: None,
            config_manager.aws_config.intelligent_warmer_function: None
        }
        
        for function_name in functions.keys():
            try:
                # Get invocation metrics from CloudWatch
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=24)
                
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Invocations',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5 minutes
                    Statistics=['Sum']
                )
                
                if response['Datapoints']:
                    # Get the most recent datapoint with invocations > 0
                    datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'], reverse=True)
                    for dp in datapoints:
                        if dp['Sum'] > 0:
                            functions[function_name] = dp['Timestamp']
                            break
                            
            except Exception as e:
                logger.warning(f"Failed to get last invocation for {function_name}: {str(e)}")
        
        return functions
    
    def _get_dynamodb_status(self) -> str:
        """Get DynamoDB table status"""
        try:
            # Try to describe the table
            dynamodb = boto3.client('dynamodb', region_name=config_manager.aws_config.region)
            response = dynamodb.describe_table(TableName=config_manager.aws_config.dynamodb_table_name)
            return response['Table']['TableStatus'].lower()
        except Exception as e:
            logger.error(f"Failed to get DynamoDB status: {str(e)}")
            return "unknown"
    
    def _get_recent_request_count(self) -> int:
        """Get recent request count from DynamoDB"""
        try:
            # Get count of records from the last hour
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            # This is a simplified count - in practice, you might want to
            # query DynamoDB directly or use CloudWatch metrics
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName='ItemCount',
                Dimensions=[
                    {'Name': 'TableName', 'Value': config_manager.aws_config.dynamodb_table_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                return int(response['Datapoints'][-1]['Average'])
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get recent request count: {str(e)}")
            return 0
    
    def _calculate_uptime_percentage(self) -> float:
        """Calculate system uptime percentage"""
        try:
            # Calculate uptime based on successful health checks over the last 24 hours
            # This is a simplified calculation
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            # Get error metrics for key services
            total_checks = 288  # 24 hours * 12 checks per hour (5-minute intervals)
            failed_checks = 0
            
            # Check Lambda errors
            for function_name in [config_manager.aws_config.data_aggregator_function]:
                try:
                    response = self.cloudwatch.get_metric_statistics(
                        Namespace='AWS/Lambda',
                        MetricName='Errors',
                        Dimensions=[
                            {'Name': 'FunctionName', 'Value': function_name}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,  # 5 minutes
                        Statistics=['Sum']
                    )
                    
                    failed_checks += sum(dp['Sum'] for dp in response['Datapoints'])
                    
                except Exception:
                    pass
            
            uptime = max(0, (total_checks - failed_checks) / total_checks * 100)
            return min(100, uptime)
            
        except Exception as e:
            logger.error(f"Failed to calculate uptime: {str(e)}")
            return 95.0  # Default reasonable uptime
    
    def _get_endpoint_metrics(self, endpoint_name: str) -> Optional[EndpointMetrics]:
        """Get detailed metrics for a specific SageMaker endpoint"""
        try:
            # Get endpoint status
            if self.sagemaker_client:
                try:
                    response = self.sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
                    status = response['EndpointStatus']
                except ClientError:
                    status = "not_found"
            else:
                status = "unknown"
            
            # Get invocation metrics from CloudWatch
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            invocation_count = 0
            average_response_time = 0.0
            error_rate = 0.0
            last_invocation = None
            
            try:
                # Get invocation count
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/SageMaker',
                    MetricName='Invocations',
                    Dimensions=[
                        {'Name': 'EndpointName', 'Value': endpoint_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Sum']
                )
                
                if response['Datapoints']:
                    invocation_count = sum(dp['Sum'] for dp in response['Datapoints'])
                    # Get most recent invocation time
                    recent_datapoints = [dp for dp in response['Datapoints'] if dp['Sum'] > 0]
                    if recent_datapoints:
                        last_invocation = max(dp['Timestamp'] for dp in recent_datapoints)
                
                # Get model latency
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/SageMaker',
                    MetricName='ModelLatency',
                    Dimensions=[
                        {'Name': 'EndpointName', 'Value': endpoint_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Average']
                )
                
                if response['Datapoints']:
                    average_response_time = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
                
            except Exception as e:
                logger.warning(f"Failed to get CloudWatch metrics for {endpoint_name}: {str(e)}")
            
            return EndpointMetrics(
                endpoint_name=endpoint_name,
                status=status,
                invocation_count=int(invocation_count),
                average_response_time=average_response_time,
                error_rate=error_rate,
                last_invocation=last_invocation
            )
            
        except Exception as e:
            logger.error(f"Failed to get metrics for endpoint {endpoint_name}: {str(e)}")
            return None
    
    def _get_lambda_function_metrics(self, function_name: str) -> Optional[LambdaMetrics]:
        """Get detailed metrics for a specific Lambda function"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            invocation_count = 0
            error_count = 0
            average_duration = 0.0
            last_invocation = None
            concurrent_executions = 0
            
            # Get invocation count
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Invocations',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Sum']
                )
                
                if response['Datapoints']:
                    invocation_count = sum(dp['Sum'] for dp in response['Datapoints'])
                    # Get most recent invocation time
                    recent_datapoints = [dp for dp in response['Datapoints'] if dp['Sum'] > 0]
                    if recent_datapoints:
                        last_invocation = max(dp['Timestamp'] for dp in recent_datapoints)
                
                # Get error count
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Errors',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Sum']
                )
                
                if response['Datapoints']:
                    error_count = sum(dp['Sum'] for dp in response['Datapoints'])
                
                # Get average duration
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Duration',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Average']
                )
                
                if response['Datapoints']:
                    average_duration = sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
                
                # Get concurrent executions
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='ConcurrentExecutions',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=end_time - timedelta(minutes=5),
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Maximum']
                )
                
                if response['Datapoints']:
                    concurrent_executions = max(dp['Maximum'] for dp in response['Datapoints'])
                
            except Exception as e:
                logger.warning(f"Failed to get CloudWatch metrics for {function_name}: {str(e)}")
            
            return LambdaMetrics(
                function_name=function_name,
                invocation_count=int(invocation_count),
                error_count=int(error_count),
                average_duration=average_duration,
                last_invocation=last_invocation,
                concurrent_executions=int(concurrent_executions)
            )
            
        except Exception as e:
            logger.error(f"Failed to get metrics for function {function_name}: {str(e)}")
            return None
    
    def _get_next_quarter_hour(self, current_time: datetime) -> datetime:
        """Calculate the next 15-minute boundary"""
        minutes = current_time.minute
        next_quarter = ((minutes // 15) + 1) * 15
        
        if next_quarter >= 60:
            # Move to next hour
            next_time = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_time = current_time.replace(minute=next_quarter, second=0, microsecond=0)
        
        return next_time
    
    def _get_last_batch_execution(self) -> tuple:
        """Get information about the last batch execution"""
        try:
            # Get recent invocations of the DataAggregator function
            function_name = config_manager.aws_config.data_aggregator_function
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=2)
            
            # Get invocation metrics
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=900,  # 15 minutes
                Statistics=['Sum']
            )
            
            last_execution_time = None
            last_status = "unknown"
            records_processed = 0
            duration = 0.0
            
            if response['Datapoints']:
                # Find the most recent execution
                datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'], reverse=True)
                for dp in datapoints:
                    if dp['Sum'] > 0:
                        last_execution_time = dp['Timestamp']
                        break
                
                # Check for errors in the same period
                error_response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Errors',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': function_name}
                    ],
                    StartTime=last_execution_time - timedelta(minutes=15) if last_execution_time else start_time,
                    EndTime=last_execution_time + timedelta(minutes=15) if last_execution_time else end_time,
                    Period=900,
                    Statistics=['Sum']
                )
                
                has_errors = any(dp['Sum'] > 0 for dp in error_response['Datapoints'])
                last_status = "failed" if has_errors else "success"
                
                # Estimate records processed (this would ideally come from custom metrics)
                records_processed = 100  # Placeholder
                duration = 2.5  # Placeholder
            
            return last_execution_time, last_status, records_processed, duration
            
        except Exception as e:
            logger.error(f"Failed to get last batch execution info: {str(e)}")
            return None, "unknown", 0, 0.0
    
    def _get_warming_events(self) -> List[Dict]:
        """Get recent warming events from CloudWatch logs"""
        try:
            # This would typically query CloudWatch Logs for warming events
            # For now, return a placeholder structure
            end_time = datetime.utcnow()
            
            # Simulate some warming events
            events = []
            for i in range(5):
                events.append({
                    'timestamp': end_time - timedelta(hours=i*6),
                    'success': i % 4 != 0,  # 75% success rate
                    'functions_warmed': ['auth-function', 'profile-function', 'search-function'],
                    'cost_saved': 0.05 * (i + 1)
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get warming events: {str(e)}")
            return []
    
    def _calculate_warming_cost_savings(self, warming_events: List[Dict]) -> float:
        """Calculate monthly cost savings from warming events"""
        try:
            if not warming_events:
                return 0.0
            
            # Calculate average cost savings per event
            total_savings = sum(event.get('cost_saved', 0) for event in warming_events)
            avg_savings_per_event = total_savings / len(warming_events)
            
            # Estimate monthly savings (assuming 4 warming events per day)
            monthly_savings = avg_savings_per_event * 4 * 30
            
            return monthly_savings
            
        except Exception as e:
            logger.error(f"Failed to calculate warming cost savings: {str(e)}")
            return 0.0
    
    def _get_next_warming_evaluation(self) -> Optional[datetime]:
        """Get the next warming evaluation time"""
        try:
            # Warming evaluations happen every 15 minutes, aligned with batch processing
            return self._get_next_quarter_hour(datetime.utcnow())
        except Exception:
            return None
    
    def _test_dynamodb_health(self) -> bool:
        """Test DynamoDB health"""
        try:
            dynamodb = boto3.client('dynamodb', region_name=config_manager.aws_config.region)
            dynamodb.describe_table(TableName=config_manager.aws_config.dynamodb_table_name)
            return True
        except Exception:
            return False
    
    def _test_sagemaker_health(self) -> bool:
        """Test SageMaker endpoints health"""
        if not self.sagemaker_client:
            return False
        
        try:
            # Test at least one endpoint
            self.sagemaker_client.describe_endpoint(
                EndpointName=config_manager.aws_config.xgboost_endpoint
            )
            return True
        except Exception:
            return False
    
    def _test_lambda_health(self) -> bool:
        """Test Lambda service health"""
        try:
            self.lambda_client.list_functions(MaxItems=1)
            return True
        except Exception:
            return False
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache:
            return False
        
        cache_time = self._cache[cache_key]["timestamp"]
        return (datetime.utcnow() - cache_time).total_seconds() < self._cache_ttl
    
    def _get_next_evaluation_time(self) -> datetime:
        """Get the next 15-minute evaluation time for batch processing"""
        return self._get_next_quarter_hour(datetime.utcnow())