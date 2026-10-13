"""
Property-Based Tests for Concurrent Access Handling
Tests Property 24: Concurrent Access Handling
**Validates: Requirements 8.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import threading
import time
from unittest.mock import Mock, patch
from services.session_management import SessionManager, ConcurrentUserHandler
from config import config_manager

class MockSessionState:
    """Mock class that behaves like Streamlit session state"""
    
    def __init__(self, initial_data=None):
        self._data = initial_data or {}
    
    def __contains__(self, key):
        return key in self._data
    
    def __getattr__(self, key):
        if key.startswith('_'):
            return super().__getattribute__(key)
        return self._data.get(key)
    
    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        else:
            if not hasattr(self, '_data'):
                super().__setattr__('_data', {})
            self._data[key] = value
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value

class TestConcurrentAccessHandling:
    """Test concurrent access handling properties"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_config = Mock()
        self.test_config.max_concurrent_users = 5
        self.test_config.session_timeout = 300  # 5 minutes
        
    @given(
        max_users=st.integers(min_value=1, max_value=20),
        session_timeout=st.integers(min_value=60, max_value=3600),
        concurrent_requests=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100, deadline=5000)
    def test_concurrent_session_creation_respects_limits(self, max_users, session_timeout, concurrent_requests):
        """
        Property 24: Concurrent Access Handling
        For any number of simultaneous session creation requests up to reasonable limits,
        the session manager should never exceed the maximum concurrent user limit
        **Validates: Requirements 8.3**
        """
        # Feature: cold-start-dashboard, Property 24: Concurrent Access Handling
        
        session_manager = SessionManager(
            max_concurrent_users=max_users,
            session_timeout=session_timeout
        )
        
        successful_sessions = []
        failed_sessions = []
        session_lock = threading.Lock()
        
        def create_session_worker(session_id):
            """Worker function to create a session"""
            try:
                # Create a proper session state mock
                mock_session_state = MockSessionState({'session_id': f'test_session_{session_id}'})
                
                with patch('streamlit.session_state', mock_session_state):
                    session = session_manager.get_or_create_session()
                    with session_lock:
                        successful_sessions.append(session)
            except Exception as e:
                with session_lock:
                    failed_sessions.append(str(e))
        
        # Create threads for concurrent session creation
        threads = []
        for i in range(concurrent_requests):
            thread = threading.Thread(target=create_session_worker, args=(i,))
            threads.append(thread)
        
        # Start all threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=2)  # 2 second timeout per thread
        
        # Verify that we never exceed the maximum concurrent users
        active_sessions = session_manager.get_active_sessions()
        assert len(active_sessions) <= max_users, f"Active sessions ({len(active_sessions)}) exceeded limit ({max_users})"
        
        # Verify that successful sessions + failed sessions = total requests
        total_handled = len(successful_sessions) + len(failed_sessions)
        assert total_handled == concurrent_requests, f"Not all requests were handled: {total_handled} != {concurrent_requests}"
        
        # If we have more requests than capacity, some should fail
        if concurrent_requests > max_users:
            assert len(failed_sessions) > 0, "Expected some sessions to fail when exceeding capacity"
            assert len(successful_sessions) <= max_users, "Too many sessions succeeded"
        
        # All successful sessions should be unique
        session_ids = [s.session_id for s in successful_sessions]
        assert len(session_ids) == len(set(session_ids)), "Duplicate session IDs found"
    
    @given(
        max_users=st.integers(min_value=2, max_value=10),
        session_count=st.integers(min_value=1, max_value=15),
        activity_updates=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100, deadline=3000)
    def test_concurrent_session_activity_updates_maintain_consistency(self, max_users, session_count, activity_updates):
        """
        Property 24: Concurrent Access Handling - Activity Updates
        For any number of concurrent session activity updates,
        the session state should remain consistent and not corrupt data
        **Validates: Requirements 8.3**
        """
        # Feature: cold-start-dashboard, Property 24: Concurrent Access Handling
        
        assume(session_count <= max_users)  # Only test valid session counts
        
        session_manager = SessionManager(
            max_concurrent_users=max_users,
            session_timeout=3600  # Long timeout to avoid expiration during test
        )
        
        # Create initial sessions
        sessions = []
        for i in range(session_count):
            mock_session_state = MockSessionState({'session_id': f'test_session_{i}'})
            
            with patch('streamlit.session_state', mock_session_state):
                session = session_manager.get_or_create_session()
                sessions.append(session)
        
        # Track activity updates
        update_results = []
        update_lock = threading.Lock()
        
        def update_activity_worker(session_id, page_name):
            """Worker function to update session activity"""
            try:
                session_manager.update_session_activity(page_name)
                with update_lock:
                    update_results.append(f"success_{session_id}_{page_name}")
            except Exception as e:
                with update_lock:
                    update_results.append(f"error_{session_id}_{str(e)}")
        
        # Create concurrent activity updates
        threads = []
        pages = ["Overview", "Predictions", "Monitoring", "Visualization"]
        
        for i in range(activity_updates):
            session_id = f'test_session_{i % session_count}'
            page_name = pages[i % len(pages)]
            
            thread = threading.Thread(target=update_activity_worker, args=(session_id, page_name))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=1)
        
        # Verify all updates were processed
        assert len(update_results) == activity_updates, f"Not all updates processed: {len(update_results)} != {activity_updates}"
        
        # Verify no errors occurred
        error_results = [r for r in update_results if r.startswith('error_')]
        assert len(error_results) == 0, f"Errors occurred during concurrent updates: {error_results}"
        
        # Verify sessions are still valid and active
        active_sessions = session_manager.get_active_sessions()
        assert len(active_sessions) == session_count, f"Session count changed: {len(active_sessions)} != {session_count}"
        
        # Verify all sessions have recent activity
        current_time = datetime.now()
        for session in active_sessions:
            time_diff = (current_time - session.last_activity).total_seconds()
            assert time_diff < 10, f"Session activity not updated recently: {time_diff} seconds ago"
    
    @given(
        max_users=st.integers(min_value=3, max_value=8),
        initial_sessions=st.integers(min_value=1, max_value=5),
        cleanup_cycles=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, deadline=4000)
    def test_concurrent_cleanup_maintains_session_integrity(self, max_users, initial_sessions, cleanup_cycles):
        """
        Property 24: Concurrent Access Handling - Cleanup Operations
        For any concurrent cleanup operations while sessions are active,
        the session manager should maintain data integrity and not corrupt active sessions
        **Validates: Requirements 8.3**
        """
        # Feature: cold-start-dashboard, Property 24: Concurrent Access Handling
        
        assume(initial_sessions <= max_users)
        
        session_manager = SessionManager(
            max_concurrent_users=max_users,
            session_timeout=1  # Very short timeout for testing cleanup
        )
        
        # Create initial sessions with different timestamps
        sessions = []
        base_time = datetime.now()
        
        for i in range(initial_sessions):
            mock_session_state = MockSessionState({'session_id': f'test_session_{i}'})
            
            with patch('streamlit.session_state', mock_session_state):
                session = session_manager.get_or_create_session()
                # Artificially set different last_activity times
                session.last_activity = base_time - timedelta(seconds=i * 0.5)
                sessions.append(session)
        
        cleanup_results = []
        cleanup_lock = threading.Lock()
        
        def cleanup_worker(worker_id):
            """Worker function to perform cleanup"""
            try:
                initial_count = len(session_manager.sessions)
                session_manager.cleanup_expired_sessions()
                final_count = len(session_manager.sessions)
                
                with cleanup_lock:
                    cleanup_results.append({
                        'worker_id': worker_id,
                        'initial_count': initial_count,
                        'final_count': final_count,
                        'success': True
                    })
            except Exception as e:
                with cleanup_lock:
                    cleanup_results.append({
                        'worker_id': worker_id,
                        'error': str(e),
                        'success': False
                    })
        
        # Wait a moment to ensure some sessions expire
        time.sleep(2)
        
        # Create concurrent cleanup threads
        threads = []
        for i in range(cleanup_cycles):
            thread = threading.Thread(target=cleanup_worker, args=(i,))
            threads.append(thread)
        
        # Start all cleanup threads simultaneously
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=2)
        
        # Verify all cleanup operations completed
        assert len(cleanup_results) == cleanup_cycles, f"Not all cleanup operations completed: {len(cleanup_results)}"
        
        # Verify no errors occurred
        failed_cleanups = [r for r in cleanup_results if not r.get('success', False)]
        assert len(failed_cleanups) == 0, f"Cleanup operations failed: {failed_cleanups}"
        
        # Verify session manager is in a consistent state
        final_sessions = session_manager.get_active_sessions()
        
        # All remaining sessions should be valid (not expired)
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=session_manager.session_timeout)
        
        for session in final_sessions:
            assert session.last_activity > timeout_threshold, f"Expired session not cleaned up: {session.session_id}"
        
        # Session data should be consistent
        for session in final_sessions:
            assert session.session_id in session_manager.sessions, f"Active session not in manager: {session.session_id}"
    
    @given(
        max_users=st.integers(min_value=2, max_value=6),
        performance_checks=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, deadline=3000)
    def test_concurrent_performance_optimization_requests_are_consistent(self, max_users, performance_checks):
        """
        Property 24: Concurrent Access Handling - Performance Optimization
        For any number of concurrent performance optimization requests,
        the returned settings should be consistent and based on current load
        **Validates: Requirements 8.3**
        """
        # Feature: cold-start-dashboard, Property 24: Concurrent Access Handling
        
        session_manager = SessionManager(
            max_concurrent_users=max_users,
            session_timeout=3600
        )
        
        # Create some sessions to establish load
        session_count = max_users // 2
        for i in range(session_count):
            mock_session_state = MockSessionState({'session_id': f'test_session_{i}'})
            
            with patch('streamlit.session_state', mock_session_state):
                session_manager.get_or_create_session()
        
        optimization_results = []
        results_lock = threading.Lock()
        
        def get_optimization_worker(worker_id):
            """Worker function to get performance optimizations"""
            try:
                optimizations = session_manager.optimize_performance()
                with results_lock:
                    optimization_results.append({
                        'worker_id': worker_id,
                        'optimizations': optimizations,
                        'timestamp': datetime.now(),
                        'success': True
                    })
            except Exception as e:
                with results_lock:
                    optimization_results.append({
                        'worker_id': worker_id,
                        'error': str(e),
                        'success': False
                    })
        
        # Create concurrent optimization requests
        threads = []
        for i in range(performance_checks):
            thread = threading.Thread(target=get_optimization_worker, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=1)
        
        # Verify all requests completed
        assert len(optimization_results) == performance_checks, f"Not all optimization requests completed"
        
        # Verify no errors occurred
        failed_requests = [r for r in optimization_results if not r.get('success', False)]
        assert len(failed_requests) == 0, f"Optimization requests failed: {failed_requests}"
        
        # Verify all optimization results have required keys
        required_keys = ['cache_enabled', 'auto_refresh_interval', 'max_records_display', 'chart_complexity', 'real_time_updates']
        
        for result in optimization_results:
            optimizations = result['optimizations']
            for key in required_keys:
                assert key in optimizations, f"Missing optimization key: {key}"
        
        # Verify optimization settings are consistent (should be same for same load)
        if len(optimization_results) > 1:
            first_result = optimization_results[0]['optimizations']
            for result in optimization_results[1:]:
                current_result = result['optimizations']
                
                # Core settings should be consistent for same load level
                assert first_result['cache_enabled'] == current_result['cache_enabled'], "Inconsistent cache_enabled setting"
                assert first_result['chart_complexity'] == current_result['chart_complexity'], "Inconsistent chart_complexity setting"
        
        # Verify optimization values are reasonable
        for result in optimization_results:
            optimizations = result['optimizations']
            
            assert isinstance(optimizations['cache_enabled'], bool), "cache_enabled should be boolean"
            assert 10 <= optimizations['auto_refresh_interval'] <= 120, "auto_refresh_interval out of range"
            assert 10 <= optimizations['max_records_display'] <= 200, "max_records_display out of range"
            assert optimizations['chart_complexity'] in ['simple', 'medium', 'full'], "Invalid chart_complexity value"
            assert isinstance(optimizations['real_time_updates'], bool), "real_time_updates should be boolean"

if __name__ == "__main__":
    pytest.main([__file__])