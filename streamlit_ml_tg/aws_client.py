"""
AWS client factory.
Uses explicit credentials if set in .env, otherwise falls back to
~/.aws/credentials (same behaviour as cold-start-dashboard).
"""
import boto3
from config import aws

def _session():
    if aws.access_key_id and aws.secret_access_key:
        return boto3.Session(
            aws_access_key_id=aws.access_key_id,
            aws_secret_access_key=aws.secret_access_key,
            region_name=aws.region,
        )
    # Use default credentials from ~/.aws/credentials or IAM role
    return boto3.Session(region_name=aws.region)

def dynamodb():
    return _session().resource('dynamodb')

def s3():
    return _session().client('s3')

def lambda_client():
    return _session().client('lambda')

def cloudwatch():
    return _session().client('cloudwatch')

def cloudwatch_logs():
    return _session().client('logs')
