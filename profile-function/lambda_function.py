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
        print("🥶 COLD START - Profile initializing...")
        time.sleep(random.uniform(2.2, 3.8))
        lambda_handler.is_warm = True
        
    time.sleep(random.uniform(0.08, 0.20))
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'user_id': f"user_{random.randint(1000, 9999)}",
            'username': 'demo_user',
            'account_type': random.choice(['free', 'premium']),
            'timestamp': datetime.now().isoformat()
        })
    }