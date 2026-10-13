"""Quick pipeline state checker"""
import sys, os, json, datetime
sys.path.insert(0, '.')
import aws_client
from config import aws

print("=" * 60)
print("PIPELINE STATE CHECK")
print("=" * 60)

# 1. Check SageMaker endpoints
print("\n[1] SageMaker Endpoints")
sm = aws_client._session().client('sagemaker')
for ep_name in ['cold-start-xgboost-serverless', 'cold-start-rf-serverless']:
    try:
        ep = sm.describe_endpoint(EndpointName=ep_name)
        status = ep['EndpointStatus']
        print(f"  {ep_name}: {status}")
    except Exception as e:
        print(f"  {ep_name}: NOT FOUND ({type(e).__name__})")

# 2. Check DataAggregator last run logs
print("\n[2] DataAggregator Last Run")
logs = aws_client.cloudwatch_logs()
try:
    streams = logs.describe_log_streams(
        logGroupName='/aws/lambda/DataAggregator',
        orderBy='LastEventTime',
        descending=True,
        limit=1
    ).get('logStreams', [])

    if streams:
        ts = streams[0].get('lastEventTimestamp', 0)
        dt = datetime.datetime.fromtimestamp(ts / 1000)
        print(f"  Last run: {dt}")

        events = logs.get_log_events(
            logGroupName='/aws/lambda/DataAggregator',
            logStreamName=streams[0]['logStreamName'],
            limit=100
        ).get('events', [])

        print(f"  Log lines ({len(events)} total, showing last 30):")
        for ev in events[-30:]:
            msg = ev.get('message', '').strip()
            if msg:
                print(f"    {msg[:250]}")
    else:
        print("  No log streams found")
except Exception as e:
    print(f"  Error: {e}")

# 3. Check IntelligentLambdaWarmer last run
print("\n[3] IntelligentLambdaWarmer Last Run")
try:
    streams2 = logs.describe_log_streams(
        logGroupName='/aws/lambda/IntelligentLambdaWarmer',
        orderBy='LastEventTime',
        descending=True,
        limit=1
    ).get('logStreams', [])

    if streams2:
        ts2 = streams2[0].get('lastEventTimestamp', 0)
        dt2 = datetime.datetime.fromtimestamp(ts2 / 1000)
        print(f"  Last run: {dt2}")

        events2 = logs.get_log_events(
            logGroupName='/aws/lambda/IntelligentLambdaWarmer',
            logStreamName=streams2[0]['logStreamName'],
            limit=100
        ).get('events', [])

        print(f"  Log lines ({len(events2)} total, showing last 30):")
        for ev in events2[-30:]:
            msg = ev.get('message', '').strip()
            if msg:
                print(f"    {msg[:250]}")
    else:
        print("  No log streams found — warmer has never run")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
