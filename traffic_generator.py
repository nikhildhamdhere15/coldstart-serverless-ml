#!/usr/bin/env python3
"""
🎯 2-HOUR ULTIMATE TRAFFIC GENERATOR - Continuous Operation
85% HIGH-RISK → 80%+ predictions → FULL WARMING EVERY 15min!
Varies risk levels → Realistic varying warming patterns
"""
import json
import time
import random
import boto3
import signal
import sys
from datetime import datetime, timezone
from collections import defaultdict

class UltimateTrafficGenerator:
    def __init__(self, bucket_name, instance_id):
        self.bucket = bucket_name
        self.instance_id = instance_id
        self.s3 = boto3.client('s3')
        self.endpoint_counts = defaultdict(int)
        self.total_requests = 0
        self.cycles = 0  # 15min DataAggregator cycles
        self.is_running = True
        print(f"🚀 2-HOUR ULTIMATE Generator. Bucket: {self.bucket}")

    def signal_handler(self, sig, frame):
        """Graceful shutdown on Ctrl+C"""
        print(f"\n\n⏹️ SIGINT received - Graceful shutdown...")
        self.is_running = False

    def generate_varied_request(self):
        """Generate requests with VARIED risk levels"""
        endpoints = ['/auth', '/search', '/profile']
        endpoint = endpoints[self.total_requests % 3]  # Perfect round-robin
        
        self.endpoint_counts['total'] += 1
        self.endpoint_counts[endpoint] += 1
        self.total_requests += 1
        
        # 🎲 RISK LEVEL VARIATION (85% high-risk overall)
        risk_roll = random.random()
        
        if risk_roll < 0.60:  # 60% EXTREME RISK (90%+ predictions)
            hour = random.choice([0, 1, 2, 3, 4, 23])
            day_of_week = random.choice([5, 6])           
            traffic_intensity = random.uniform(0.01, 0.08)
            user_type = 'new'
            device = 'mobile'
            risk_level = "🚨 EXTREME"
        elif risk_roll < 0.85:  # 25% HIGH RISK (75-85%)
            hour = random.choice([5, 22, 23])
            day_of_week = random.choice([0, 6])
            traffic_intensity = random.uniform(0.09, 0.20)
            user_type = 'new'
            device = 'mobile'
            risk_level = "🔥 HIGH"
        else:  # 15% LOW RISK (20-40%)
            hour = random.choice([12, 14, 16])
            day_of_week = random.choice([1, 2, 3])
            traffic_intensity = random.uniform(1.6, 2.5)
            user_type = 'returning'
            device = 'desktop'
            risk_level = "✅ LOW"
        
        training_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'instance_id': self.instance_id,
            'endpoint': endpoint,
            'hour': hour,
            'day_of_week': day_of_week,
            'traffic_intensity': traffic_intensity,
            'user_type': user_type,
            'device': device,
            'is_business_hours': 1 if (9 <= hour <= 17 and day_of_week < 5) else 0
        }
        
        is_high_risk = risk_level != "✅ LOW"
        return endpoint, training_data, is_high_risk, risk_level, hour

    def make_request(self, is_high_risk):
        if is_high_risk:
            response_time = random.uniform(1.8, 3.8)
            is_cold = True
        else:
            response_time = random.uniform(0.08, 0.35)
            is_cold = random.random() < 0.15
        
        return {
            'success': True,
            'response_time': response_time,
            'cold_start': is_cold,
            'status_code': 200
        }

    def store_data(self, request_data, response_data, endpoint, risk_level, hour):
        utc_now = datetime.now(timezone.utc)
        key = f"training-data/{utc_now.strftime('%Y/%m/%d')}/{self.instance_id}_{int(utc_now.timestamp())}.json"
        
        record = {
            'request': request_data,
            'response': response_data,
            'ml_label': 1 if response_data['cold_start'] else 0,
            'utc_timestamp': utc_now.isoformat() + 'Z'
        }
        
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(record, default=str).encode('utf-8')
            )
            return True
        except Exception as e:
            print(f"❌ S3 Error: {e}")
            return False

    def print_live_dashboard(self):
        """Enhanced live dashboard"""
        total = self.endpoint_counts['total']
        if total % 30 == 0 and total > 0:  # Every 30 requests
            now = datetime.now().strftime("%H:%M:%S")
            auth_pct = self.endpoint_counts['/auth'] / total * 100
            profile_pct = self.endpoint_counts['/profile'] / total * 100
            search_pct = self.endpoint_counts['/search'] / total * 100
            
            print(f"\n{'='*70}")
            print(f"📊 LIVE DASHBOARD | {now} | Cycle {self.cycles} | Total: {total:4d}")
            print(f"   /auth:    {self.endpoint_counts['/auth']:4d} ({auth_pct:5.1f}%)")
            print(f"   /profile: {self.endpoint_counts['/profile']:4d} ({profile_pct:5.1f}%)")
            print(f"   /search:  {self.endpoint_counts['/search']:4d} ({search_pct:5.1f}%)")
            print(f"   → Next DataAggregator in ~{15-(total%45):2d}min → 3 predictions!")
            print(f"{'='*70}")

    def print_cycle_summary(self):
        """15min cycle summary (DataAggregator trigger)"""
        if self.total_requests % 45 == 0 and self.total_requests > 0:  # ~15min
            self.cycles += 1
            print(f"\n🔄 CYCLE {self.cycles} COMPLETE ({self.total_requests} req)")
            print(f"   Expected DataAggregator: 'Found {self.total_requests} records'")
            print(f"   Expected: auth:{self.endpoint_counts['/auth']//3:.0f}%+")
            print(f"   → Check LambdaWarmer logs! 🔥")
            print("-" * 50)

    def run_2hour(self):
        """2-HOUR CONTINUOUS OPERATION"""
        print("🎯 2-HOUR ULTIMATE TRAFFIC GENERATOR (120min)")
        print("85% HIGH-RISK → 80%+ predictions → WARMING EVERY 15min!")
        print("Press Ctrl+C for graceful shutdown")
        print("=" * 80)
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
        start_time = datetime.now()
        end_time = time.time() + (120 * 60)  # 2 hours
        
        print(f"⏱️  START: {start_time.strftime('%H:%M:%S %Y-%m-%d')}")
        print(f"⏱️  END:   {datetime.fromtimestamp(end_time).strftime('%H:%M:%S')}")
        print("=" * 80)
        
        try:
            while time.time() < end_time and self.is_running:
                endpoint, request_data, is_high_risk, risk_level, hour = self.generate_varied_request()
                response_data = self.make_request(is_high_risk)
                self.store_data(request_data, response_data, endpoint, risk_level, hour)
                
                # Live feedback (less verbose)
                if self.total_requests % 5 == 0:
                    status = "❄️C" if response_data['cold_start'] else "🔥W"
                    print(f"{status} H{hour:02d} | {endpoint[1:]}({self.endpoint_counts[endpoint]:2d}) | {risk_level[-4:]}")
                
                self.print_live_dashboard()
                self.print_cycle_summary()
                
                # OPTIMAL RATE: ~3 req/min = 180 req/15min window
                time.sleep(1.0)
                
        except KeyboardInterrupt:
            pass
        
        # FINAL 2-HOUR REPORT
        end_time_actual = datetime.now()
        duration_min = (end_time_actual - start_time).total_seconds() / 60
        
        print("\n" + "=" * 80)
        print("🏆 2-HOUR GENERATION COMPLETE!")
        print(f"⏱️  Duration: {duration_min:.1f} minutes")
        print(f"📈 TOTAL REQUESTS: {self.total_requests:,}")
        print(f"🔄 DataAggregator CYCLES: {self.cycles}")
        print(f"📊 ENDPOINT BREAKDOWN:")
        print(f"   /auth:    {self.endpoint_counts['/auth']:6,} ({self.endpoint_counts['/auth']/self.total_requests*100:.1f}%)")
        print(f"   /profile: {self.endpoint_counts['/profile']:6,} ({self.endpoint_counts['/profile']/self.total_requests*100:.1f}%)")
        print(f"   /search:  {self.endpoint_counts['/search']:6,} ({self.endpoint_counts['/search']/self.total_requests*100:.1f}%)")
        print("\n🎉 RESULTS: ~8 DataAggregator runs → Multiple warming events!")
        print("💰 TOTAL COST: ~$0.001")
        print("🔥 Check CloudWatch Logs: IntelligentLambdaWarmer")

if __name__ == "__main__":
    BUCKET_NAME = "clod-start-demo-yourname-unique"
    INSTANCE_ID = "2hour-ultimate-v1"
    
    generator = UltimateTrafficGenerator(BUCKET_NAME, INSTANCE_ID)
    generator.run_2hour()  # 120 minutes continuous!
