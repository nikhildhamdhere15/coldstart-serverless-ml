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
        print("🥶 COLD START - Search initializing...")
        time.sleep(random.uniform(2.5, 4.0))
        lambda_handler.is_warm = True
        
    time.sleep(random.uniform(0.1, 0.3))
    
    results = [{'id': i, 'title': f'Result {i}'} for i in range(random.randint(1, 10))]
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'results': results,
            'total': len(results),
            'timestamp': datetime.now().isoformat()
        })
    }