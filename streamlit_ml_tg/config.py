"""
Configuration — reads from Streamlit secrets (cloud) or .env (local).
Falls back to default AWS credentials (~/.aws/credentials) if no keys set.
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

class AWSConfig:
    region                   = _get("AWS_DEFAULT_REGION", "ap-south-1")
    # Leave blank to use ~/.aws/credentials (same as cold-start-dashboard)
    access_key_id            = _get("AWS_ACCESS_KEY_ID", "")
    secret_access_key        = _get("AWS_SECRET_ACCESS_KEY", "")
    dynamodb_table           = _get("DYNAMODB_TABLE", "ETLFeatureData")
    s3_bucket                = _get("S3_BUCKET", "clod-start-demo-yourname-unique")
    data_aggregator_function = _get("DATA_AGGREGATOR_FUNCTION", "DataAggregator")
    warmer_function          = _get("WARMER_FUNCTION", "IntelligentLambdaWarmer")
    cloudwatch_namespace     = "ColdStart/IntelligentWarming"

aws = AWSConfig()
