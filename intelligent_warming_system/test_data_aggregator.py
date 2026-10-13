"""
Test the updated DataAggregator Lambda after deployment.
Invokes it directly and shows the full output.

Run:
    python intelligent_warming_system/test_data_aggregator.py
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import aws_client
from config import aws

lc   = aws_client.lambda_client()
logs = aws_client.cloudwatch_logs()

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"

print("\n" + "=" * 60)
print("DataAggregator Lambda — Direct Invocation Test")
print("=" * 60)

print(f"\nInvoking '{aws.data_aggregator_function}'...")

try:
    response = lc.invoke(
        FunctionName=aws.data_aggregator_function,
        InvocationType='RequestResponse',
        Payload=json.dumps({}).encode('utf-8'),
    )

    status    = response.get('StatusCode', 0)
    fn_error  = response.get('FunctionError', '')
    raw       = response['Payload'].read().decode('utf-8')

    print(f"\nStatusCode:    {status}")
    print(f"FunctionError: {fn_error or 'None'}")

    if fn_error:
        print(f"\n{RED}Lambda threw an exception:{RESET}")
        try:
            err = json.loads(raw)
            print(f"  errorMessage: {err.get('errorMessage', raw[:500])}")
            print(f"  stackTrace:   {err.get('stackTrace', [''])[0][:300]}")
        except Exception:
            print(f"  Raw: {raw[:500]}")
        sys.exit(1)

    outer = json.loads(raw)
    body_str = outer.get('body', '{}')
    body = json.loads(body_str) if isinstance(body_str, str) else body_str

    print(f"\n{GREEN}Response body:{RESET}")
    print(json.dumps(body, indent=2, default=str)[:3000])

    # Summary
    preds = body.get('predictions', [])
    if preds:
        print(f"\n{GREEN}✅ Predictions made:{RESET}")
        for p in preds:
            ep   = p.get('endpoint', '?')
            prob = p.get('ensemble_probability', 0)
            conf = p.get('confidence', 0)
            cbw  = prob >= 0.7 and conf >= 0.6
            print(f"  {ep:10} | P_final={prob:.3f} | C={conf:.3f} | CBW={'WARM ⚡' if cbw else 'SKIP'}")

        warm_count = body.get('endpoints_to_warm', 0)
        invoked    = body.get('warmer_invoked', False)
        print(f"\n  Endpoints to warm: {warm_count}")
        print(f"  Warmer invoked:    {invoked}")

        if invoked:
            print(f"\n{GREEN}✅ IntelligentLambdaWarmer was invoked!{RESET}")
            print("  Check CloudWatch Logs: /aws/lambda/IntelligentLambdaWarmer")
        elif warm_count == 0:
            print(f"\n{YELLOW}⚠️  No endpoints passed CBW gate (P_final < 0.7 or C < 0.6){RESET}")
            print("  This is correct behaviour — no warming needed right now.")
        else:
            print(f"\n{RED}❌ Warmer was NOT invoked despite {warm_count} endpoints needing warming{RESET}")
    else:
        msg = body.get('message', '')
        print(f"\n{YELLOW}⚠️  No predictions: {msg}{RESET}")
        if 'No data' in msg:
            print("  Run Traffic Generator first to populate DynamoDB.")

except Exception as e:
    print(f"\n{RED}Invocation failed: {type(e).__name__}: {e}{RESET}")
    sys.exit(1)

# Wait a moment then check warmer logs
import time
if body.get('warmer_invoked'):
    print("\nWaiting 15s for warmer to complete...")
    time.sleep(15)

    print("\n[IntelligentLambdaWarmer Logs]")
    try:
        streams = logs.describe_log_streams(
            logGroupName='/aws/lambda/IntelligentLambdaWarmer',
            orderBy='LastEventTime',
            descending=True,
            limit=1
        ).get('logStreams', [])

        if streams:
            ts = streams[0].get('lastEventTimestamp', 0)
            dt = datetime.datetime.fromtimestamp(ts / 1000)
            print(f"  Last run: {dt}")

            events = logs.get_log_events(
                logGroupName='/aws/lambda/IntelligentLambdaWarmer',
                logStreamName=streams[0]['logStreamName'],
                limit=50
            ).get('events', [])

            for ev in events[-20:]:
                msg = ev.get('message', '').strip()
                if msg:
                    print(f"  {msg[:250]}")
    except Exception as e:
        print(f"  Could not read warmer logs: {e}")

print("\n" + "=" * 60)
