"""
Deploy updated DataAggregator Lambda with bundled local models.

Strategy: Use a Lambda Layer for numpy/joblib/xgboost (pre-built),
and only bundle the handler + model .pkl files in the function zip.
This keeps the deployment zip small (~1 MB).

Run from project root:
    python intelligent_warming_system/deploy_data_aggregator.py

Requirements:
    - AWS credentials configured
    - streamlit_ml_tg/models/xgboost_model.pkl  (run save_models.py first)
    - streamlit_ml_tg/models/random_forest_model.pkl
"""

import os
import sys
import json
import shutil
import zipfile
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit_ml_tg'))
import aws_client
from config import aws

FUNCTION_NAME = aws.data_aggregator_function
REGION        = aws.region

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(ROOT_DIR, 'streamlit_ml_tg', 'models')
DA_SCRIPT  = os.path.join(os.path.dirname(__file__), 'data_aggregator.py')

# Public ARN for xgboost + numpy + scipy layer (Python 3.9, ap-south-1)
# Source: https://github.com/keithrozario/Klayers
# This layer includes: numpy, scipy, pandas, xgboost, joblib
XGBOOST_LAYER_ARN = "arn:aws:lambda:ap-south-1:770693421928:layer:Klayers-p39-xgboost:1"

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"
def ok(msg):   print(f"  {GREEN}✅{RESET} {msg}")
def fail(msg): print(f"  {RED}❌{RESET} {msg}")
def info(msg): print(f"  ℹ️  {msg}")


def check_prerequisites():
    xgb_path = os.path.join(MODELS_DIR, 'xgboost_model.pkl')
    rf_path  = os.path.join(MODELS_DIR, 'random_forest_model.pkl')
    if not os.path.exists(xgb_path):
        fail(f"XGBoost model not found: {xgb_path}")
        print("  Run: cd streamlit_ml_tg && python save_models.py")
        return False
    if not os.path.exists(rf_path):
        fail(f"RF model not found: {rf_path}")
        return False
    ok(f"XGBoost model: {os.path.getsize(xgb_path)/1024/1024:.1f} MB")
    ok(f"RF model:      {os.path.getsize(rf_path)/1024/1024:.1f} MB")
    return True


def build_small_zip(tmp_dir: str) -> str:
    """
    Build a small zip containing ONLY:
    - data_aggregator.py
    - models/xgboost_model.pkl
    - models/random_forest_model.pkl

    numpy/joblib/xgboost come from the Lambda Layer.
    """
    zip_path = os.path.join(tmp_dir, 'data_aggregator.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Handler
        zf.write(DA_SCRIPT, 'data_aggregator.py')
        # Models
        zf.write(os.path.join(MODELS_DIR, 'xgboost_model.pkl'),
                 'models/xgboost_model.pkl')
        zf.write(os.path.join(MODELS_DIR, 'random_forest_model.pkl'),
                 'models/random_forest_model.pkl')

    zip_mb = os.path.getsize(zip_path) / 1024 / 1024
    ok(f"Deployment zip: {zip_mb:.2f} MB (handler + models only)")
    return zip_path


def find_or_create_layer(lc) -> str | None:
    """
    Try to find a suitable xgboost layer.
    First tries the public Klayers ARN, then checks existing layers.
    """
    # Try public Klayers layer
    try:
        lc.get_layer_version_by_arn(Arn=XGBOOST_LAYER_ARN)
        ok(f"Using public xgboost layer: {XGBOOST_LAYER_ARN}")
        return XGBOOST_LAYER_ARN
    except Exception:
        pass

    # Check existing layers in account
    try:
        layers = lc.list_layers().get('Layers', [])
        for layer in layers:
            name = layer.get('LayerName', '')
            if 'xgboost' in name.lower() or 'ml' in name.lower():
                arn = layer['LatestMatchingVersion']['LayerVersionArn']
                ok(f"Found existing layer: {arn}")
                return arn
    except Exception:
        pass

    return None


def deploy(zip_path: str, layer_arn: str | None):
    """Upload zip directly (it's small now) and update Lambda."""
    lc = aws_client.lambda_client()

    with open(zip_path, 'rb') as f:
        zip_bytes = f.read()

    info(f"Uploading {len(zip_bytes)/1024/1024:.2f} MB to Lambda '{FUNCTION_NAME}'...")

    try:
        # Update code
        resp = lc.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=zip_bytes,
            Publish=False,
        )
        ok(f"Code uploaded — State: {resp.get('State', '?')}")

        # Wait for update
        info("Waiting for code update to complete...")
        for _ in range(30):
            fn = lc.get_function_configuration(FunctionName=FUNCTION_NAME)
            status = fn.get('LastUpdateStatus', 'InProgress')
            if status == 'Successful':
                break
            if status == 'Failed':
                fail(f"Update failed: {fn.get('LastUpdateStatusReason', '')}")
                return False
            time.sleep(2)

        # Build config update
        config_kwargs = {
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
            config_kwargs['Layers'] = [layer_arn]
            info(f"Attaching layer: {layer_arn}")
        else:
            info("No layer found — numpy/joblib/xgboost must already be in Lambda runtime")

        lc.update_function_configuration(**config_kwargs)
        ok("Configuration updated (handler, timeout=300s, memory=512MB, env vars)")
        return True

    except Exception as e:
        fail(f"Deploy failed: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("DataAggregator Lambda — Deploy with Local Models")
    print("=" * 60)
    print(f"\nTarget:  {FUNCTION_NAME} ({REGION})")
    print(f"Models:  {MODELS_DIR}\n")

    if not check_prerequisites():
        sys.exit(1)

    lc = aws_client.lambda_client()

    info("Looking for xgboost Lambda Layer...")
    layer_arn = find_or_create_layer(lc)
    if not layer_arn:
        print(f"\n  {YELLOW}⚠️  No xgboost layer found.{RESET}")
        print("  The Lambda already has numpy/xgboost from its existing deployment.")
        print("  Proceeding without adding a layer.\n")

    info("Building deployment zip...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = build_small_zip(tmp_dir)

        info("Deploying to AWS Lambda...")
        success = deploy(zip_path, layer_arn)

    if success:
        print(f"\n{GREEN}✅ Deployment complete!{RESET}")
        print("\nTest immediately:")
        print("  python intelligent_warming_system/test_data_aggregator.py")
        print("\nOr wait for next EventBridge trigger (every 15 min)")
        print("Then check: /aws/lambda/DataAggregator CloudWatch Logs")
    else:
        print(f"\n{RED}❌ Deployment failed.{RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()
