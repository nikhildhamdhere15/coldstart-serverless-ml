import json
import time
import random
from datetime import datetime

def lambda_handler(event, context):
    # Check if this is a warming request from the controller
    if event.get('warming'):
        return {'statusCode': 200, 'body': json.dumps({'message': 'Warmed'})}

    # Simulate cold start
    if not hasattr(lambda_handler, 'is_warm'):
        print("🥶 COLD START - Auth initializing...")
        time.sleep(random.uniform(2.0, 3.5))  # Cold start delay
        lambda_handler.is_warm = True
        
    # Simulate auth logic
    time.sleep(random.uniform(0.05, 0.15))

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'message': 'Authentication successful',
            'user_id': f"user_{random.randint(1000, 9999)}",
            'timestamp': datetime.now().isoformat()
        })
    }