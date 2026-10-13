import boto3
import json
import os
import time
import zipfile
from botocore.exceptions import ClientError

# --- CONFIGURATION (UPDATE THESE) ---
AWS_REGION = 'ap-south-1' 
BUCKET_NAME = 'clod-start-demo-yourname-unique' # !!! MUST BE GLOBALLY UNIQUE !!!
API_NAME = 'CLODStartDemoAPI'
# ---

# Define the functions and their properties for deployment
FUNCTIONS = {
    'auth-function': {'path': 'auth-function', 'handler': 'lambda_function.lambda_handler', 'runtime': 'python3.10', 'method': 'POST', 'resource': '/auth'},
    'profile-function': {'path': 'profile-function', 'handler': 'lambda_function.lambda_handler', 'runtime': 'python3.10', 'method': 'GET', 'resource': '/profile'},
    'search-function': {'path': 'search-function', 'handler': 'lambda_function.lambda_handler', 'runtime': 'python3.10', 'method': 'GET', 'resource': '/search'},
}

# --- BOTO3 CLIENTS ---
iam_client = boto3.client('iam', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)
apigateway_client = boto3.client('apigateway', region_name=AWS_REGION)

# --- HELPER FUNCTIONS ---

def create_zip_file(source_dir, output_filename):
    """Zips the Lambda function code for deployment."""
    output_path = os.path.join(os.getcwd(), output_filename)
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file == 'lambda_function.py':
                    # Only zip the lambda_function.py
                    zipf.write(os.path.join(root, file), 'lambda_function.py')
    return output_path

def create_iam_role(role_name, assume_role_policy, policy_arn=None):
    """Creates an IAM role and attaches a policy (e.g., S3 Full Access)."""
    try:
        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        print(f"✅ Created IAM Role: {role_name}")
        if policy_arn:
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print(f"✅ Attached policy {policy_arn} to {role_name}")
        return role['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"⚠️ Role {role_name} already exists. Retrieving ARN.")
            return iam_client.get_role(RoleName=role_name)['Role']['Arn']
        else:
            print(f"❌ Error creating IAM role {role_name}: {e}")
            return None

def deploy_lambda_function(name, func_config, role_arn):
    """Deploys a Lambda function using the zipped code."""
    zip_file_name = f"{name}.zip"
    zip_path = create_zip_file(func_config['path'], zip_file_name)
    
    with open(zip_path, 'rb') as f:
        zipped_code = f.read()
    
    try:
        response = lambda_client.create_function(
            FunctionName=name,
            Runtime=func_config['runtime'],
            Role=role_arn,
            Handler=func_config['handler'],
            Code={'ZipFile': zipped_code}, # Use ZipFile for deployment
            Timeout=30,
            MemorySize=512,
            Publish=True
        )
        print(f"✅ Deployed Lambda Function: {name}")
        os.remove(zip_path)
        return response['FunctionArn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print(f"⚠️ Function {name} already exists. Skipping deployment.")
            os.remove(zip_path)
            return lambda_client.get_function(FunctionName=name)['Configuration']['FunctionArn']
        else:
            print(f"❌ Error deploying Lambda {name}: {e}")
            os.remove(zip_path)
            return None
    except Exception as e:
        print(f"❌ Unexpected Error during Lambda deployment: {e}")
        os.remove(zip_path)
        return None

def setup_apigateway(lambda_arns, role_arn):
    """Creates the API Gateway, resources, methods, and integrations."""
    try:
        # 1. Create REST API
        api = apigateway_client.create_rest_api(name=API_NAME, description='CLOD START Demo API')
        api_id = api['id']
        root_resource_id = apigateway_client.get_resources(restApiId=api_id)['items'][0]['id']
        print(f"✅ Created API Gateway: {api_id}")

        # 2. Deploy Endpoints and Integration
        for func_name, config in FUNCTIONS.items():
            lambda_arn = lambda_arns.get(func_name)
            if not lambda_arn: continue
            
            # Create Resource (e.g., /auth, /profile)
            resource = apigateway_client.create_resource(
                restApiId=api_id,
                parentId=root_resource_id,
                pathPart=config['resource'].strip('/')
            )
            resource_id = resource['id']

            # Setup Method (e.g., POST, GET)
            apigateway_client.put_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod=config['method'],
                authorizationType='NONE'
            )
            
            # Setup AWS_PROXY Integration
            integration_uri = (
                f"arn:aws:apigateway:{AWS_REGION}:lambda:path/2015-03-31/functions/"
                f"{lambda_arn}/invocations"
            )

            apigateway_client.put_integration(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod=config['method'],
                type='AWS_PROXY',
                integrationHttpMethod='POST', # Lambda integrations use POST internally
                uri=integration_uri,
                credentials=role_arn # Role used to call the Lambda
            )
            
            # Grant API Gateway permission to invoke Lambda
            account_id = boto3.client('sts').get_caller_identity()['Account']
            source_arn_pattern = f"arn:aws:execute-api:{AWS_REGION}:{account_id}:{api_id}/*/{config['method']}{config['resource']}"
            lambda_client.add_permission(
                FunctionName=lambda_arn,
                StatementId=f'{func_name}APIGatewayInvoke',
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=source_arn_pattern
            )
            print(f"   - Integrated {config['method']} {config['resource']}")

        # 3. Deploy API
        apigateway_client.create_deployment(restApiId=api_id, stageName='prod')
        print(f"✅ Deployed API to /prod stage.")
        return f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com/prod"

    except Exception as e:
        print(f"❌ Error setting up API Gateway: {e}")
        return None

# --- MAIN EXECUTION ---

def main():
    print("--- 🚀 Starting CLOD START Automated Deployment (Day 1) ---")

    # 1. Setup IAM Roles
    lambda_assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]
    }
    
    ec2_assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
    }
    
    # CLODStartDemoRole (Lambda Execution Role).txt]
    lambda_role_arn = create_iam_role(
        'CLODStartDemoRole',
        lambda_assume_role_policy,
        'arn:aws:iam::aws:policy/AdministratorAccess' # Using Admin for simplicity on this tight deadline, will add specific policies later.
    )

    # EC2-CLOD-START-Role (Traffic Generator Role).txt]
    ec2_role_arn = create_iam_role(
        'EC2-CLOD-START-Role',
        ec2_assume_role_policy,
        'arn:aws:iam::aws:policy/AmazonS3FullAccess' 
    )

    if not lambda_role_arn or not ec2_role_arn:
        print("Stopping deployment due to IAM error.")
        return

    # Wait for IAM propagation before using the roles
    print("--- Pausing 15 seconds for IAM propagation... ---")
    time.sleep(15)


    # 2. Setup S3 Bucket
    try:
        s3_client.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
        )
        # Create folders
        s3_client.put_object(Bucket=BUCKET_NAME, Key='ml-models/')
        s3_client.put_object(Bucket=BUCKET_NAME, Key='processed-data/')
        s3_client.put_object(Bucket=BUCKET_NAME, Key='training-data/')
        print(f"✅ Created S3 Bucket and folders: {BUCKET_NAME}")
    except ClientError as e:
        print(f"⚠️ S3 Bucket error (may exist or name not unique): {e}")

    # 3. Deploy Lambda Functions
    lambda_arns = {}
    for name, config in FUNCTIONS.items():
        arn = deploy_lambda_function(name, config, lambda_role_arn)
        if arn:
            lambda_arns[name] = arn

    # 4. Setup API Gateway
    api_url = None
    if lambda_arns:
        api_url = setup_apigateway(lambda_arns, lambda_role_arn)
    
    # 5. Instructions for Traffic Generator
    print("\n" + "="*70)
    print("                ✅ DAY 1 DEPLOYMENT COMPLETE! ✅")
    print("="*70)
    print(f"🌐 Final API Endpoint: {api_url}")
    print(f"🗄️ S3 Bucket Name: {BUCKET_NAME}")
    print("\n--- ⚙️ TRAFFIC GENERATOR INSTRUCTIONS ---")
    print("1. **IMPORTANT:** Update the following variables in your `traffic_generator.py` script:")
    print(f"   API_URL = \"{api_url}\"")
    print(f"   self.bucket = '{BUCKET_NAME}'")
    print(f"2. Launch an EC2 instance and attach the **EC2-CLOD-START-Role**.")
    print("3. Copy traffic_generator.py to the EC2 instance.")
    print("4. Run the script on EC2 to start data collection (e.g., `nohup python3 traffic_generator.py 120 &`)")
    print("---")


if __name__ == "__main__":
    main()