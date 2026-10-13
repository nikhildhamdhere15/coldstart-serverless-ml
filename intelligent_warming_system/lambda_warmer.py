"""
Intelligent Lambda Warmer Function
Receives predictions from Data Aggregator and intelligently warms Lambda functions
Implements smart warming strategies to optimize cost vs performance
"""

import boto3
import json
import time
from datetime import datetime, timedelta
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
lambda_client = boto3.client('lambda')
cloudwatch = boto3.client('cloudwatch')

# Configuration
LAMBDA_FUNCTIONS = {
    'auth': 'auth-function',
    'profile': 'profile-function', 
    'search': 'search-function'
}

# Warming thresholds
COLD_START_THRESHOLD = 0.7  # Warm if probability > 70%
HIGH_RISK_THRESHOLD = 0.8   # High priority warming if > 80%
WARMING_INTERVAL_MINUTES = 10  # Keep warm for 10 minutes

class IntelligentWarmer:
    def __init__(self):
        self.current_time = datetime.now()
        
    def evaluate_warming_strategy(self, predictions):
        """
        Evaluate which Lambda functions need warming based on predictions
        Returns warming plan with priorities and strategies
        """
        try:
            warming_plan = []
            
            for prediction in predictions:
                endpoint = prediction['endpoint']
                function_name = prediction['function_name']
                probability = prediction['ensemble_probability']
                request_count = prediction['request_count']
                
                # Determine if warming is needed
                if probability > COLD_START_THRESHOLD:
                    
                    # Determine warming priority
                    if probability > HIGH_RISK_THRESHOLD:
                        priority = 'HIGH'
                        warming_frequency = 2  # Warm every 5 minutes for 10 minutes
                    else:
                        priority = 'MEDIUM'
                        warming_frequency = 1  # Warm once
                    
                    # Adjust based on request volume
                    if request_count > 20:
                        warming_frequency += 1  # More frequent warming for high traffic
                    
                    warming_plan.append({
                        'endpoint': endpoint,
                        'function_name': function_name,
                        'probability': probability,
                        'priority': priority,
                        'warming_frequency': warming_frequency,
                        'request_count': request_count,
                        'action': 'WARM',
                        'reason': f"Cold start probability: {probability:.3f}"
                    })
                    
                    logger.info(f"Planning to warm {function_name} - Priority: {priority}, Probability: {probability:.3f}")
                    
                else:
                    warming_plan.append({
                        'endpoint': endpoint,
                        'function_name': function_name,
                        'probability': probability,
                        'priority': 'NONE',
                        'warming_frequency': 0,
                        'request_count': request_count,
                        'action': 'SKIP',
                        'reason': f"Low cold start risk: {probability:.3f}"
                    })
                    
                    logger.info(f"Skipping {function_name} - Low risk: {probability:.3f}")
            
            return warming_plan
            
        except Exception as e:
            logger.error(f"Error evaluating warming strategy: {str(e)}")
            raise
    
    def warm_lambda_function(self, function_name, warming_frequency=1):
        """
        Warm a Lambda function by invoking it with warming payload
        """
        try:
            warming_payload = {
                'warming': True,
                'timestamp': self.current_time.isoformat(),
                'warmer': 'IntelligentWarmer'
            }
            
            success_count = 0
            
            for i in range(warming_frequency):
                try:
                    response = lambda_client.invoke(
                        FunctionName=function_name,
                        InvocationType='RequestResponse',  # Synchronous to ensure warming
                        Payload=json.dumps(warming_payload)
                    )
                    
                    # Check if warming was successful
                    if response['StatusCode'] == 200:
                        success_count += 1
                        logger.info(f"Successfully warmed {function_name} (attempt {i+1}/{warming_frequency})")
                    else:
                        logger.warning(f"Warming attempt {i+1} failed for {function_name}: Status {response['StatusCode']}")
                    
                    # Small delay between warming attempts
                    if i < warming_frequency - 1:
                        time.sleep(2)
                        
                except Exception as e:
                    logger.error(f"Error in warming attempt {i+1} for {function_name}: {str(e)}")
                    continue
            
            return {
                'function_name': function_name,
                'attempts': warming_frequency,
                'successful': success_count,
                'success_rate': success_count / warming_frequency if warming_frequency > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error warming {function_name}: {str(e)}")
            return {
                'function_name': function_name,
                'attempts': warming_frequency,
                'successful': 0,
                'success_rate': 0,
                'error': str(e)
            }
    
    def execute_warming_plan(self, warming_plan):
        """
        Execute the warming plan for all Lambda functions
        """
        try:
            warming_results = []
            
            # Sort by priority (HIGH first)
            sorted_plan = sorted(warming_plan, 
                               key=lambda x: {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'NONE': 0}[x['priority']], 
                               reverse=True)
            
            for plan in sorted_plan:
                if plan['action'] == 'WARM':
                    function_name = plan['function_name']
                    warming_frequency = plan['warming_frequency']
                    
                    logger.info(f"Executing warming for {function_name} with frequency {warming_frequency}")
                    
                    result = self.warm_lambda_function(function_name, warming_frequency)
                    result.update({
                        'endpoint': plan['endpoint'],
                        'priority': plan['priority'],
                        'probability': plan['probability'],
                        'reason': plan['reason']
                    })
                    
                    warming_results.append(result)
                    
                else:
                    # Record skipped functions
                    warming_results.append({
                        'function_name': plan['function_name'],
                        'endpoint': plan['endpoint'],
                        'action': 'SKIPPED',
                        'priority': plan['priority'],
                        'probability': plan['probability'],
                        'reason': plan['reason'],
                        'attempts': 0,
                        'successful': 0,
                        'success_rate': 0
                    })
            
            return warming_results
            
        except Exception as e:
            logger.error(f"Error executing warming plan: {str(e)}")
            raise
    
    def send_metrics_to_cloudwatch(self, warming_results, predictions):
        """
        Send warming metrics to CloudWatch for monitoring
        """
        try:
            metrics = []
            
            # Overall metrics
            total_functions = len(warming_results)
            warmed_functions = sum(1 for r in warming_results if r.get('successful', 0) > 0)
            
            metrics.extend([
                {
                    'MetricName': 'TotalFunctionsEvaluated',
                    'Value': total_functions,
                    'Unit': 'Count',
                    'Dimensions': [{'Name': 'Service', 'Value': 'IntelligentWarmer'}]
                },
                {
                    'MetricName': 'FunctionsWarmed',
                    'Value': warmed_functions,
                    'Unit': 'Count',
                    'Dimensions': [{'Name': 'Service', 'Value': 'IntelligentWarmer'}]
                }
            ])
            
            # Per-function metrics
            for result in warming_results:
                endpoint = result.get('endpoint', 'unknown')
                probability = result.get('probability', 0)
                success_rate = result.get('success_rate', 0)
                
                metrics.extend([
                    {
                        'MetricName': 'ColdStartProbability',
                        'Value': probability,
                        'Unit': 'None',
                        'Dimensions': [
                            {'Name': 'Endpoint', 'Value': endpoint},
                            {'Name': 'Service', 'Value': 'IntelligentWarmer'}
                        ]
                    },
                    {
                        'MetricName': 'WarmingSuccessRate',
                        'Value': success_rate,
                        'Unit': 'Percent',
                        'Dimensions': [
                            {'Name': 'Endpoint', 'Value': endpoint},
                            {'Name': 'Service', 'Value': 'IntelligentWarmer'}
                        ]
                    }
                ])
            
            # Send metrics in batches (CloudWatch limit is 20 per call)
            for i in range(0, len(metrics), 20):
                batch = metrics[i:i+20]
                cloudwatch.put_metric_data(
                    Namespace='ColdStart/IntelligentWarming',
                    MetricData=batch
                )
            
            logger.info(f"Sent {len(metrics)} metrics to CloudWatch")
            return True
            
        except Exception as e:
            logger.error(f"Error sending metrics to CloudWatch: {str(e)}")
            return False

def lambda_handler(event, context):
    """
    Main Lambda handler - receives predictions from Data Aggregator
    """
    try:
        logger.info("Starting intelligent Lambda warming process")
        
        # Extract predictions from event
        predictions = event.get('predictions', [])
        
        if not predictions:
            logger.warning("No predictions received")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No predictions to process',
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        logger.info(f"Received {len(predictions)} predictions")
        
        warmer = IntelligentWarmer()
        
        # Step 1: Evaluate warming strategy
        warming_plan = warmer.evaluate_warming_strategy(predictions)
        
        # Step 2: Execute warming plan
        warming_results = warmer.execute_warming_plan(warming_plan)
        
        # Step 3: Send metrics to CloudWatch
        metrics_sent = warmer.send_metrics_to_cloudwatch(warming_results, predictions)
        
        # Calculate summary statistics
        total_warmed = sum(1 for r in warming_results if r.get('successful', 0) > 0)
        total_attempts = sum(r.get('attempts', 0) for r in warming_results)
        total_successful = sum(r.get('successful', 0) for r in warming_results)
        
        overall_success_rate = (total_successful / total_attempts * 100) if total_attempts > 0 else 0
        
        logger.info(f"Warming complete - {total_warmed} functions warmed, {overall_success_rate:.1f}% success rate")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Intelligent warming completed successfully',
                'summary': {
                    'functions_evaluated': len(predictions),
                    'functions_warmed': total_warmed,
                    'total_warming_attempts': total_attempts,
                    'successful_warming_attempts': total_successful,
                    'overall_success_rate': f"{overall_success_rate:.1f}%",
                    'metrics_sent_to_cloudwatch': metrics_sent
                },
                'warming_results': warming_results,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

# For local testing
if __name__ == "__main__":
    # Test the warmer locally
    test_event = {
        'predictions': [
            {
                'endpoint': 'auth',
                'function_name': 'auth-function',
                'ensemble_probability': 0.85,
                'request_count': 25
            },
            {
                'endpoint': 'profile',
                'function_name': 'profile-function',
                'ensemble_probability': 0.45,
                'request_count': 10
            }
        ]
    }
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))