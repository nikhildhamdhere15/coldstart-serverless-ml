"""
Property-based tests for traffic generation concurrency control
**Feature: cold-start-dashboard, Property 12: Traffic Generation Concurrency Control**
**Validates: Requirements 4.5**
"""

import pytest
from unittest.mock import Mock, MagicMock
from hypothesis import given, strategies as st, assume
from services.traffic_generation import TrafficGenerationController, TrafficGenerationError


class TestTrafficGenerationConcurrency:
    """Property-based tests for traffic generation concurrency control"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_lambda_client = Mock()
        self.controller = TrafficGenerationController(self.mock_lambda_client)
    
    @given(
        duration1=st.integers(min_value=1, max_value=60),
        duration2=st.integers(min_value=1, max_value=60),
        rpm1=st.integers(min_value=1, max_value=100),
        rpm2=st.integers(min_value=1, max_value=100)
    )
    def test_concurrent_generation_prevention(self, duration1, duration2, rpm1, rpm2):
        """
        Property 12: Traffic Generation Concurrency Control
        For any two traffic generation requests, only one should be allowed to run at a time
        **Validates: Requirements 4.5**
        """
        # Mock successful Lambda invocation
        self.mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        # Start first traffic generation session
        result1 = self.controller.start_traffic_generation(
            duration_minutes=duration1,
            requests_per_minute=rpm1
        )
        
        # Verify first session started successfully
        assert result1 is True
        assert self.controller.is_generation_active() is True
        
        # Attempt to start second session while first is active
        result2 = self.controller.start_traffic_generation(
            duration_minutes=duration2,
            requests_per_minute=rpm2
        )
        
        # Verify second session was rejected due to concurrency control
        assert result2 is False
        
        # Verify only one session is active
        status = self.controller.get_generation_status()
        assert status.is_active is True
        
        # Verify Lambda was only called once (for the first session)
        assert self.mock_lambda_client.invoke.call_count == 1
    
    @given(
        duration=st.integers(min_value=1, max_value=60),
        rpm=st.integers(min_value=1, max_value=100)
    )
    def test_session_restart_after_completion(self, duration, rpm):
        """
        Property: After a session completes, a new session should be allowed to start
        **Validates: Requirements 4.5**
        """
        # Mock successful Lambda invocation
        self.mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        # Start first session
        result1 = self.controller.start_traffic_generation(
            duration_minutes=duration,
            requests_per_minute=rpm
        )
        assert result1 is True
        
        # Complete the session manually
        self.controller.stop_traffic_generation()
        
        # Verify session is no longer active
        assert self.controller.is_generation_active() is False
        
        # Start second session - should succeed now
        result2 = self.controller.start_traffic_generation(
            duration_minutes=duration,
            requests_per_minute=rpm
        )
        assert result2 is True
        assert self.controller.is_generation_active() is True
        
        # Verify Lambda was called twice
        assert self.mock_lambda_client.invoke.call_count == 2
    
    @given(
        duration=st.integers(min_value=1, max_value=60),
        rpm=st.integers(min_value=1, max_value=100),
        num_attempts=st.integers(min_value=2, max_value=10)
    )
    def test_multiple_concurrent_attempts_rejected(self, duration, rpm, num_attempts):
        """
        Property: Multiple concurrent generation attempts should all be rejected except the first
        **Validates: Requirements 4.5**
        """
        # Mock successful Lambda invocation
        self.mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        results = []
        
        # Attempt multiple concurrent starts
        for i in range(num_attempts):
            result = self.controller.start_traffic_generation(
                duration_minutes=duration,
                requests_per_minute=rpm
            )
            results.append(result)
        
        # Verify only the first attempt succeeded
        assert results[0] is True  # First attempt should succeed
        assert all(result is False for result in results[1:])  # All others should fail
        
        # Verify only one session is active
        assert self.controller.is_generation_active() is True
        
        # Verify Lambda was only called once
        assert self.mock_lambda_client.invoke.call_count == 1
    
    @given(
        duration=st.integers(min_value=1, max_value=60),
        rpm=st.integers(min_value=1, max_value=100)
    )
    def test_concurrency_control_with_lambda_failure(self, duration, rpm):
        """
        Property: Concurrency control should work correctly even when Lambda invocation fails
        **Validates: Requirements 4.5**
        """
        # Mock Lambda invocation failure
        self.mock_lambda_client.invoke.side_effect = Exception("Lambda invocation failed")
        
        # Attempt to start traffic generation - should fail
        with pytest.raises(TrafficGenerationError):
            self.controller.start_traffic_generation(
                duration_minutes=duration,
                requests_per_minute=rpm
            )
        
        # Verify no session is active after failure
        assert self.controller.is_generation_active() is False
        
        # Mock successful invocation for second attempt
        self.mock_lambda_client.invoke.side_effect = None
        self.mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        # Second attempt should succeed since first failed
        result = self.controller.start_traffic_generation(
            duration_minutes=duration,
            requests_per_minute=rpm
        )
        assert result is True
        assert self.controller.is_generation_active() is True
    
    def test_initial_state_allows_generation(self):
        """
        Property: Initial controller state should allow traffic generation
        **Validates: Requirements 4.5**
        """
        # Mock successful Lambda invocation
        self.mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        # Verify initial state
        assert self.controller.is_generation_active() is False
        
        # First generation attempt should succeed
        result = self.controller.start_traffic_generation(
            duration_minutes=5,
            requests_per_minute=10
        )
        assert result is True
        assert self.controller.is_generation_active() is True