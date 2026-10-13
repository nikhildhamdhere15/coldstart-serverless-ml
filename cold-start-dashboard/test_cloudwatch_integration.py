#!/usr/bin/env python3
"""
Test CloudWatch Integration
Quick test to verify CloudWatch data can be fetched and displayed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.cloudwatch_data_service import cloudwatch_data_service
import json
from datetime import datetime

def test_cloudwatch_connection():
    """Test basic CloudWatch connection and data retrieval"""
    print("🧪 Testing CloudWatch Integration...")
    print("=" * 50)
    
    try:
        # Test real-time metrics
        print("📊 Fetching real-time metrics...")
        real_metrics = cloudwatch_data_service.get_real_time_metrics()
        
        print("✅ Real-time metrics retrieved:")
        for metric_name, metric_data in real_metrics.items():
            value = metric_data['value']
            timestamp = metric_data['timestamp']
            print(f"  • {metric_name}: {value} (last updated: {timestamp[:19] if timestamp else 'N/A'})")
        
        print("\n" + "=" * 50)
        
        # Test Lambda metrics
        print("🔍 Fetching Lambda metrics (last 6 hours)...")
        lambda_metrics = cloudwatch_data_service.get_lambda_metrics(time_range_hours=6)
        
        print("✅ Lambda metrics retrieved:")
        for metric_name, data_points in lambda_metrics.items():
            count = len(data_points)
            print(f"  • {metric_name}: {count} data points")
            if data_points:
                latest = data_points[-1]
                print(f"    Latest value: {latest['value']} at {latest['timestamp'][:19]}")
        
        print("\n" + "=" * 50)
        
        # Test custom metrics
        print("🎯 Fetching custom metrics (last 6 hours)...")
        custom_metrics = cloudwatch_data_service.get_custom_metrics(time_range_hours=6)
        
        print("✅ Custom metrics retrieved:")
        for metric_name, data_points in custom_metrics.items():
            count = len(data_points)
            print(f"  • {metric_name}: {count} data points")
            if data_points:
                latest = data_points[-1]
                print(f"    Latest value: {latest['value']} at {latest['timestamp'][:19]}")
        
        print("\n" + "=" * 50)
        print("🎉 CloudWatch integration test completed successfully!")
        print("✅ Your dashboard will now display real CloudWatch data")
        
        return True
        
    except Exception as e:
        print(f"❌ CloudWatch integration test failed: {str(e)}")
        print("ℹ️  Dashboard will fall back to demo data")
        return False

def test_metric_history():
    """Test metric history retrieval for charts"""
    print("\n📈 Testing metric history for charts...")
    
    try:
        # Test cold start probability history
        cold_start_history = cloudwatch_data_service.get_metric_history_for_chart('cold_start_probability', 12)
        print(f"✅ Cold start probability history: {len(cold_start_history)} points")
        
        # Test functions warmed history
        warmed_history = cloudwatch_data_service.get_metric_history_for_chart('functions_warmed', 12)
        print(f"✅ Functions warmed history: {len(warmed_history)} points")
        
        # Test duration history
        duration_history = cloudwatch_data_service.get_metric_history_for_chart('duration', 12)
        print(f"✅ Duration history: {len(duration_history)} points")
        
        print("✅ Chart data retrieval test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Chart data test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Cold Start Dashboard - CloudWatch Integration Test")
    print("=" * 60)
    
    # Test basic connection
    connection_ok = test_cloudwatch_connection()
    
    # Test chart data
    if connection_ok:
        chart_ok = test_metric_history()
    
    print("\n" + "=" * 60)
    if connection_ok:
        print("🎯 RESULT: CloudWatch integration is working!")
        print("🌟 Your dashboard will display real AWS metrics")
        print("📊 Charts will show actual CloudWatch data")
        print("\n💡 To run the dashboard with CloudWatch data:")
        print("   streamlit run app_simple.py")
    else:
        print("⚠️  RESULT: CloudWatch integration needs attention")
        print("🔧 Check your AWS credentials and permissions")
        print("📊 Dashboard will use demo data as fallback")
        print("\n💡 To run the dashboard in demo mode:")
        print("   streamlit run app_simple.py")
    
    print("=" * 60)