"""
Traffic Generator — exact same logic as UltimateTrafficGenerator.
UI exposes only one option: how many hours to run.
Rate: ~3 req/min = 180 req per 15-min DataAggregator window.
"""
import json
import random
import time
from datetime import datetime, timezone
from collections import defaultdict
import aws_client
from config import aws

BUCKET_NAME = aws.s3_bucket
INSTANCE_ID = "streamlit-ui-generator"
ENDPOINTS   = ['/auth', '/search', '/profile']


def _generate_request(total_requests):
    """Exact same logic as UltimateTrafficGenerator.generate_varied_request"""
    endpoint = ENDPOINTS[total_requests % 3]  # round-robin

    risk_roll = random.random()

    if risk_roll < 0.60:          # 60% EXTREME RISK
        hour             = random.choice([0, 1, 2, 3, 4, 23])
        day_of_week      = random.choice([5, 6])
        traffic_intensity = random.uniform(0.01, 0.08)
        user_type        = 'new'
        device           = 'mobile'
        is_high_risk     = True

    elif risk_roll < 0.85:        # 25% HIGH RISK
        hour             = random.choice([5, 22, 23])
        day_of_week      = random.choice([0, 6])
        traffic_intensity = random.uniform(0.09, 0.20)
        user_type        = 'new'
        device           = 'mobile'
        is_high_risk     = True

    else:                         # 15% LOW RISK
        hour             = random.choice([12, 14, 16])
        day_of_week      = random.choice([1, 2, 3])
        traffic_intensity = random.uniform(1.6, 2.5)
        user_type        = 'returning'
        device           = 'desktop'
        is_high_risk     = False

    request_data = {
        'timestamp':        datetime.now(timezone.utc).isoformat(),
        'instance_id':      INSTANCE_ID,
        'endpoint':         endpoint,
        'hour':             hour,
        'day_of_week':      day_of_week,
        'traffic_intensity': traffic_intensity,
        'user_type':        user_type,
        'device':           device,
        'is_business_hours': 1 if (9 <= hour <= 17 and day_of_week < 5) else 0,
    }
    return endpoint, request_data, is_high_risk


def _make_response(is_high_risk):
    """Exact same logic as UltimateTrafficGenerator.make_request"""
    if is_high_risk:
        return {
            'success':       True,
            'response_time': random.uniform(1.8, 3.8),
            'cold_start':    True,
            'status_code':   200,
        }
    else:
        return {
            'success':       True,
            'response_time': random.uniform(0.08, 0.35),
            'cold_start':    random.random() < 0.15,
            'status_code':   200,
        }


def run(hours: float, on_progress=None, on_status=None, stop_flag=None):
    """
    Run traffic generation for the specified number of hours.
    Rate: 1 request/second = ~3 req/min = 180 req per 15-min window.
    Uploads one JSON record per request to S3 (same as original script).
    """
    s3_client      = aws_client.s3()
    end_time       = time.time() + (hours * 3600)
    total_requests = 0
    counts         = defaultdict(int)

    if on_status:
        on_status(
            f"Started — {hours}h run | Bucket: {BUCKET_NAME}\n"
            f"Rate: ~3 req/min | 85% high-risk | round-robin endpoints"
        )

    while time.time() < end_time:
        if stop_flag and stop_flag():
            if on_status:
                on_status("Stopped by user.")
            break

        endpoint, request_data, is_high_risk = _generate_request(total_requests)
        response_data = _make_response(is_high_risk)

        # S3 key — use local date (IST) to match your calendar date
        local_now = datetime.now()
        utc_now   = datetime.now(timezone.utc)
        key = (
            f"training-data/{local_now.strftime('%Y/%m/%d')}/"
            f"{INSTANCE_ID}_{int(utc_now.timestamp())}.json"
        )

        record = {
            'request':       request_data,
            'response':      response_data,
            'ml_label':      1 if response_data['cold_start'] else 0,
            'utc_timestamp': utc_now.isoformat() + 'Z',
        }

        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(record, default=str).encode('utf-8'),
            )
            counts[endpoint] += 1
            total_requests   += 1

            if on_progress:
                elapsed  = time.time() - (end_time - hours * 3600)
                pct      = min(int(elapsed / (hours * 3600) * 100), 99)
                on_progress(pct, total_requests)

            if on_status and total_requests % 45 == 0:
                on_status(
                    f"Cycle complete — {total_requests} requests | "
                    f"auth:{counts['/auth']} search:{counts['/search']} profile:{counts['/profile']}"
                )

        except Exception as e:
            if on_status:
                on_status(f"S3 error: {e}")

        time.sleep(1.0)   # ~3 req/min

    if on_status:
        on_status(
            f"Done. {total_requests} requests in {hours}h — "
            f"auth:{counts['/auth']} search:{counts['/search']} profile:{counts['/profile']}"
        )
    if on_progress:
        on_progress(100, total_requests)
