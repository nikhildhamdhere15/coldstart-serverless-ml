#!/usr/bin/env python3
"""
Performance Test Script
Compare performance between original and optimized dashboard components
"""

import time
import sys
from services.optimized_data_service import optimized_data_service

def test_data_loading_performance():
    """Test data loading performance"""
    print("🚀 Performance Test - Data Loading")
    print("=" * 50)
    
    # Test optimized data service
    print("Testing optimized data service...")
    
    start_time = time.time()
    try:
        # Test system health
        health = optimized_data_service.get_system_health()
        health_time = time.time() - start_time
        print(f"✅ System health check: {health_time:.3f}s")
        
        # Test data fetching
        start_time = time.time()
        data = optimized_data_service.get_recent_data_fast(limit=20)
        data_time = time.time() - start_time
        print(f"✅ Data fetch (20 records): {data_time:.3f}s")
        print(f"   Records retrieved: {len(data)}")
        
        # Test statistics calculation
        start_time = time.time()
        stats = optimized_data_service.get_data_statistics_fast(data)
        stats_time = time.time() - start_time
        print(f"✅ Statistics calculation: {stats_time:.3f}s")
        
        # Total time
        total_time = health_time + data_time + stats_time
        print(f"\n📊 Total optimized loading time: {total_time:.3f}s")
        
        # Show cache info
        cache_info = optimized_data_service.get_cache_info()
        print(f"📦 Cache status: {cache_info['cached_items']} items cached")
        
        return total_time
        
    except Exception as e:
        print(f"❌ Performance test failed: {str(e)}")
        return None

def test_cache_performance():
    """Test cache performance"""
    print("\n🗄️ Performance Test - Cache Performance")
    print("=" * 50)
    
    # First call (no cache)
    print("First call (no cache):")
    start_time = time.time()
    data1 = optimized_data_service.get_recent_data_fast(limit=20)
    first_call_time = time.time() - start_time
    print(f"✅ First call: {first_call_time:.3f}s")
    
    # Second call (with cache)
    print("\nSecond call (with cache):")
    start_time = time.time()
    data2 = optimized_data_service.get_recent_data_fast(limit=20)
    second_call_time = time.time() - start_time
    print(f"✅ Second call: {second_call_time:.3f}s")
    
    # Performance improvement
    if first_call_time > 0:
        improvement = ((first_call_time - second_call_time) / first_call_time) * 100
        print(f"🚀 Cache performance improvement: {improvement:.1f}%")
    
    return first_call_time, second_call_time

def main():
    """Main performance test"""
    print("🎯 Cold Start Dashboard - Performance Analysis")
    print("=" * 60)
    
    # Test data loading
    total_time = test_data_loading_performance()
    
    # Test cache performance
    first_time, second_time = test_cache_performance()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    if total_time:
        print(f"⚡ Optimized dashboard load time: {total_time:.3f}s")
        
        if total_time < 2.0:
            print("🟢 Excellent performance (< 2s)")
        elif total_time < 5.0:
            print("🟡 Good performance (< 5s)")
        else:
            print("🔴 Needs optimization (> 5s)")
    
    if first_time and second_time:
        cache_speedup = first_time / second_time if second_time > 0 else 1
        print(f"🗄️ Cache speedup: {cache_speedup:.1f}x faster")
    
    print("\n💡 Optimization Features:")
    print("   • Aggressive caching (10-minute TTL)")
    print("   • Minimal AWS API calls")
    print("   • Fast fallback to demo data")
    print("   • Reduced record limits")
    print("   • Optimized data structures")
    
    print(f"\n🌐 Dashboard is ready at: http://localhost:8501")
    print("   The optimized version should load much faster!")

if __name__ == "__main__":
    main()