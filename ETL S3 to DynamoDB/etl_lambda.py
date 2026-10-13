import boto3
import json
from datetime import datetime

# Initialize boto3 clients
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

# DynamoDB table name (must match table created in your automation script)
TABLE_NAME = 'ETLFeatureData'
table = dynamodb.Table(TABLE_NAME)

def extract_features(raw_data):
    try:
        request_data = raw_data['request']
        timestamp = datetime.fromisoformat(request_data['timestamp'].replace('Z', '+00:00'))
        endpoint = request_data['endpoint']

        features = {
            # Composite ID: combine unique ID or use s3 key + timestamp for uniqueness, adjust as needed
            'id': raw_data.get('id', '') + '_' + str(int(timestamp.timestamp())),
            'timestamp_s': int(timestamp.timestamp()),
            'cold_start_label': raw_data['ml_label'],
            'hour_of_day': timestamp.hour,
            'day_of_week': timestamp.weekday(),
            'is_business_hours': request_data['is_business_hours'],
            'endpoint_auth': 1 if endpoint == '/auth' else 0,
            'endpoint_profile': 1 if endpoint == '/profile' else 0,
            'endpoint_search': 1 if endpoint == '/search' else 0,
            'traffic_intensity': int(request_data['traffic_intensity']),
            'user_type_new': 1 if request_data['user_type'] == 'new' else 0,
            'device_mobile': 1 if request_data['device'] == 'mobile' else 0,
        }
        return features
    except Exception as e:
        print(f"Feature extraction error: {e}")
        raise

def lambda_handler(event, context):
    # Get S3 bucket and object key from event
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    print(f"Processing S3 object: s3://{bucket}/{key}")

    try:
        # Get raw JSON data from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw_json = json.loads(response['Body'].read().decode('utf-8'))

        # Extract features
        features = extract_features(raw_json)

        # Write to DynamoDB table
        table.put_item(Item=features)
        print(f"Successfully wrote item to DynamoDB: {features['id']}")

        return {
            'statusCode': 200,
            'body': f'Successfully processed {key}'
        }
    except Exception as e:
        print(f"Error processing S3 object {key}: {e}")
        return {
            'statusCode': 500,
            'body': f'Error processing {key}: {e}'
        }   