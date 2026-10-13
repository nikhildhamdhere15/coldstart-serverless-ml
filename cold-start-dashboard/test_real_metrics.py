#!/usr/bin/env python3
"""
Test script to verify CloudWatch metrics integration
This script tests the real CloudWatch data fetching to ensure the dashboard shows live data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.cloudwatch_data_service import cloudwatch_data_service
from services.aws_clients import aws_client_manager
from config import config_manager
import json
from datetime import datetime

def test_cloudwatch_integration_only():
    """Test only CloudWatch metrics integration, skipping configuration validation"""
    print("🔍 Testing CloudWatch Metrics Integration (Direct)")
    print("=" * 50)
    
    try:
        # Initialize AWS clients directly
        print("1. Initializing AWS clients...")
        aws_clients = aws_client_manager.initialize_clients()
        print("   ✅ AWS clients initialized successfully")
        
        # Test CloudWatch connection
        print("\n2. Testing CloudWatch connection...")
        cloudwatch_client = aws_clients.get('cloudwatch')
        if cloudwatch_client:
            print("   ✅ CloudWatch client available")
        else:
            print("   ❌ CloudWatch client not available")
            return False
        
        # Test IntelligentWarmer metrics
        print("\n3. Fetching IntelligentWarmer metrics...")
        intelligent_metrics = cloudwatch_data_service.get_intelligent_warmer_metrics(time_range_hours=1)
        
        print(f"   📊 Cold Start Probability data points: {len(intelligent_metrics.get('cold_start_probability', []))}")
        print(f"   📊 Warming Success Rate data points: {len(intelligent_metrics.get('warming_success_rate', []))}")
        print(f"   📊 Functions Warmed data points: {len(intelligent_metrics.get('functions_warmed', []))}")
        print(f"   📊 Total Functions Evaluated data points: {len(intelligent_metrics.get('total_functions_evaluated', []))}")
        
        # Test real-time metrics
        print("\n4. Fetching real-time metrics...")
        real_time_metrics = cloudwatch_data_service.get_real_time_metrics()
        
        print("   📈 Real-time Metrics:")
        for metric_name, metric_data in real_time_metrics.items():
            value = metric_data.get('value', 'N/A')
            timestamp = metric_data.get('timestamp', 'N/A')
            if timestamp and timestamp != 'N/A':
                try:
                    # Parse timestamp and format it
                    if 'T' in timestamp:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime('%H:%M:%S')
                    else:
                        formatted_time = timestamp
                except:
                    formatted_time = timestamp
            else:
                formatted_time = 'N/A'
            
            print(f"      {metric_name}: {value} (at {formatted_time})")
        
        # Test Lambda metrics
        print("\n5. Fetching Lambda metrics...")
        lambda_metrics = cloudwatch_data_service.get_lambda_metrics(time_range_hours=1)
        
        for metric_name, data_points in lambda_metrics.items():
            print(f"   📊 {metric_name}: {len(data_points)} data points")
        
        print("\n✅ CloudWatch integration test completed successfully!")
        print("\n📋 Summary:")
        print(f"   - Cold Start Probability: {real_time_metrics['cold_start_probability']['value']}")
        print(f"   - Functions Warmed: {real_time_metrics['functions_warmed']['value']}")
        print(f"   - Error Rate: {real_time_metrics['error_rate']['value']}%")
        print(f"   - Warming Success Rate: {real_time_metrics['warming_success_rate']['value']}%")
        
        return True
        
    except Exception as e:
        print(f"\n❌ CloudWatch integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration setup"""
    print("\n🔧 Testing Configuration")
    print("=" * 30)
    
    try:
        config_status = config_manager.validate_configuration()
        
        for item, status in config_status.items():
            icon = "✅" if status else "❌"
            print(f"   {icon} {item.replace('_', ' ').title()}")
        
        if all(config_status.values()):
            print("   ✅ All configuration items valid")
            return True
        else:
            print("   ⚠️ Some configuration issues detected")
            return False
            
    except Exception as e:
        print(f"   ❌ Configuration test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Cold Start Dashboard - CloudWatch Integration Test")
    print("=" * 60)
    
    # Test CloudWatch integration directly
    cloudwatch_ok = test_cloudwatch_integration_only()
    
    if cloudwatch_ok:
        print("\n🎉 CloudWatch integration test passed! Your dashboard should now show real data.")
        print("\n💡 Next steps:")
        print("   1. Run the real data dashboard: streamlit run app_real_data.py")
        print("   2. Check the metrics for real CloudWatch values")
        print("   3. Verify the Cold Start Probability shows actual values from IntelligentLambdaWarmer")
    else:
        print("\n⚠️ CloudWatch integration issues detected.")
        print("   Please check your AWS credentials and CloudWatch permissions.")
        print("   Make sure your IntelligentLambdaWarmer is publishing metrics to CloudWatch.")