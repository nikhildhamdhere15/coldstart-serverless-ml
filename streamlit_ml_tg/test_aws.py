import boto3, json
from datetime import datetime, timezone, timedelta

# Test 1: CloudWatch
try:
    cw = boto3.client('cloudwatch', region_name='ap-south-1')
    r = cw.list_metrics(Namespace='ColdStart/IntelligentWarming')
    metrics = r.get('Metrics', [])
    print(f'CloudWatch OK - {len(metrics)} metrics found')
    for m in metrics[:5]:
        print(f'  {m["MetricName"]}')
except Exception as e:
    print(f'CloudWatch ERROR: {e}')

# Test 2: Lambda invoke DataAggregator
try:
    lc = boto3.client('lambda', region_name='ap-south-1')
    r = lc.invoke(
        FunctionName='DataAggregator',
        InvocationType='RequestResponse',
        Payload=json.dumps({'source': 'dashboard'})
    )
    print(f'Lambda invoke status: {r["StatusCode"]}')
    body = r['Payload'].read()
    print(f'Response (first 300 chars): {body[:300]}')
except Exception as e:
    print(f'Lambda ERROR: {e}')
