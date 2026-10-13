import boto3
from datetime import datetime, timezone, timedelta

cw = boto3.client('cloudwatch', region_name='ap-south-1')

try:
    r = cw.list_metrics(Namespace='ColdStart/IntelligentWarming')
    print(f'list_metrics OK - {len(r["Metrics"])} metrics found')
    for m in r["Metrics"][:5]:
        print(f'  {m["MetricName"]}')
except Exception as e:
    print(f'list_metrics FAILED: {e}')

try:
    r = cw.get_metric_statistics(
        Namespace='ColdStart/IntelligentWarming',
        MetricName='ColdStartProbability',
        StartTime=datetime.now(timezone.utc) - timedelta(hours=24),
        EndTime=datetime.now(timezone.utc),
        Period=3600,
        Statistics=['Average']
    )
    print(f'get_metric_statistics OK - {len(r["Datapoints"])} datapoints')
except Exception as e:
    print(f'get_metric_statistics FAILED: {e}')

# Check what namespaces exist
try:
    r = cw.list_metrics()
    namespaces = set(m['Namespace'] for m in r.get('Metrics', []))
    print(f'All namespaces: {list(namespaces)[:10]}')
except Exception as e:
    print(f'list all metrics FAILED: {e}')
