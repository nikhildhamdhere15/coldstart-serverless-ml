#!/usr/bin/env python3
"""
AWS Connection Setup Script
Verifies and sets up AWS resources for the Cold Start Dashboard
"""

import boto3
import json
from botocore.exceptions import ClientError, NoCredentialsError
from config import config_manager

def check_aws_credentials():
    """Check if AWS credentials are properly configured"""
    print("🔐 Checking AWS credentials...")
    
    try:
        session = config_manager.get_aws_session()
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        
        print(f"✅ AWS credentials configured successfully")
        print(f"   Account ID: {identity['Account']}")
        print(f"   User/Role: {identity['Arn']}")
        print(f"   Region: {config_manager.aws_config.region}")
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        print("   Please configure AWS credentials using:")
        print("   - AWS CLI: aws configure")
        print("   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("   - IAM roles (if running on EC2)")
        return False
        
    except Exception as e:
        print(f"❌ AWS credentials error: {str(e)}")
        return False

def check_dynamodb_table():
    """Check if DynamoDB table exists and is accessible"""
    print(f"\n📊 Checking DynamoDB table '{config_manager.aws_config.dynamodb_table_name}'...")
    
    try:
        session = config_manager.get_aws_session()
        dynamodb = session.client('dynamodb')
        
        response = dynamodb.describe_table(
            TableName=config_manager.aws_config.dynamodb_table_name
        )
        
        table_status = response['Table']['TableStatus']
        item_count = response['Table']['ItemCount']
        
        print(f"✅ DynamoDB table found")
        print(f"   Status: {table_status}")
        print(f"   Item Count: {item_count:,}")
        print(f"   Region: {config_manager.aws_config.region}")
        
        return table_status == 'ACTIVE'
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"❌ DynamoDB table '{config_manager.aws_config.dynamodb_table_name}' not found")
            print(f"   Please create the table in region: {config_manager.aws_config.region}")
        else:
            print(f"❌ DynamoDB error: {e.response['Error']['Message']}")
        return False
        
    except Exception as e:
        print(f"❌ DynamoDB connection error: {str(e)}")
        return False

def check_sagemaker_endpoints():
    """Check if SageMaker endpoints exist and are in service"""
    print(f"\n🤖 Checking SageMaker endpoints...")
    
    endpoints = [
        config_manager.aws_config.xgboost_endpoint,
        config_manager.aws_config.random_forest_endpoint
    ]
    
    try:
        session = config_manager.get_aws_session()
        sagemaker = session.client('sagemaker')
        
        all_endpoints_ready = True
        
        for endpoint_name in endpoints:
            try:
                response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
                status = response['EndpointStatus']
                
                if status == 'InService':
                    print(f"✅ {endpoint_name}: {status}")
                else:
                    print(f"⚠️  {endpoint_name}: {status}")
                    all_endpoints_ready = False
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ValidationException':
                    print(f"❌ {endpoint_name}: Not found")
                else:
                    print(f"❌ {endpoint_name}: {e.response['Error']['Message']}")
                all_endpoints_ready = False
        
        return all_endpoints_ready
        
    except Exception as e:
        print(f"❌ SageMaker connection error: {str(e)}")
        return False

def check_lambda_functions():
    """Check if Lambda functions exist"""
    print(f"\n⚡ Checking Lambda functions...")
    
    functions = [
        config_manager.aws_config.traffic_generator_function,
        config_manager.aws_config.data_aggregator_function,
        config_manager.aws_config.intelligent_warmer_function
    ]
    
    try:
        session = config_manager.get_aws_session()
        lambda_client = session.client('lambda')
        
        all_functions_exist = True
        
        for function_name in functions:
            try:
                response = lambda_client.get_function(FunctionName=function_name)
                state = response['Configuration']['State']
                
                if state == 'Active':
                    print(f"✅ {function_name}: {state}")
                else:
                    print(f"⚠️  {function_name}: {state}")
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print(f"❌ {function_name}: Not found")
                else:
                    print(f"❌ {function_name}: {e.response['Error']['Message']}")
                all_functions_exist = False
        
        return all_functions_exist
        
    except Exception as e:
        print(f"❌ Lambda connection error: {str(e)}")
        return False

def create_cloudwatch_log_group():
    """Create CloudWatch log group if it doesn't exist"""
    print(f"\n📝 Setting up CloudWatch logging...")
    
    log_group_name = f"/aws/dashboard/cold-start-prevention-dashboard"
    
    try:
        session = config_manager.get_aws_session()
        logs_client = session.client('logs')
        
        # Check if log group exists
        try:
            logs_client.describe_log_groups(logGroupNamePrefix=log_group_name)
            print(f"✅ CloudWatch log group already exists: {log_group_name}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create log group
                logs_client.create_log_group(logGroupName=log_group_name)
                
                # Set retention policy
                logs_client.put_retention_policy(
                    logGroupName=log_group_name,
                    retentionInDays=config_manager.dashboard_config.log_retention_days
                )
                
                print(f"✅ Created CloudWatch log group: {log_group_name}")
                print(f"   Retention: {config_manager.dashboard_config.log_retention_days} days")
                return True
            else:
                print(f"❌ CloudWatch error: {e.response['Error']['Message']}")
                return False
                
    except Exception as e:
        print(f"❌ CloudWatch setup error: {str(e)}")
        return False

def test_sample_operations():
    """Test sample operations to verify everything works"""
    print(f"\n🧪 Testing sample operations...")
    
    # Test DynamoDB query
    try:
        session = config_manager.get_aws_session()
        dynamodb = session.resource('dynamodb')
        table = dynamodb.Table(config_manager.aws_config.dynamodb_table_name)
        
        # Try to scan a few items
        response = table.scan(Limit=1)
        print(f"✅ DynamoDB query test successful")
        print(f"   Sample items available: {response['Count']}")
        
    except Exception as e:
        print(f"⚠️  DynamoDB query test failed: {str(e)}")
    
    # Test SageMaker endpoint (if available)
    try:
        session = config_manager.get_aws_session()
        sagemaker_runtime = session.client('sagemaker-runtime')
        
        # Test with sample data
        test_data = {
            "instances": [[14, 2, 1.0, 0, 1, 0]]  # Sample feature vector
        }
        
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=config_manager.aws_config.xgboost_endpoint,
            ContentType='application/json',
            Body=json.dumps(test_data)
        )
        
        print(f"✅ SageMaker endpoint test successful")
        
    except Exception as e:
        print(f"⚠️  SageMaker endpoint test failed: {str(e)}")

def main():
    """Main setup and verification workflow"""
    print("🚀 Cold Start Dashboard - AWS Connection Setup")
    print("=" * 60)
    
    # Check each component
    credentials_ok = check_aws_credentials()
    if not credentials_ok:
        print("\n❌ Cannot proceed without valid AWS credentials")
        return False
    
    dynamodb_ok = check_dynamodb_table()
    sagemaker_ok = check_sagemaker_endpoints()
    lambda_ok = check_lambda_functions()
    cloudwatch_ok = create_cloudwatch_log_group()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SETUP SUMMARY")
    print("=" * 60)
    
    components = [
        ("AWS Credentials", credentials_ok),
        ("DynamoDB Table", dynamodb_ok),
        ("SageMaker Endpoints", sagemaker_ok),
        ("Lambda Functions", lambda_ok),
        ("CloudWatch Logging", cloudwatch_ok)
    ]
    
    for component, status in components:
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")
    
    all_ready = all(status for _, status in components)
    
    if all_ready:
        print(f"\n🎉 All AWS resources are ready!")
        print(f"   Region: {config_manager.aws_config.region}")
        print(f"   The dashboard should now connect to your real AWS resources.")
        print(f"\n🚀 Restart the dashboard to use live AWS data:")
        print(f"   python deploy_external.py")
        
        # Run sample tests
        test_sample_operations()
        
    else:
        print(f"\n⚠️  Some AWS resources are not ready.")
        print(f"   The dashboard will run in demo mode for missing resources.")
        print(f"   Please deploy missing resources in region: {config_manager.aws_config.region}")
    
    return all_ready

if __name__ == "__main__":
    main()