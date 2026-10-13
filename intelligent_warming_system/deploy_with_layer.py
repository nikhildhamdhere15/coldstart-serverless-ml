"""
Deploy DataAggregator Lambda using a Lambda Layer for xgboost/numpy.

Strategy:
  1. Create a Lambda Layer with xgboost + numpy + scikit-learn (uploaded to S3)
  2. Deploy a tiny function zip (~1MB) with just the handler + model .pkl files
  3. Attach the layer to the function

Run:
    python intelligent_warming_system/deploy_with_layer.py
"""

import os, sys, json, shutil, zipfile, subprocess, tempfile, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import aws_client
from config import aws

FUNCTION_NAME = aws.data_aggregator_function
REGION        = aws.region
ROOT_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR    = os.path.join(ROOT_DIR, 'streamlit_ml_tg', 'models')
DA_SCRIPT     = os.path.join(os.path.dirname(__file__), 'data_aggregator.py')
LAYER_NAME    = "coldstart-xgboost-layer"
S3_PREFIX     = "lambda-deployments"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅{E} {m}")
def fail(m): print(f"  {R}❌{E} {m}")
def info(m): print(f"  {B}ℹ️ {E} {m}")
def warn(m): print(f"  {Y}⚠️ {E} {m}")


# ── Step 1: Check prerequisites ───────────────────────────────────────────────
def check_prereqs():
    xgb = os.path.join(MODELS_DIR, 'xgboost_model.pkl')
    rf  = os.path.join(MODELS_DIR, 'random_forest_model.pkl')
    if not os.path.exists(xgb):
        fail(f"Missing: {xgb}  →  run: cd streamlit_ml_tg && python save_models.py")
        return False
    if not os.path.exists(rf):
        fail(f"Missing: {rf}")
        return False
    ok(f"XGBoost model: {os.path.getsize(xgb)/1024:.0f} KB")
    ok(f"RF model:      {os.path.getsize(rf)/1024:.0f} KB")
    return True


# ── Step 2: Build layer zip (python/lib/python3.9/site-packages/...) ──────────
def build_layer_zip(tmp_dir):
    """
    Lambda layers must have this structure:
    python/lib/python3.9/site-packages/<packages>
    """
    site_pkg = os.path.join(tmp_dir, 'layer', 'python', 'lib', 'python3.9', 'site-packages')
    os.makedirs(site_pkg, exist_ok=True)

    info("Installing xgboost + numpy + scikit-learn into layer (takes ~60s)...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install',
         'xgboost', 'numpy', 'scikit-learn',
         '--target', site_pkg,
         '--quiet', '--no-cache-dir',
         '--platform', 'manylinux2014_x86_64',
         '--only-binary=:all:',
         '--python-version', '3.9'],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        fail(f"pip install failed:\n{result.stderr[:1000]}")
        return None
    ok("Dependencies installed into layer")

    # Zip the layer
    layer_zip = os.path.join(tmp_dir, 'layer.zip')
    layer_dir = os.path.join(tmp_dir, 'layer')
    with zipfile.ZipFile(layer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(layer_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__' and not d.endswith('.dist-info')]
            for f in files:
                if f.endswith('.pyc'): continue
                full = os.path.join(root, f)
                arc  = os.path.relpath(full, layer_dir)
                zf.write(full, arc)

    mb = os.path.getsize(layer_zip) / 1024 / 1024
    ok(f"Layer zip: {mb:.1f} MB")
    return layer_zip


# ── Step 3: Build tiny function zip (handler + models only) ───────────────────
def build_function_zip(tmp_dir):
    fn_zip = os.path.join(tmp_dir, 'function.zip')
    with zipfile.ZipFile(fn_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DA_SCRIPT, 'data_aggregator.py')
        zf.write(os.path.join(MODELS_DIR, 'xgboost_model.pkl'),     'models/xgboost_model.pkl')
        zf.write(os.path.join(MODELS_DIR, 'random_forest_model.pkl'),'models/random_forest_model.pkl')
    mb = os.path.getsize(fn_zip) / 1024 / 1024
    ok(f"Function zip: {mb:.2f} MB (handler + models only)")
    return fn_zip


# ── Step 4: Upload both zips to S3 ────────────────────────────────────────────
def upload_to_s3(layer_zip, fn_zip):
    s3 = aws_client.s3()
    layer_key = f"{S3_PREFIX}/layer.zip"
    fn_key    = f"{S3_PREFIX}/data_aggregator.zip"

    info(f"Uploading layer zip ({os.path.getsize(layer_zip)/1024/1024:.1f} MB) to S3...")
    s3.upload_file(layer_zip, aws.s3_bucket, layer_key)
    ok(f"Layer uploaded: s3://{aws.s3_bucket}/{layer_key}")

    info(f"Uploading function zip ({os.path.getsize(fn_zip)/1024/1024:.2f} MB) to S3...")
    s3.upload_file(fn_zip, aws.s3_bucket, fn_key)
    ok(f"Function uploaded: s3://{aws.s3_bucket}/{fn_key}")

    return layer_key, fn_key


# ── Step 5: Create/update Lambda Layer ────────────────────────────────────────
def publish_layer(layer_key):
    lc = aws_client.lambda_client()

    info(f"Publishing Lambda Layer '{LAYER_NAME}'...")
    try:
        resp = lc.publish_layer_version(
            LayerName=LAYER_NAME,
            Description="xgboost + numpy + scikit-learn for DataAggregator",
            Content={'S3Bucket': aws.s3_bucket, 'S3Key': layer_key},
            CompatibleRuntimes=['python3.9', 'python3.10', 'python3.11'],
        )
        layer_arn = resp['LayerVersionArn']
        ok(f"Layer published: {layer_arn}")
        return layer_arn
    except Exception as e:
        fail(f"Layer publish failed: {e}")
        return None


# ── Step 6: Update Lambda function code + attach layer ────────────────────────
def deploy_function(fn_key, layer_arn):
    lc = aws_client.lambda_client()

    info(f"Updating Lambda '{FUNCTION_NAME}' code from S3...")
    try:
        lc.update_function_code(
            FunctionName=FUNCTION_NAME,
            S3Bucket=aws.s3_bucket,
            S3Key=fn_key,
            Publish=False,
        )
        ok("Code updated")

        # Wait for update to complete
        info("Waiting for code update...")
        for _ in range(30):
            fn = lc.get_function_configuration(FunctionName=FUNCTION_NAME)
            if fn.get('LastUpdateStatus') == 'Successful': break
            if fn.get('LastUpdateStatus') == 'Failed':
                fail(f"Update failed: {fn.get('LastUpdateStatusReason')}")
                return False
            time.sleep(2)

        # Update config: attach layer, set handler/timeout/memory/env
        config = {
            'FunctionName': FUNCTION_NAME,
            'Handler':      'data_aggregator.lambda_handler',
            'Timeout':      300,
            'MemorySize':   512,
            'Environment': {
                'Variables': {
                    'FEATURE_TABLE_NAME': aws.dynamodb_table,
                    'WARMER_FUNCTION':    aws.warmer_function,
                }
            }
        }
        if layer_arn:
            config['Layers'] = [layer_arn]

        lc.update_function_configuration(**config)
        ok("Configuration updated (handler, timeout=300s, memory=512MB, layer attached)")

        # Wait for config update
        info("Waiting for config update...")
        for _ in range(30):
            fn = lc.get_function_configuration(FunctionName=FUNCTION_NAME)
            if fn.get('LastUpdateStatus') == 'Successful': break
            time.sleep(2)

        ok("Lambda fully updated and ready")
        return True

    except Exception as e:
        fail(f"Function deploy failed: {e}")
        return False


# ── Step 7: Quick smoke test ──────────────────────────────────────────────────
def smoke_test():
    lc = aws_client.lambda_client()
    info("Running smoke test (invoking Lambda with empty event)...")
    try:
        resp    = lc.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps({}).encode('utf-8'),
        )
        status  = resp.get('StatusCode', 0)
        fn_err  = resp.get('FunctionError', '')
        raw     = resp['Payload'].read().decode('utf-8')

        if fn_err:
            try:
                err = json.loads(raw)
                fail(f"Lambda error: {err.get('errorMessage', raw[:300])}")
            except Exception:
                fail(f"Lambda error: {raw[:300]}")
            return False

        outer = json.loads(raw)
        body  = json.loads(outer.get('body', '{}')) if isinstance(outer.get('body'), str) else outer.get('body', {})
        msg   = body.get('message', '')

        ok(f"Lambda responded: {msg}")
        preds = body.get('predictions', [])
        if preds:
            ok(f"Predictions made: {len(preds)}")
            for p in preds:
                ep   = p.get('endpoint', '?')
                prob = p.get('ensemble_probability', 0)
                conf = p.get('confidence', 0)
                cbw  = prob >= 0.7 and conf >= 0.6
                print(f"    {ep:10} P={prob:.3f} C={conf:.3f} CBW={'WARM ⚡' if cbw else 'SKIP'}")
            if body.get('warmer_invoked'):
                ok("IntelligentLambdaWarmer was invoked!")
        elif 'No data' in msg:
            warn("No DynamoDB data — start Traffic Generator first, then re-test")
        return True

    except Exception as e:
        fail(f"Smoke test failed: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print("DataAggregator Lambda — Deploy with Lambda Layer")
    print(f"{'='*60}")
    print(f"\nFunction: {FUNCTION_NAME}  |  Region: {REGION}")
    print(f"S3 Bucket: {aws.s3_bucket}\n")

    if not check_prereqs():
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        # Build
        info("Building layer zip...")
        layer_zip = build_layer_zip(tmp)
        if not layer_zip:
            sys.exit(1)

        info("Building function zip...")
        fn_zip = build_function_zip(tmp)

        # Upload
        info("Uploading to S3...")
        layer_key, fn_key = upload_to_s3(layer_zip, fn_zip)

        # Publish layer
        layer_arn = publish_layer(layer_key)

        # Deploy function
        info("Deploying function...")
        if not deploy_function(fn_key, layer_arn):
            sys.exit(1)

    # Smoke test
    print()
    smoke_test()

    print(f"\n{G}{'='*60}")
    print("Deployment complete!")
    print(f"{'='*60}{E}")
    print("\nNext steps:")
    print("  1. Start Traffic Generator in Streamlit dashboard")
    print("  2. Wait 15 min for EventBridge to trigger DataAggregator")
    print("  3. Check CloudWatch Logs: /aws/lambda/DataAggregator")
    print("  4. Verify IntelligentLambdaWarmer runs: /aws/lambda/IntelligentLambdaWarmer")
    print("\nOr test immediately:")
    print("  python intelligent_warming_system/test_data_aggregator.py")


if __name__ == '__main__':
    main()
