"""
Deploy Intelligent Warming System
Deploys the complete 15-minute batch prediction and warming system
"""

import boto3
import json
import zipfile
import os
import time
from botocore.exceptions import ClientError

# Configuration
AWS_REGION = 'ap-south-1'
BUCKET_NAME = 'clod-start-demo-yourname-unique'  # Use your existing bucket

# Lambda function configurations
FUNCTIONS = {
    'DataAggregator': {
        'filename': 'intelligent_warming_system/data_aggregator.py',
        'handler': 'data_aggregator.lambda_handler',
        'description': 'Aggregates DynamoDB data every 15 minutes and makes batch predictions',
        'timeout': 300,  # 5 minutes
        'memory': 512
    },
    'IntelligentLambdaWarmer': {
        'filename': 'intelligent_warming_system/lambda_warmer.py', 
        'handler': 'lambda_warmer.lambda_handler',
        'description': 'Intelligently warms Lambda functions based on predictions',
        'timeout': 180,  # 3 minutes
        'memory': 256
    }
}

# Initialize AWS clients
iam_client = boto3.client('iam', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)
events_client = boto3.client('events', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

class IntelligentWarmingDeployer:
    def __init__(self):
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        
    def create_iam_role(self, role_name, assume_role_policy, policies):
        """Create IAM role with specified policies"""
        try:
            # Create role
            try:
                role = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                    Description=f'Execution role for {role_name}'
                )
                print(f"✅ Created IAM Role: {role_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    print(f"⚠️ Role {role_name} already exists")
                    role = iam_client.get_role(RoleName=role_name)
                else:
                    raise
            
            role_arn = role['Role']['Arn']
            
            # Attach policies
            for policy_arn in policies:
                try:
                    iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
                    print(f"✅ Attached policy {policy_arn}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'EntityAlreadyExists':
                        print(f"⚠️ Policy attachment issue: {e}")
            
            # Wait for IAM propagation
            print("⏳ Waiting for IAM propagation...")
            time.sleep(15)
            
            return role_arn
            
        except Exception as e:
            print(f"❌ Error creating IAM role {role_name}: {e}")
            raise
    
    def create_custom_policy(self, policy_name, policy_document):
        """Create custom IAM policy"""
        try:
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{policy_name}"
            
            try:
                iam_client.create_policy(
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document)
                )
                print(f"✅ Created custom policy: {policy_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    print(f"⚠️ Policy {policy_name} already exists")
                else:
                    raise
            
            return policy_arn
            
        except Exception as e:
            print(f"❌ Error creating policy {policy_name}: {e}")
            raise
    
    def create_lambda_package(self, function_name, filename):
        """Create deployment package for Lambda function"""
        try:
            zip_filename = f"{function_name}.zip"
            
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(filename, os.path.basename(filename))
            
            print(f"✅ Created deployment package: {zip_filename}")
            return zip_filename
            
        except Exception as e:
            print(f"❌ Error creating package for {function_name}: {e}")
            raise
    
    def deploy_lambda_function(self, function_name, config, role_arn):
        """Deploy Lambda function"""
        try:
            # Create deployment package
            zip_file = self.create_lambda_package(function_name, config['filename'])
            
            # Read zip file
            with open(zip_file, 'rb') as f:
                zip_content = f.read()
            
            # Deploy function
            try:
                response = lambda_client.create_function(
                    FunctionName=function_name,
                    Runtime='python3.9',
                    Role=role_arn,
                    Handler=config['handler'],
                    Code={'ZipFile': zip_content},
                    Description=config['description'],
                    Timeout=config['timeout'],
                    MemorySize=config['memory'],
                    Publish=True,
                    Environment={
                        'Variables': {
                            'FEATURE_TABLE_NAME': 'ETLFeatureData',
                            'XGBOOST_ENDPOINT': 'cold-start-xgboost-serverless',
                            'RF_ENDPOINT': 'cold-start-rf-serverless'
                        }
                    }
                )
                print(f"✅ Deployed Lambda function: {function_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceConflictException':
                    print(f"⚠️ Function {function_name} already exists, updating...")
                    response = lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_content,
                        Publish=True
                    )
                    # Update configuration
                    lambda_client.update_function_configuration(
                        FunctionName=function_name,
                        Timeout=config['timeout'],
                        MemorySize=config['memory'],
                        Environment={
                            'Variables': {
                                'FEATURE_TABLE_NAME': 'ETLFeatureData',
                                'XGBOOST_ENDPOINT': 'cold-start-xgboost-serverless',
                                'RF_ENDPOINT': 'cold-start-rf-serverless'
                            }
                        }
                    )
                else:
                    raise
            
            # Clean up zip file
            os.remove(zip_file)
            
            return response['FunctionArn']
            
        except Exception as e:
            print(f"❌ Error deploying {function_name}: {e}")
            raise
    
    def create_eventbridge_rule(self):
        """Create EventBridge rule for 15-minute schedule"""
        try:
            rule_name = 'IntelligentWarmingSchedule'
            
            # Create rule
            try:
                events_client.put_rule(
                    Name=rule_name,
                    ScheduleExpression='rate(15 minutes)',
                    Description='Triggers data aggregation and prediction every 15 minutes',
                    State='ENABLED'
                )
                print(f"✅ Created EventBridge rule: {rule_name}")
            except ClientError as e:
                print(f"⚠️ EventBridge rule issue: {e}")
            
            return rule_name
            
        except Exception as e:
            print(f"❌ Error creating EventBridge rule: {e}")
            raise
    
    def add_eventbridge_target(self, rule_name, function_arn):
        """Add Lambda function as EventBridge target"""
        try:
            # Add permission for EventBridge to invoke Lambda
            try:
                lambda_client.add_permission(
                    FunctionName='DataAggregator',
                    StatementId='AllowEventBridgeInvoke',
                    Action='lambda:InvokeFunction',
                    Principal='events.amazonaws.com',
                    SourceArn=f"arn:aws:events:{AWS_REGION}:{self.account_id}:rule/{rule_name}"
                )
                print("✅ Added EventBridge invoke permission")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceConflictException':
                    print(f"⚠️ Permission issue: {e}")
            
            # Add target
            events_client.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': '1',
                        'Arn': function_arn
                    }
                ]
            )
            print(f"✅ Added Lambda target to EventBridge rule")
            
        except Exception as e:
            print(f"❌ Error adding EventBridge target: {e}")
            raise
    
    def deploy_complete_system(self):
        """Deploy the complete intelligent warming system"""
        try:
            print("🚀 Starting Intelligent Warming System Deployment")
            print("=" * 60)
            
            # Step 1: Create custom policies
            print("\n📋 Creating IAM policies...")
            
            # Data Aggregator policy
            aggregator_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:Scan",
                            "dynamodb:Query",
                            "dynamodb:GetItem"
                        ],
                        "Resource": f"arn:aws:dynamodb:{AWS_REGION}:{self.account_id}:table/ETLFeatureData"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "sagemaker:InvokeEndpoint"
                        ],
                        "Resource": [
                            f"arn:aws:sagemaker:{AWS_REGION}:{self.account_id}:endpoint/cold-start-xgboost-serverless",
                            f"arn:aws:sagemaker:{AWS_REGION}:{self.account_id}:endpoint/cold-start-rf-serverless"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "lambda:InvokeFunction"
                        ],
                        "Resource": f"arn:aws:lambda:{AWS_REGION}:{self.account_id}:function:IntelligentLambdaWarmer"
                    }
                ]
            }
            
            aggregator_policy_arn = self.create_custom_policy(
                'DataAggregatorPolicy', 
                aggregator_policy
            )
            
            # Warmer policy
            warmer_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "lambda:InvokeFunction"
                        ],
                        "Resource": [
                            f"arn:aws:lambda:{AWS_REGION}:{self.account_id}:function:auth-function",
                            f"arn:aws:lambda:{AWS_REGION}:{self.account_id}:function:profile-function",
                            f"arn:aws:lambda:{AWS_REGION}:{self.account_id}:function:search-function"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:PutMetricData"
                        ],
                        "Resource": "*"
                    }
                ]
            }
            
            warmer_policy_arn = self.create_custom_policy(
                'IntelligentWarmerPolicy',
                warmer_policy
            )
            
            # Step 2: Create IAM roles
            print("\n🔐 Creating IAM roles...")
            
            lambda_assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }
                ]
            }
            
            # Data Aggregator role
            aggregator_role_arn = self.create_iam_role(
                'DataAggregatorRole',
                lambda_assume_role_policy,
                [
                    'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
                    aggregator_policy_arn
                ]
            )
            
            # Warmer role
            warmer_role_arn = self.create_iam_role(
                'IntelligentWarmerRole',
                lambda_assume_role_policy,
                [
                    'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
                    warmer_policy_arn
                ]
            )
            
            # Step 3: Deploy Lambda functions
            print("\n⚡ Deploying Lambda functions...")
            
            aggregator_arn = self.deploy_lambda_function(
                'DataAggregator',
                FUNCTIONS['DataAggregator'],
                aggregator_role_arn
            )
            
            warmer_arn = self.deploy_lambda_function(
                'IntelligentLambdaWarmer',
                FUNCTIONS['IntelligentLambdaWarmer'],
                warmer_role_arn
            )
            
            # Step 4: Create EventBridge schedule
            print("\n⏰ Setting up EventBridge schedule...")
            
            rule_name = self.create_eventbridge_rule()
            self.add_eventbridge_target(rule_name, aggregator_arn)
            
            # Step 5: Test the system
            print("\n🧪 Testing the system...")
            
            test_response = lambda_client.invoke(
                FunctionName='DataAggregator',
                InvocationType='RequestResponse',
                Payload=json.dumps({})
            )
            
            if test_response['StatusCode'] == 200:
                print("✅ System test successful!")
            else:
                print("⚠️ System test had issues")
            
            print("\n" + "=" * 60)
            print("🎉 INTELLIGENT WARMING SYSTEM DEPLOYED SUCCESSFULLY!")
            print("=" * 60)
            print(f"📊 Data Aggregator: {aggregator_arn}")
            print(f"🔥 Lambda Warmer: {warmer_arn}")
            print(f"⏰ Schedule: Every 15 minutes")
            print(f"💰 Cost Optimization: Batch predictions reduce SageMaker costs")
            print(f"🎯 Smart Warming: Only warm high-risk Lambda functions")
            print("\n📈 Monitor in CloudWatch:")
            print("   - Namespace: ColdStart/IntelligentWarming")
            print("   - Metrics: ColdStartProbability, WarmingSuccessRate")
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return False

def main():
    """Main deployment function"""
    deployer = IntelligentWarmingDeployer()
    success = deployer.deploy_complete_system()
    
    if success:
        print("\n✅ Your intelligent warming system is ready!")
        print("The system will automatically:")
        print("  1. Analyze DynamoDB data every 15 minutes")
        print("  2. Make batch predictions to reduce costs")
        print("  3. Intelligently warm high-risk Lambda functions")
        print("  4. Send metrics to CloudWatch for monitoring")
    else:
        print("\n❌ Deployment failed! Check the logs above.")

if __name__ == "__main__":
    main()