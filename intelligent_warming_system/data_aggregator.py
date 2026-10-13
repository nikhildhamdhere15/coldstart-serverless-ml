"""
DataAggregator Lambda Function
Triggered every 15 min by EventBridge.

UPDATED: Uses bundled XGBoost .pkl models instead of SageMaker endpoints
(SageMaker endpoints cold-start-xgboost-serverless and cold-start-rf-serverless
were deleted — models are now bundled directly in the Lambda deployment package)

Pipeline:
  EventBridge (every 15 min)
      → DataAggregator Lambda
          → reads DynamoDB last 15 min
          → runs local XGBoost (70%) + RF (30%) ensemble
          → async invokes IntelligentLambdaWarmer with predictions
"""

import boto3
import json
import os
import numpy as np
import joblib
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb      = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

# Config from env vars
FEATURE_TABLE_NAME   = os.environ.get('FEATURE_TABLE_NAME', 'ETLFeatureData')
WARMER_FUNCTION_NAME = os.environ.get('WARMER_FUNCTION', 'IntelligentLambdaWarmer')

# Thresholds (match Streamlit app)
COLD_START_THRESHOLD = 0.7
HIGH_RISK_THRESHOLD  = 0.8
CONFIDENCE_THRESHOLD = 0.6

# ── Load models once at cold start ───────────────────────────────────────────
_xgb_model = None
_rf_model   = None

def _load_models():
    global _xgb_model, _rf_model
    if _xgb_model is None:
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        xgb_path  = os.path.join(model_dir, 'xgboost_model.pkl')
        rf_path   = os.path.join(model_dir, 'random_forest_model.pkl')
        _xgb_model = joblib.load(xgb_path)
        _rf_model  = joblib.load(rf_path)
        logger.info(f"Models loaded: XGBoost={type(_xgb_model).__name__}, RF={type(_rf_model).__name__}")
    return _xgb_model, _rf_model


def ensemble_predict(features: list) -> dict:
    """
    Run local XGBoost (70%) + Random Forest (30%) ensemble.
    features: 9-element list matching training column order:
    [hour_of_day, day_of_week, traffic_intensity,
     endpoint_auth, endpoint_profile, endpoint_search,
     user_type_new, device_mobile, is_business_hours]
    """
    xgb_model, rf_model = _load_models()
    feat_arr = np.array([features])

    xgb_prob = float(xgb_model.predict_proba(feat_arr)[0][1])
    rf_prob  = float(rf_model.predict_proba(feat_arr)[0][1])

    p_final    = round(0.7 * xgb_prob + 0.3 * rf_prob, 4)
    confidence = round(1.0 - abs(xgb_prob - rf_prob), 4)

    logger.info(f"Prediction — XGB: {xgb_prob:.3f}, RF: {rf_prob:.3f}, "
                f"P_final: {p_final:.3f}, C: {confidence:.3f}")

    return {
        'xgboost_probability':      xgb_prob,
        'random_forest_probability': rf_prob,
        'ensemble_probability':      p_final,
        'confidence':                confidence,
        'prediction':                'cold_start' if p_final > 0.5 else 'warm',
    }


def get_recent_data(minutes: int = 15) -> list:
    """Read DynamoDB for the last N minutes and aggregate per endpoint."""
    table    = dynamodb.Table(FEATURE_TABLE_NAME)
    now      = datetime.utcnow()
    end_ts   = int(now.timestamp())
    start_ts = int((now - timedelta(minutes=minutes)).timestamp())

    logger.info(f"Querying DynamoDB from {start_ts} to {end_ts}")

    resp  = table.scan(
        FilterExpression='#ts BETWEEN :s AND :e',
        ExpressionAttributeNames={'#ts': 'timestamp_s'},
        ExpressionAttributeValues={':s': start_ts, ':e': end_ts},
    )
    items = resp.get('Items', [])

    while 'LastEvaluatedKey' in resp:
        resp = table.scan(
            FilterExpression='#ts BETWEEN :s AND :e',
            ExpressionAttributeNames={'#ts': 'timestamp_s'},
            ExpressionAttributeValues={':s': start_ts, ':e': end_ts},
            ExclusiveStartKey=resp['LastEvaluatedKey'],
        )
        items.extend(resp.get('Items', []))

    # Convert Decimal → float
    for item in items:
        for k, v in item.items():
            if isinstance(v, Decimal):
                item[k] = float(v)

    logger.info(f"Found {len(items)} records in last {minutes} minutes")
    return items


def aggregate_per_endpoint(items: list) -> list:
    """
    Group items by endpoint and build feature vectors.
    Returns list of dicts ready for ensemble_predict().
    """
    endpoint_items = {'auth': [], 'profile': [], 'search': []}

    for item in items:
        if item.get('endpoint_auth', 0) == 1:
            endpoint_items['auth'].append(item)
        elif item.get('endpoint_profile', 0) == 1:
            endpoint_items['profile'].append(item)
        elif item.get('endpoint_search', 0) == 1:
            endpoint_items['search'].append(item)

    result = []
    for ep_name, ep_data in endpoint_items.items():
        if len(ep_data) < 5:
            logger.info(f"Skipping {ep_name} — only {len(ep_data)} records (min 5)")
            continue

        n = len(ep_data)
        latest = max(ep_data, key=lambda x: x.get('timestamp_s', 0))

        hour_of_day  = float(latest.get('hour_of_day', datetime.utcnow().hour))
        day_of_week  = float(latest.get('day_of_week', datetime.utcnow().weekday()))
        # Scale traffic: 5req→0.01, 50req→0.09, 200req→0.39, 500req→0.99
        traffic      = max(0.01, min(1.0, (n - 5) * 0.002))
        user_new     = 1.0 if (sum(float(i.get('user_type_new', 0)) for i in ep_data) / n) > 0.5 else 0.0
        device_mob   = 1.0 if (sum(float(i.get('device_mobile', 0)) for i in ep_data) / n) > 0.5 else 0.0
        is_biz       = float(latest.get('is_business_hours', 0))

        ep_auth    = 1.0 if ep_name == 'auth'    else 0.0
        ep_profile = 1.0 if ep_name == 'profile' else 0.0
        ep_search  = 1.0 if ep_name == 'search'  else 0.0

        features = [
            hour_of_day, day_of_week, traffic,
            ep_auth, ep_profile, ep_search,
            user_new, device_mob, is_biz,
        ]

        logger.info(f"{ep_name} ({n} req): H{hour_of_day:.0f} D{day_of_week:.0f} "
                    f"I{traffic:.3f} N{user_new:.0f} M{device_mob:.0f} → {features}")

        result.append({
            'endpoint':      ep_name,
            'function_name': f'{ep_name}-function',
            'features':      features,
            'request_count': n,
        })

    return result


def build_warmer_payload(predictions: list) -> list:
    """Build the payload IntelligentLambdaWarmer expects."""
    return [
        {
            'endpoint':             p['endpoint'],
            'function_name':        p['function_name'],
            'ensemble_probability': p['ensemble_probability'],
            'request_count':        p['request_count'],
        }
        for p in predictions
        # Only send endpoints that pass CBW gate
        if p['ensemble_probability'] >= COLD_START_THRESHOLD
        and p['confidence'] >= CONFIDENCE_THRESHOLD
    ]


def invoke_warmer(warmer_payload: list) -> bool:
    """Async-invoke IntelligentLambdaWarmer with predictions."""
    if not warmer_payload:
        logger.info("No endpoints passed CBW gate — skipping warmer invocation")
        return False

    try:
        response = lambda_client.invoke(
            FunctionName=WARMER_FUNCTION_NAME,
            InvocationType='Event',  # Async — fire and forget
            Payload=json.dumps({'predictions': warmer_payload}).encode('utf-8'),
        )
        status = response.get('StatusCode', 0)
        logger.info(f"IntelligentLambdaWarmer invoked async — StatusCode: {status}")
        return status == 202  # 202 = accepted for async invocation
    except Exception as e:
        logger.error(f"Failed to invoke IntelligentLambdaWarmer: {e}")
        return False


def lambda_handler(event, context):
    """
    Main handler — triggered every 15 min by EventBridge.
    """
    logger.info("DataAggregator: starting 15-min cycle")

    try:
        # Step 1: Read DynamoDB
        items = get_recent_data(minutes=15)
        if not items:
            logger.info("No data in last 15 min — skipping")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No data', 'timestamp': datetime.utcnow().isoformat()})
            }

        # Step 2: Aggregate per endpoint
        endpoint_features = aggregate_per_endpoint(items)
        if not endpoint_features:
            logger.info("No endpoints with enough data — skipping")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Insufficient data per endpoint',
                                    'timestamp': datetime.utcnow().isoformat()})
            }

        # Step 3: Run local ensemble predictions
        predictions = []
        for ep in endpoint_features:
            try:
                pred = ensemble_predict(ep['features'])
                predictions.append({
                    'endpoint':                  ep['endpoint'],
                    'function_name':             ep['function_name'],
                    'request_count':             ep['request_count'],
                    'features':                  ep['features'],
                    **pred,
                })
                logger.info(f"{ep['endpoint']}: P_final={pred['ensemble_probability']:.3f}, "
                            f"C={pred['confidence']:.3f}, "
                            f"CBW={'WARM' if pred['ensemble_probability'] >= COLD_START_THRESHOLD and pred['confidence'] >= CONFIDENCE_THRESHOLD else 'SKIP'}")
            except Exception as e:
                logger.error(f"Prediction failed for {ep['endpoint']}: {e}")

        if not predictions:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'All predictions failed',
                                    'timestamp': datetime.utcnow().isoformat()})
            }

        # Step 4: Build warmer payload (only CBW-passing endpoints)
        warmer_payload = build_warmer_payload(predictions)
        warm_count = len(warmer_payload)
        logger.info(f"CBW gate: {warm_count}/{len(predictions)} endpoints need warming")

        # Step 5: Invoke IntelligentLambdaWarmer
        warmer_invoked = invoke_warmer(warmer_payload)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message':                   'Cycle complete',
                'total_records':             len(items),
                'endpoints_evaluated':       len(predictions),
                'endpoints_to_warm':         warm_count,
                'warmer_invoked':            warmer_invoked,
                'predictions':               predictions,
                'timestamp':                 datetime.utcnow().isoformat(),
            })
        }

    except Exception as e:
        logger.error(f"DataAggregator error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e), 'timestamp': datetime.utcnow().isoformat()})
        }
