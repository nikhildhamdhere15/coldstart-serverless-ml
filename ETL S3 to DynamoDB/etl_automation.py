import boto3
import json
import zipfile
import os
import time

AWS_REGION = 'ap-south-1'
BUCKET_NAME = 'clod-start-demo-yourname-unique'
LAMBDA_FUNCTION_NAME = 'ETLProcessor'
LAMBDA_EXECUTION_ROLE_NAME = 'LambdaS3ETLExecutionRole'
LAMBDA_HANDLER = 'etl_lambda.lambda_handler'
LAMBDA_RUNTIME = 'python3.9'
LAMBDA_ZIP_PATH = 'etl_lambda_package.zip'  # Will create this
LAMBDA_CODE_FILE = 'etl_lambda.py'
S3_EVENT_PREFIX = 'training-data/'

DYNAMODB_TABLE_NAME = 'ETLFeatureData'

iam_client = boto3.client('iam')
lambda_client = boto3.client('lambda', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)
dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)
s3_resource = boto3.resource('s3', region_name=AWS_REGION)


def create_iam_role(role_name):
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    print(f"Creating IAM role {role_name}...")
    try:
        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description='Execution role for Lambda ETL processor'
        )
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists. Using existing.")
        role = iam_client.get_role(RoleName=role_name)
    role_arn = role['Role']['Arn']

    print("Attaching policies...")
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess')
    iam_client.attach_role_policy(RoleName=role_name, PolicyArn='arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess')

    print("Waiting for IAM role propagation...")
    time.sleep(15)
    return role_arn


def create_lambda_zip(lambda_code_file, zip_path):
    print(f"Creating deployment zip {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(lambda_code_file)
    print("Zip file created.")


def create_lambda_function(function_name, role_arn, zip_path):
    with open(zip_path, 'rb') as f:
        zipped_code = f.read()

    print(f"Creating Lambda function {function_name}...")
    try:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime=LAMBDA_RUNTIME,
            Role=role_arn,
            Handler=LAMBDA_HANDLER,
            Code={'ZipFile': zipped_code},
            Timeout=180,
            MemorySize=512,
            Publish=True,
            PackageType='Zip',
        )
    except lambda_client.exceptions.ResourceConflictException:
        print("Lambda function exists. Updating code.")
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zipped_code,
            Publish=True
        )
    return response['FunctionArn']


def create_s3_bucket(bucket_name):
    print(f"Checking if bucket {bucket_name} exists...")
    buckets = s3_client.list_buckets()
    if any(b['Name'] == bucket_name for b in buckets['Buckets']):
        print("Bucket already exists.")
        return

    print(f"Creating bucket {bucket_name}...")
    if AWS_REGION == 'us-east-1':
        s3_client.create_bucket(Bucket=bucket_name)
    else:
        s3_client.create_bucket(Bucket=bucket_name,
                                CreateBucketConfiguration={'LocationConstraint': AWS_REGION})
    time.sleep(5)
    print("Bucket created.")


def create_dynamodb_table(table_name):
    print(f"Checking if DynamoDB table {table_name} exists...")
    existing_tables = dynamodb.list_tables()['TableNames']
    if table_name in existing_tables:
        print(f"Table {table_name} already exists.")
        return

    print(f"Creating DynamoDB table {table_name}...")
    response = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},    # Partition key, you can define your own structure
            {'AttributeName': 'timestamp_s', 'KeyType': 'RANGE'}  # Sort key for time-ordering
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp_s', 'AttributeType': 'N'}
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    print("Waiting for table to become active...")
    waiter = dynamodb.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    print(f"Table {table_name} is active.")


def add_s3_event_trigger(bucket_name, prefix, lambda_arn):
    if ':function:' in lambda_arn:
        base_arn_head = lambda_arn.split(':function:')[0]
        base_arn_tail = lambda_arn.split(':function:')[1].split(':')[0]
        lambda_arn_no_version = base_arn_head + ':function:' + base_arn_tail
    else:
        lambda_arn_no_version = lambda_arn

    print("Adding S3 event trigger for Lambda on object create...")
    print(f"Using Lambda ARN (without version) for notification: {lambda_arn_no_version}")

    statement_id = f"s3invoke-{bucket_name}-{prefix.replace('/', '')}"
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNCTION_NAME,
            StatementId=statement_id,
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{bucket_name}',
            SourceAccount=boto3.client('sts').get_caller_identity()['Account']
        )
        print("Added Lambda invoke permission for S3.")
        time.sleep(20)
    except lambda_client.exceptions.ResourceConflictException:
        print("Lambda invoke permission for S3 already exists.")

    full_config = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
    valid_keys = ['TopicConfigurations', 'QueueConfigurations', 'LambdaFunctionConfigurations', 'EventBridgeConfiguration']
    notification_configuration = {k: full_config[k] for k in valid_keys if k in full_config}

    print("Current notification configuration before update:")
    print(json.dumps(notification_configuration, indent=2))

    existing_lambda_configs = notification_configuration.get('LambdaFunctionConfigurations', [])
    filtered_lambda_configs = [conf for conf in existing_lambda_configs if
                               conf.get('LambdaFunctionArn') != lambda_arn_no_version]

    new_lambda_config = {
        'LambdaFunctionArn': lambda_arn_no_version,
        'Events': ['s3:ObjectCreated:Put'],
        'Filter': {'Key': {'FilterRules': [{'Name': 'prefix', 'Value': prefix}]}}
    }
    filtered_lambda_configs.append(new_lambda_config)
    notification_configuration['LambdaFunctionConfigurations'] = filtered_lambda_configs

    try:
        s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=notification_configuration
        )
        print("S3 event trigger configured successfully.")
    except Exception as e:
        print(f"Error applying bucket notification configuration: {e}")
        raise


def main():
    role_arn = create_iam_role(LAMBDA_EXECUTION_ROLE_NAME)
    create_lambda_zip(LAMBDA_CODE_FILE, LAMBDA_ZIP_PATH)
    lambda_arn = create_lambda_function(LAMBDA_FUNCTION_NAME, role_arn, LAMBDA_ZIP_PATH)
    print(f"Deployed Lambda ARN: {lambda_arn}")
    create_s3_bucket(BUCKET_NAME)
    create_dynamodb_table(DYNAMODB_TABLE_NAME)
    add_s3_event_trigger(BUCKET_NAME, S3_EVENT_PREFIX, lambda_arn)
    print(f"Deployment complete. JSON files uploaded to training-data/ will be processed and written to DynamoDB.")


if __name__ == '__main__':
    main()