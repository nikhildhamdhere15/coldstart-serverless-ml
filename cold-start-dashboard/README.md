# Cold Start Dashboard

A production-ready Streamlit dashboard that showcases the intelligent cold start prevention system with live ML predictions, real-time monitoring, and external access capabilities.

## Features

- **Live ML Predictions**: Real-time cold start risk predictions using SageMaker serverless endpoints
- **System Monitoring**: Real-time AWS service health and performance metrics
- **Data Visualization**: Live data from DynamoDB with trends and statistics
- **Traffic Generation**: Interactive traffic generation for demonstrations
- **Warming Control**: Monitor and control the intelligent Lambda warming system
- **Cost Analytics**: Performance and cost optimization insights
- **External Access**: Public URL sharing for remote examiner access

## Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS credentials configured
- Access to the cold start prevention AWS infrastructure

### Installation

1. Clone or navigate to the dashboard directory:
```bash
cd cold-start-dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your AWS credentials and endpoints
```

4. Run the dashboard:
```bash
streamlit run app.py
```

### Configuration

The dashboard uses environment variables for configuration. Copy `.env.example` to `.env` and update the following:

#### Required AWS Configuration
- `AWS_DEFAULT_REGION`: Your AWS region (default: us-east-1)
- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `DYNAMODB_TABLE_NAME`: DynamoDB table name (default: ETLFeatureData)

#### SageMaker Endpoints
- `XGBOOST_ENDPOINT`: XGBoost serverless endpoint name
- `RF_ENDPOINT`: Random Forest serverless endpoint name

#### Lambda Functions
- `TRAFFIC_GENERATOR_FUNCTION`: Traffic generator Lambda function name
- `DATA_AGGREGATOR_FUNCTION`: Data aggregator Lambda function name
- `INTELLIGENT_WARMER_FUNCTION`: Intelligent warmer Lambda function name

#### Optional Configuration
- `API_GATEWAY_URL`: API Gateway URL for health checks
- `NGROK_AUTH_TOKEN`: ngrok token for external access
- `AUTO_REFRESH_INTERVAL`: Dashboard refresh interval in seconds (default: 30)

## Architecture

The dashboard integrates with the following AWS services:
- **DynamoDB**: ETLFeatureData table for request history
- **SageMaker**: Serverless endpoints for ML predictions
- **Lambda**: Traffic generation and warming functions
- **CloudWatch**: System metrics and monitoring
- **API Gateway**: Health status monitoring

## External Access

For external examiner access, the dashboard supports public URL generation via ngrok:

1. Install ngrok: https://ngrok.com/download
2. Set your ngrok auth token in `.env`
3. The dashboard will automatically generate a public URL

## Development

### Project Structure
```
cold-start-dashboard/
├── app.py              # Main Streamlit application
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variable template
├── .env               # Your environment variables (create from example)
├── services/          # AWS service integrations (to be implemented)
├── components/        # UI components (to be implemented)
└── tests/            # Test files (to be implemented)
```

### Testing

Run tests with:
```bash
pytest tests/
```

Property-based tests use Hypothesis for comprehensive validation.

## Support

For issues or questions:
1. Check the configuration validation in the dashboard
2. Verify AWS credentials and permissions
3. Ensure all required AWS resources are deployed
4. Check CloudWatch logs for detailed error information

## License

This project is part of the intelligent cold start prevention system demonstration.