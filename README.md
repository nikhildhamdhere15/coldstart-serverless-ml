# COLDSTART: Intelligent AWS Lambda Cold-Start Prevention

COLDSTART is an ML-powered serverless orchestration system that predicts AWS
Lambda cold-start risk and proactively warms only the functions that need it.
The goal is to reduce user-facing latency without continuously keeping
unnecessary Lambda resources active.

## Problem

When an AWS Lambda function has been idle, AWS may need to create and
initialize a new execution environment before handling the next request. This
is known as a **cold start** and can add noticeable latency to an API request.

Keeping every function warm can reduce this latency, but it increases cost and
can waste resources. COLDSTART addresses this latency-versus-cost trade-off by
combining traffic history, temporal features, user behavior, and system
telemetry to predict when warming is worthwhile.

## How It Works

```text
Traffic Generator
        |
        v
      S3  --->  ETL Lambda  --->  DynamoDB feature data
                                      |
                                      v
                         EventBridge scheduled trigger
                                      |
                                      v
                            DataAggregator Lambda
                                      |
                                      v
                    XGBoost (70%) + Random Forest (30%)
                                      |
                                      v
                          Confidence-Based Warming
                                      |
                                      v
                         IntelligentLambdaWarmer
                          /         |          \
                         v          v           v
                       Auth      Profile      Search
                                      |
                                      v
                              CloudWatch metrics
                                      |
                                      v
                             Streamlit dashboard
```

The ensemble prediction is combined with warming thresholds and prediction
confidence. High-risk functions receive higher-priority warming actions, while
low-risk functions are left idle to avoid unnecessary cost.

## Main Features

- ML-based cold-start risk prediction
- XGBoost and Random Forest ensemble inference
- Confidence-Based Warming (CBW) decision logic
- Scheduled batch prediction through EventBridge
- Automated Lambda warming for auth, profile, and search APIs
- S3-to-DynamoDB feature ETL pipeline
- CloudWatch monitoring and operational metrics
- Streamlit dashboard for predictions, traffic, system health, and warming
- Unit, integration, system, performance, and user-acceptance tests

## Repository Structure

| Directory or file | Purpose |
| --- | --- |
| `cold-start-dashboard/` | Streamlit monitoring and control dashboard |
| `intelligent_warming_system/` | Data aggregation and intelligent Lambda warming |
| `auth-function/` | Example authentication Lambda |
| `profile-function/` | Example profile Lambda |
| `search-function/` | Example search Lambda |
| `ETL S3 to DynamoDB/` | ETL code that stores traffic features |
| `cold_start_ensemble_deployment/` | SageMaker ensemble deployment scripts |
| `intelligence_layer/` | Warming decision and orchestration logic |
| `project_testing/` | Project test suite |
| `streamlit_ml_tg/` | Streamlit traffic-generation and prediction application |
| `traffic_generator.py` | Synthetic traffic generation |
| `deploy_foundation.py` | Foundation AWS deployment script |
| `complete model/` | Model deployment and evaluation scripts |
| `COLDSTART_Updated_Paper.md` | Technical research paper |

## Technology Stack

- **Language:** Python
- **Machine learning:** XGBoost, scikit-learn, joblib
- **Cloud:** AWS Lambda, S3, DynamoDB, SageMaker, EventBridge, CloudWatch
- **Dashboard:** Streamlit and Plotly
- **Testing:** pytest and Hypothesis

## Requirements

Before deployment, configure:

- Python 3.8 or newer
- An AWS account and credentials
- An AWS region
- Permissions for Lambda, S3, DynamoDB, SageMaker, EventBridge, and CloudWatch
- A DynamoDB feature table, commonly named `ETLFeatureData`
- SageMaker endpoints for the XGBoost and Random Forest models

Do not commit AWS credentials or private keys. Copy the relevant
`.env.example` file to `.env` locally and fill in the values on your machine.
The repository ignores `.env`, `.pem`, and `.key` files.

## Running the Dashboard

```bash
cd cold-start-dashboard
pip install -r requirements.txt
streamlit run app.py
```

The dashboard expects AWS configuration and resource names in environment
variables. Refer to `cold-start-dashboard/.env.example` for the available
settings.

## Deploying Intelligent Warming

The intelligent warming system aggregates recent traffic, performs scheduled
batch predictions, and invokes warming actions when the predicted risk passes
the configured thresholds.

```bash
cd intelligent_warming_system
python deploy_intelligent_warming.py
```

Typical configuration includes:

- Aggregation window: 15 minutes
- Warming threshold: 70% predicted cold-start probability
- High-risk threshold: 80% predicted probability
- Target functions: auth, profile, and search

Review the deployment scripts and AWS account configuration before running
them. Deployment may create or modify AWS resources and incur cloud charges.

## Testing

From the repository root:

```bash
python project_testing/UT1_data_collection.py
python project_testing/run_all_tests.py
```

The test suite covers data collection, preprocessing, prediction and warming
logic, AWS integrations, end-to-end workflows, performance, and dashboard
connectivity.

## Security and Large Files

Environment files, private keys, caches, and local runtime files are excluded
through `.gitignore`. The bundled `complete model/openJdk-25/` runtime is also
excluded because it is an unnecessary large binary dependency. Install a
compatible JDK locally only if one of the model deployment workflows requires
it.

## Research Context

The project is documented in
[`COLDSTART_Updated_Paper.md`](COLDSTART_Updated_Paper.md), which describes the
Multi-Modal Prediction architecture, ensemble prediction engine,
Confidence-Based Warming mechanism, and cost-aware serverless orchestration
approach.

## License

This repository is an academic and demonstration project. Review the
copyright and project ownership information in
[`project_copyright_details.tex`](project_copyright_details.tex) before
redistributing or using the project commercially.
