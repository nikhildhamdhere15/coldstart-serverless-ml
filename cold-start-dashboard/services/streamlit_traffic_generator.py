"""
Streamlit Traffic Generator Service
Runs traffic generation directly from the Streamlit UI
Sends requests to API Gateway and stores JSON logs in S3
"""

import boto3
import json
import random
import threading
import time
from datetime import datetime, timezone
from collections import defaultdict
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────
BUCKET_NAME  = 'clod-start-demo-yourname-unique'   # update to your bucket name
API_ENDPOINTS = ['/auth', '/profile', '/search']


def _get_s3_client():
    """Get S3 client using Streamlit secrets or local credentials"""
    try:
        return boto3.client(
            's3',
            region_name=st.secrets.get("AWS_DEFAULT_REGION", "ap-south-1"),
            aws_access_key_id=st.secrets.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=st.secrets.get("AWS_SECRET_ACCESS_KEY")
        )
    except Exception:
        return boto3.client('s3', region_name='ap-south-1')


def _generate_request(endpoint: str, request_num: int) -> dict:
    """Generate a single realistic API request JSON record"""

    # Risk level variation — 85% high-risk overall
    risk_roll = random.random()

    if risk_roll < 0.60:       # 60% EXTREME RISK
        hour             = random.choice([0, 1, 2, 3, 4, 23])
        day_of_week      = random.choice([5, 6])
        traffic_intensity = round(random.uniform(0.01, 0.08), 4)
        user_type        = 'new'
        device           = 'mobile'
        ml_label         = 1   # cold start

    elif risk_roll < 0.85:     # 25% HIGH RISK
        hour             = random.choice([5, 6, 7, 22])
        day_of_week      = random.choice([0, 1, 2, 3, 4])
        traffic_intensity = round(random.uniform(0.08, 0.3), 4)
        user_type        = random.choice(['new', 'returning'])
        device           = random.choice(['mobile', 'desktop'])
        ml_label         = 1

    else:                      # 15% LOW RISK (warm)
        hour             = random.choice(range(9, 18))
        day_of_week      = random.choice([0, 1, 2, 3, 4])
        traffic_intensity = round(random.uniform(0.5, 2.0), 4)
        user_type        = 'returning'
        device           = 'desktop'
        ml_label         = 0   # warm start

    is_business_hours = (0 <= day_of_week <= 4) and (9 <= hour <= 17)

    return {
        "id": f"req_{request_num}_{int(datetime.now().timestamp())}",
        "ml_label": ml_label,
        "request": {
            "endpoint":          endpoint,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
            "hour_of_day":       hour,
            "day_of_week":       day_of_week,
            "traffic_intensity": traffic_intensity,
            "user_type":         user_type,
            "device":            device,
            "is_business_hours": is_business_hours
        }
    }


def _upload_batch_to_s3(s3_client, records: list, batch_num: int):
    """Upload a batch of records as a single JSON file to S3"""
    key  = f"training-data/batch_{batch_num}_{int(time.time())}.json"
    body = json.dumps(records, default=str)
    s3_client.put_object(Bucket=BUCKET_NAME, Key=key, Body=body)
    return key


def run_traffic_generation(
    total_requests: int,
    requests_per_batch: int,
    delay_between_batches: float,
    progress_callback=None,
    status_callback=None
):
    """
    Main traffic generation function — runs in a background thread.

    Args:
        total_requests:        Total number of requests to generate
        requests_per_batch:    How many records per S3 file
        delay_between_batches: Seconds to wait between batches
        progress_callback:     Called with (current, total) for progress bar
        status_callback:       Called with a status string message
    """
    s3_client   = _get_s3_client()
    request_num = 0
    batch_num   = 0
    endpoint_cycle = 0
    counts = defaultdict(int)

    while request_num < total_requests:
        batch = []

        for _ in range(min(requests_per_batch, total_requests - request_num)):
            endpoint = API_ENDPOINTS[endpoint_cycle % 3]
            endpoint_cycle += 1

            record = _generate_request(endpoint, request_num)
            batch.append(record)

            counts[endpoint] += 1
            counts['total']  += 1
            request_num      += 1

        # Upload batch to S3
        try:
            key = _upload_batch_to_s3(s3_client, batch, batch_num)
            batch_num += 1

            if status_callback:
                cold_starts = sum(1 for r in batch if r['ml_label'] == 1)
                status_callback(
                    f"✅ Batch {batch_num} uploaded → {key}\n"
                    f"   Records: {len(batch)} | Cold starts: {cold_starts} | "
                    f"Total so far: {request_num}/{total_requests}"
                )

        except Exception as e:
            if status_callback:
                status_callback(f"❌ Upload error: {str(e)}")

        if progress_callback:
            progress_callback(request_num, total_requests)

        if request_num < total_requests:
            time.sleep(delay_between_batches)

    if status_callback:
        status_callback(
            f"🎉 Done! Generated {request_num} requests → "
            f"auth: {counts['/auth']}, "
            f"profile: {counts['/profile']}, "
            f"search: {counts['/search']}"
        )
