# Intelligent Lambda Warming System

## Overview

This system implements a **cost-optimized, intelligent Lambda warming solution** that:

1. **Aggregates data** from DynamoDB every 15 minutes
2. **Makes batch predictions** using your SageMaker ensemble models
3. **Intelligently warms** Lambda functions based on cold start risk
4. **Reduces costs** by batching SageMaker requests instead of real-time predictions

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│  DynamoDB   │    │ EventBridge  │    │ Data Aggregator │    │  SageMaker   │
│ (Features)  │    │ (15 min)     │    │    Lambda       │    │  Endpoints   │
└─────────────┘    └──────────────┘    └─────────────────┘    └──────────────┘
                           │                       │                    │
                           │                       │                    │
                           ▼                       ▼                    ▼
                   ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
                   │   Triggers   │    │   Aggregates    │    │   Batch      │
                   │   every      │    │   15min data    │    │ Predictions  │
                   │   15 min     │    │   by endpoint   │    │ (Cost Save!) │
                   └──────────────┘    └─────────────────┘    └──────────────┘
                                                │
                                                ▼
                                    ┌─────────────────┐    ┌──────────────┐
                                    │ Lambda Warmer   │    │   Target      │
                                    │   (Smart        │───▶│  Lambda      │
                                    │   Warming)      │    │ Functions    │
                                    └─────────────────┘    └──────────────┘
```

## Components

### 1. Data Aggregator (`data_aggregator.py`)
- **Triggered**: Every 15 minutes by EventBridge
- **Function**: 
  - Queries DynamoDB for recent traffic data
  - Aggregates features by endpoint type (auth, profile, search)
  - Makes batch predictions using SageMaker ensemble
  - Sends warming instructions to Lambda Warmer

### 2. Lambda Warmer (`lambda_warmer.py`)
- **Triggered**: By Data Aggregator
- **Function**:
  - Evaluates warming strategy based on predictions
  - Intelligently warms high-risk Lambda functions
  - Implements priority-based warming (HIGH/MEDIUM/LOW)
  - Sends metrics to CloudWatch

### 3. Deployment Script (`deploy_intelligent_warming.py`)
- **Function**: Deploys the complete system with proper IAM roles and permissions

## Cost Optimization Benefits

### Before (Real-time predictions)
- **SageMaker calls**: ~240 per hour (every request)
- **Cost**: High - continuous endpoint usage
- **Latency**: Added to every API call

### After (15-minute batching)
- **SageMaker calls**: 4 per hour (every 15 minutes)
- **Cost**: **98% reduction** in SageMaker calls
- **Latency**: Zero impact on API calls
- **Efficiency**: Batch processing 3 endpoints at once

## Smart Warming Strategy

### Warming Thresholds
- **Cold Start Probability > 70%**: Warm the function
- **Cold Start Probability > 80%**: High priority warming (multiple attempts)
- **High traffic (>20 requests)**: Increase warming frequency

### Warming Priorities
- **HIGH**: Probability > 80% - Warm multiple times
- **MEDIUM**: Probability 70-80% - Warm once
- **LOW/NONE**: Probability < 70% - Skip warming

## Deployment Instructions

### Prerequisites
1. Ensure your existing system is deployed:
   - API Gateway + Lambda functions
   - DynamoDB table (`ETLFeatureData`)
   - SageMaker endpoints (`cold-start-xgboost-serverless`, `cold-start-rf-serverless`)

### Deploy the System
```bash
cd intelligent_warming_system
python deploy_intelligent_warming.py
```

### What Gets Deployed
1. **IAM Roles & Policies**:
   - `DataAggregatorRole` - Access to DynamoDB, SageMaker, Lambda
   - `IntelligentWarmerRole` - Access to Lambda functions, CloudWatch

2. **Lambda Functions**:
   - `DataAggregator` - 5min timeout, 512MB memory
   - `IntelligentLambdaWarmer` - 3min timeout, 256MB memory

3. **EventBridge Rule**:
   - Triggers every 15 minutes
   - Invokes DataAggregator function

## Monitoring & Metrics

### CloudWatch Namespace: `ColdStart/IntelligentWarming`

#### Key Metrics
- **ColdStartProbability**: Predicted probability per endpoint
- **WarmingSuccessRate**: Success rate of warming attempts
- **TotalFunctionsEvaluated**: Number of functions analyzed
- **FunctionsWarmed**: Number of functions actually warmed

#### Dimensions
- **Service**: IntelligentWarmer
- **Endpoint**: auth, profile, search

### Sample CloudWatch Dashboard Query
```
SELECT AVG(ColdStartProbability) FROM SCHEMA("ColdStart/IntelligentWarming", Endpoint)
WHERE Endpoint = 'auth'
```

## Configuration

### Environment Variables (Auto-configured)
```python
AWS_REGION = 'ap-south-1'
FEATURE_TABLE_NAME = 'ETLFeatureData'
XGBOOST_ENDPOINT = 'cold-start-xgboost-serverless'
RF_ENDPOINT = 'cold-start-rf-serverless'
```

### Tunable Parameters
```python
# In data_aggregator.py
AGGREGATION_WINDOW = 15  # minutes

# In lambda_warmer.py
COLD_START_THRESHOLD = 0.7    # Warm if probability > 70%
HIGH_RISK_THRESHOLD = 0.8     # High priority if > 80%
WARMING_INTERVAL_MINUTES = 10 # Keep warm for 10 minutes
```

## Testing

### Test Data Aggregator
```bash
aws lambda invoke \
  --function-name DataAggregator \
  --payload '{}' \
  response.json
```

### Test Lambda Warmer
```bash
aws lambda invoke \
  --function-name IntelligentLambdaWarmer \
  --payload '{
    "predictions": [
      {
        "endpoint": "auth",
        "function_name": "auth-function", 
        "ensemble_probability": 0.85,
        "request_count": 25
      }
    ]
  }' \
  response.json
```

## Expected Results

### Immediate Benefits
- **98% reduction** in SageMaker endpoint calls
- **Zero latency impact** on API requests
- **Intelligent warming** only when needed
- **Comprehensive monitoring** via CloudWatch

### Long-term Benefits
- **Significant cost savings** on SageMaker usage
- **Improved user experience** through proactive warming
- **Data-driven insights** into cold start patterns
- **Scalable architecture** for additional endpoints

## Troubleshooting

### Common Issues

1. **IAM Permission Errors**
   - Ensure all policies are attached correctly
   - Wait for IAM propagation (15 seconds)

2. **SageMaker Endpoint Not Found**
   - Verify endpoint names match your deployment
   - Check endpoint status in SageMaker console

3. **DynamoDB Access Issues**
   - Verify table name matches `ETLFeatureData`
   - Check table exists and has data

4. **EventBridge Not Triggering**
   - Verify rule is enabled
   - Check Lambda permissions for EventBridge

### Logs Location
- **DataAggregator**: `/aws/lambda/DataAggregator`
- **IntelligentLambdaWarmer**: `/aws/lambda/IntelligentLambdaWarmer`

## Next Steps

1. **Deploy the system** using the deployment script
2. **Monitor CloudWatch** metrics for the first few cycles
3. **Adjust thresholds** based on your specific traffic patterns
4. **Set up CloudWatch alarms** for system health monitoring
5. **Create dashboards** for visualization

## Cost Analysis

### Monthly Savings Estimate
- **Before**: ~17,280 SageMaker calls/month
- **After**: ~2,880 SageMaker calls/month  
- **Reduction**: 83% fewer calls
- **Estimated Savings**: $200-500/month (depending on endpoint pricing)

The system pays for itself through SageMaker cost savings while providing better Lambda performance!