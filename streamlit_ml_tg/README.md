# ⚡ COLDSTART — Cold Start Prevention Dashboard

> Real-time ML-powered AWS Lambda cold start prevention and monitoring system.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

---

## Overview

COLDSTART is an intelligent orchestration framework that:

- **Predicts** cold start risk using an ensemble of XGBoost (70%) + Random Forest (30%)
- **Gates** warming actions via the Confidence-Based Warming (CBW) mechanism
- **Warms** Lambda functions automatically through IntelligentLambdaWarmer
- **Monitors** the entire pipeline in real-time via a Streamlit dashboard

## Architecture

```
Traffic Generator → S3 → ETL Lambda → DynamoDB
                                          ↓
                    EventBridge (15 min) → DataAggregator Lambda
                                          ↓
                              XGBoost 70% + RF 30% ensemble
                                          ↓
                    P_final ≥ 0.7 AND C ≥ 0.6 (CBW Gate)
                                          ↓
                          IntelligentLambdaWarmer
                                          ↓
                      auth / profile / search — Lambda functions
                                          ↓
                           CloudWatch Metrics
```

## Dashboard Pages

| Page | Description |
|------|-------------|
| Overview | Live KPIs, traffic charts, ML predictions |
| Live Prediction | Manual prediction with custom parameters |
| Traffic Generator | Generate synthetic API traffic to S3 |
| System Status | AWS service health and configuration |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Train ML models

```bash
python save_models.py
```

### 3. Configure AWS credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### 4. Run locally

```bash
streamlit run app.py --server.port 8502
```

## Streamlit Cloud Deployment

Set the following secrets in the Streamlit Cloud dashboard:

```toml
AWS_DEFAULT_REGION      = "ap-south-1"
AWS_ACCESS_KEY_ID       = "your_key"
AWS_SECRET_ACCESS_KEY   = "your_secret"
DYNAMODB_TABLE          = "ETLFeatureData"
S3_BUCKET               = "your-bucket-name"
DATA_AGGREGATOR_FUNCTION = "DataAggregator"
WARMER_FUNCTION         = "IntelligentLambdaWarmer"
```

## Tech Stack

- **ML**: XGBoost, scikit-learn, joblib
- **Cloud**: AWS Lambda, DynamoDB, S3, CloudWatch, EventBridge
- **Frontend**: Streamlit, Plotly
- **Language**: Python 3.9+

## Authors

Abhishek Doke · Nikhil Dhamdhere · Joanna Dharwadkar · Geetanjali Bejjalwar  
Dr. D.Y. Patil College of Engineering and Innovation, 2025–26
