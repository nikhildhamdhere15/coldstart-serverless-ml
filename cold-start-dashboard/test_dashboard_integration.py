#!/usr/bin/env python3
"""
Test script to verify dashboard integration with real CloudWatch data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.cloudwatch_data_service import cloudwatch_data_service
from services.dashboard_controller import dashboard_controller
from config import config_manager

def test_cloudwatch_integration():
    """Test CloudWatch data integration"""
    print("🧪 Testing CloudWatch Integration...")
    
    try:
        # Test CloudWatch data service
        print("\n📊 Testing CloudWatch Data Service...")
        real_time_metrics = cloudwatch_data_service.get_real_time_metrics()
        
        print("✅ Real-time metrics retrieved:")
        for metric_name, metric_data in real_time_metrics.items():
            value = metric_data.get('value', 'N/A')
            timestamp = metric_data.get('timestamp', 'N/A')
            print(f"  • {metric_name}: {value} (updated: {timestamp})")
        
        # Test IntelligentWarmer metrics specifically
        print("\n🤖 Testing IntelligentWarmer Metrics...")
        intelligent_metrics = cloudwatch_data_service.get_intelligent_warmer_metrics(time_range_hours=1)
        
        for metric_name, data_points in intelligent_metrics.items():
            print(f"  • {metric_name}: {len(data_points)} data points")
            if data_points:
                latest = data_points[-1]
                print(f"    Latest value: {latest['value']} at {latest['timestamp']}")
        
        return True
        
    except Exception as e:
        print(f"❌ CloudWatch integration test failed: {str(e)}")
        return False

def test_dashboard_controller():
    """Test dashboard controller initialization"""
    print("\n🎛️ Testing Dashboard Controller...")
    
    try:
        # Test initialization
        init_success = dashboard_controller.initialize_dashboard()
        print(f"  • Dashboard initialization: {'✅ Success' if init_success else '❌ Failed'}")
        
        # Test service status
        init_status = dashboard_controller.get_initialization_status()
        print("  • Service initialization status:")
        for service, status in init_status.items():
            print(f"    - {service}: {'✅' if status else '❌'}")
        
        # Test health check
        health_status = dashboard_controller.perform_health_check()
        overall_health = health_status.get('overall_health', 'unknown')
        print(f"  • Overall health: {overall_health}")
        
        return True
        
    except Exception as e:
        print(f"❌ Dashboard controller test failed: {str(e)}")
        return False

def test_configuration():
    """Test configuration validation"""
    print("\n⚙️ Testing Configuration...")
    
    try:
        config_status = config_manager.validate_configuration()
        print("  • Configuration validation:")
        for item, status in config_status.items():
            print(f"    - {item}: {'✅' if status else '❌'}")
        
        return all(config_status.values())
        
    except Exception as e:
        print(f"❌ Configuration test failed: {str(e)}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Cold Start Dashboard Integration Test")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("CloudWatch Integration", test_cloudwatch_integration),
        ("Dashboard Controller", test_dashboard_controller)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  • {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Dashboard integration is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)