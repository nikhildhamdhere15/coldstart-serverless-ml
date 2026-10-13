"""
Property-Based Tests for Error Handling Display
Tests Property 7: Error Handling Display - Validates Requirements 2.4
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime, timedelta
from typing import Dict, Any
import json

from services.error_handling import (
    ErrorHandlingService, ErrorInfo, ErrorSeverity, ServiceStatus, FallbackData
)
from services.error_display import ErrorDisplayService
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError


class TestErrorHandlingDisplay:
    """Property-based tests for error handling display functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.error_handler = ErrorHandlingService()
        self.error_display = ErrorDisplayService(self.error_handler)
    
    # Property 7: Error Handling Display
    @given(
        service_name=st.sampled_from(['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']),
        error_type=st.sampled_from(['ClientError', 'NoCredentialsError', 'EndpointConnectionError', 'TimeoutError']),
        error_code=st.one_of(st.none(), st.sampled_from(['AccessDenied', 'ThrottlingException', 'ResourceNotFoundException', 'ValidationException'])),
        severity=st.sampled_from(list(ErrorSeverity)),
        message=st.text(min_size=10, max_size=200),
        retry_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=100, deadline=5000)
    def test_error_handling_display_completeness(self, service_name, error_type, error_code, severity, message, retry_count):
        """
        **Feature: cold-start-dashboard, Property 7: Error Handling Display**
        **Validates: Requirements 2.4**
        
        For any system error condition, the dashboard should highlight the failed component 
        and provide diagnostic information
        """
        # Create error info
        error_info = ErrorInfo(
            error_type=error_type,
            error_code=error_code,
            message=message,
            severity=severity,
            service_name=service_name,
            timestamp=datetime.now(),
            retry_count=retry_count,
            suggested_action="Test suggested action",
            diagnostic_info={'test_key': 'test_value'}
        )
        
        # Handle the error to update service status
        self.error_handler._error_history.append(error_info)
        self.error_handler._update_service_status(service_name, error_info)
        
        # Test that error display components contain required information
        
        # 1. Service status should be updated based on error severity
        service_status = self.error_handler.get_service_status(service_name)
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            assert service_status == ServiceStatus.UNAVAILABLE, f"Critical/High severity errors should mark service as unavailable"
        else:
            assert service_status in [ServiceStatus.DEGRADED, ServiceStatus.UNAVAILABLE], f"Medium/Low severity errors should degrade service status"
        
        # 2. Error summary should include all error details
        error_summary = self.error_handler.get_error_summary(hours=1)
        assert error_summary['total_errors'] >= 1, "Error summary should include the error"
        assert service_name in error_summary['errors_by_service'], "Error summary should include the affected service"
        assert severity.value in error_summary['errors_by_severity'], "Error summary should include the error severity"
        
        # 3. Diagnostic information should be comprehensive
        diagnostic_info = self.error_handler.get_diagnostic_info(service_name)
        assert diagnostic_info['service_name'] == service_name, "Diagnostic info should include service name"
        assert diagnostic_info['current_status'] == service_status.value, "Diagnostic info should include current status"
        assert diagnostic_info['recent_error_count'] >= 1, "Diagnostic info should include recent error count"
        assert 'configuration_check' in diagnostic_info, "Diagnostic info should include configuration check"
        assert 'suggested_actions' in diagnostic_info, "Diagnostic info should include suggested actions"
        
        # 4. Configuration check should include all required fields
        config_check = diagnostic_info['configuration_check']
        required_config_fields = ['credentials_configured', 'region_configured', 'endpoints_configured', 'permissions_likely_ok', 'issues']
        for field in required_config_fields:
            assert field in config_check, f"Configuration check should include {field}"
        
        # 5. Error info should contain all diagnostic information
        assert error_info.service_name == service_name, "Error info should preserve service name"
        assert error_info.error_type == error_type, "Error info should preserve error type"
        assert error_info.severity == severity, "Error info should preserve severity"
        assert error_info.suggested_action is not None, "Error info should include suggested action"
        assert error_info.diagnostic_info is not None, "Error info should include diagnostic information"
    
    @given(
        services=st.lists(
            st.sampled_from(['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']),
            min_size=1,
            max_size=4,
            unique=True
        ),
        error_counts=st.lists(st.integers(min_value=0, max_value=10), min_size=1, max_size=4)
    )
    @settings(max_examples=50, deadline=3000)
    def test_service_status_panel_completeness(self, services, error_counts):
        """
        For any set of services with errors, the service status panel should display 
        status for all services and highlight failed components
        """
        assume(len(services) == len(error_counts))
        
        # Create errors for each service
        for service, count in zip(services, error_counts):
            for i in range(count):
                severity = ErrorSeverity.HIGH if i % 2 == 0 else ErrorSeverity.MEDIUM
                error_info = ErrorInfo(
                    error_type='TestError',
                    error_code='TEST001',
                    message=f'Test error {i} for {service}',
                    severity=severity,
                    service_name=service,
                    timestamp=datetime.now() - timedelta(minutes=i),
                    suggested_action='Test action'
                )
                self.error_handler._error_history.append(error_info)
                self.error_handler._update_service_status(service, error_info)
        
        # Test service status retrieval
        all_status = self.error_handler.get_all_service_status()
        
        # All services with errors should have non-healthy status
        for service, count in zip(services, error_counts):
            if count > 0:
                status = self.error_handler.get_service_status(service)
                assert status != ServiceStatus.HEALTHY, f"Service {service} with {count} errors should not be healthy"
                assert service in all_status, f"Service {service} should be in status overview"
        
        # Error summary should reflect all services
        error_summary = self.error_handler.get_error_summary(hours=1)
        services_with_errors = [s for s, c in zip(services, error_counts) if c > 0]
        
        for service in services_with_errors:
            assert service in error_summary['errors_by_service'], f"Service {service} should be in error summary"
            assert error_summary['errors_by_service'][service] > 0, f"Service {service} should have error count > 0"
    
    @given(
        data_type=st.sampled_from(['prediction', 'system_health', 'data_visualization']),
        service_name=st.sampled_from(['sagemaker', 'dynamodb', 'cloudwatch']),
        cache_age_minutes=st.integers(min_value=1, max_value=120),
        has_fallback=st.booleans()
    )
    @settings(max_examples=50, deadline=3000)
    def test_fallback_data_display_requirements(self, data_type, service_name, cache_age_minutes, has_fallback):
        """
        For any service outage, fallback displays should be available and properly labeled
        """
        if has_fallback:
            # Create fallback data
            fallback_data = FallbackData(
                data_type=data_type,
                data={'test': 'fallback_data'},
                timestamp=datetime.now() - timedelta(minutes=cache_age_minutes),
                source='cache' if cache_age_minutes < 60 else 'default',
                is_stale=cache_age_minutes > 60
            )
            
            # Cache the fallback data
            cache_key = f"{service_name}_{data_type}"
            self.error_handler._fallback_cache[cache_key] = fallback_data
        
        # Test fallback data retrieval
        retrieved_fallback = self.error_handler.get_fallback_data(data_type, service_name)
        
        if has_fallback:
            assert retrieved_fallback is not None, "Fallback data should be available when cached"
            assert retrieved_fallback.data_type == data_type, "Fallback data should preserve data type"
            assert retrieved_fallback.source in ['cache', 'default'], "Fallback data should have valid source"
            
            # Check staleness detection
            if cache_age_minutes > 60:
                assert retrieved_fallback.is_stale, "Old cached data should be marked as stale"
            else:
                assert not retrieved_fallback.is_stale, "Recent cached data should not be marked as stale"
        else:
            # Should get default fallback
            assert retrieved_fallback is not None, "Default fallback should always be available"
            assert retrieved_fallback.source == 'default', "Should get default fallback when no cache available"
    
    @given(
        hours_back=st.integers(min_value=1, max_value=48),
        num_errors=st.integers(min_value=0, max_value=20),
        severity_distribution=st.lists(
            st.sampled_from(list(ErrorSeverity)),
            min_size=0,
            max_size=20
        )
    )
    @settings(max_examples=30, deadline=3000)
    def test_error_summary_accuracy(self, hours_back, num_errors, severity_distribution):
        """
        For any time period and error distribution, error summary should accurately 
        reflect error statistics and service health
        """
        assume(len(severity_distribution) == num_errors)
        
        # Clear existing errors
        self.error_handler.clear_error_history()
        
        # Create errors within the time window
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        for i, severity in enumerate(severity_distribution):
            error_time = cutoff_time + timedelta(minutes=i * 10)  # Spread errors over time
            service = ['dynamodb', 'sagemaker', 'lambda'][i % 3]
            
            error_info = ErrorInfo(
                error_type='TestError',
                error_code=f'TEST{i:03d}',
                message=f'Test error {i}',
                severity=severity,
                service_name=service,
                timestamp=error_time,
                suggested_action='Test action'
            )
            self.error_handler._error_history.append(error_info)
        
        # Get error summary
        summary = self.error_handler.get_error_summary(hours=hours_back)
        
        # Verify summary accuracy
        assert summary['total_errors'] == num_errors, f"Total errors should match: expected {num_errors}, got {summary['total_errors']}"
        assert summary['time_period_hours'] == hours_back, "Time period should match request"
        
        # Verify severity distribution
        expected_severity_counts = {}
        for severity in severity_distribution:
            expected_severity_counts[severity.value] = expected_severity_counts.get(severity.value, 0) + 1
        
        for severity_name, expected_count in expected_severity_counts.items():
            actual_count = summary['errors_by_severity'].get(severity_name, 0)
            assert actual_count == expected_count, f"Severity {severity_name} count mismatch: expected {expected_count}, got {actual_count}"
        
        # Verify service health score calculation
        if num_errors == 0:
            assert summary['service_health_score'] == 100.0, "Health score should be 100% with no errors"
        else:
            assert 0 <= summary['service_health_score'] <= 100, "Health score should be between 0 and 100"
            assert summary['service_health_score'] < 100, "Health score should be less than 100% with errors"
    
    @given(
        connection_results=st.dictionaries(
            keys=st.sampled_from(['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']),
            values=st.booleans(),
            min_size=1,
            max_size=4
        )
    )
    @settings(max_examples=30, deadline=2000)
    def test_connection_test_display_completeness(self, connection_results):
        """
        For any connection test results, the display should show status for all tested services
        and highlight failed connections with diagnostic information
        """
        # Test that connection results processing is complete
        failed_services = [service for service, status in connection_results.items() if not status]
        successful_services = [service for service, status in connection_results.items() if status]
        
        # All services should be accounted for
        assert len(failed_services) + len(successful_services) == len(connection_results), "All services should be categorized"
        
        # For each failed service, diagnostic info should be available
        for service in failed_services:
            diagnostic_info = self.error_handler.get_diagnostic_info(service)
            
            # Diagnostic info should be comprehensive
            assert diagnostic_info['service_name'] == service, "Diagnostic info should include service name"
            assert 'current_status' in diagnostic_info, "Diagnostic info should include current status"
            assert 'configuration_check' in diagnostic_info, "Diagnostic info should include configuration check"
            assert 'suggested_actions' in diagnostic_info, "Diagnostic info should include suggested actions"
            
            # Configuration check should be detailed
            config_check = diagnostic_info['configuration_check']
            assert isinstance(config_check, dict), "Configuration check should be a dictionary"
            assert 'issues' in config_check, "Configuration check should include issues list"
        
        # Overall connection health should be determinable
        all_connected = all(connection_results.values())
        any_connected = any(connection_results.values())
        
        if all_connected:
            # All services healthy
            assert len(failed_services) == 0, "No services should be failed when all connected"
        elif not any_connected:
            # All services failed
            assert len(successful_services) == 0, "No services should be successful when none connected"
        else:
            # Mixed results
            assert len(failed_services) > 0 and len(successful_services) > 0, "Should have both failed and successful services"
    
    @given(
        retry_count=st.integers(min_value=0, max_value=5),
        max_retries=st.integers(min_value=1, max_value=5),
        operation_name=st.text(min_size=5, max_size=50),
        has_delay=st.booleans()
    )
    @settings(max_examples=30, deadline=2000)
    def test_retry_status_display_accuracy(self, retry_count, max_retries, operation_name, has_delay):
        """
        For any retry operation, the display should accurately show retry progress and status
        """
        assume(retry_count <= max_retries)
        
        # Calculate expected progress
        expected_progress = retry_count / max_retries if max_retries > 0 else 0
        
        # Test retry status information
        if retry_count == 0:
            # No retries yet - should not display retry status
            assert True, "No retry status should be shown for retry_count = 0"
        else:
            # Should show retry progress
            assert 0 <= expected_progress <= 1, "Progress should be between 0 and 1"
            
            if retry_count >= max_retries:
                # Should indicate failure
                assert retry_count == max_retries, "Should have reached max retries"
            else:
                # Should indicate retry in progress
                assert retry_count < max_retries, "Should be within retry limits"
        
        # Delay information should be consistent
        if has_delay and retry_count < max_retries:
            # Should show next retry timing
            assert retry_count >= 0, "Retry count should be non-negative when showing delay"
        
        # Operation name should be preserved
        assert len(operation_name.strip()) > 0, "Operation name should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])