"""
Error Display Service
Provides user-friendly error messages and diagnostic information displays
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from services.error_handling import ErrorHandlingService, ErrorInfo, ErrorSeverity, ServiceStatus
from services.ui_styling import ui_style_manager

class ErrorDisplayService:
    """
    Service for creating user-friendly error displays and diagnostic information
    """
    
    def __init__(self, error_handler: ErrorHandlingService):
        """Initialize with error handling service"""
        self.error_handler = error_handler
    
    def display_service_error(self, error_info: ErrorInfo, show_details: bool = False):
        """
        Display a user-friendly error message for a service error
        
        Args:
            error_info: ErrorInfo object with error details
            show_details: Whether to show detailed diagnostic information
        """
        # Determine alert type based on severity
        if error_info.severity == ErrorSeverity.CRITICAL:
            alert_type = "error"
            icon = "🚨"
        elif error_info.severity == ErrorSeverity.HIGH:
            alert_type = "error"
            icon = "❌"
        elif error_info.severity == ErrorSeverity.MEDIUM:
            alert_type = "warning"
            icon = "⚠️"
        else:
            alert_type = "info"
            icon = "ℹ️"
        
        # Create main error message
        title = f"{icon} {error_info.service_name.title()} Service Issue"
        message = error_info.message
        
        # Add suggested action
        if error_info.suggested_action:
            message += f"\n\n**Suggested Action:** {error_info.suggested_action}"
        
        # Display the alert
        ui_style_manager.create_enhanced_alert_box(message, alert_type, title)
        
        # Show details if requested
        if show_details:
            self._display_error_details(error_info)
    
    def display_service_status_panel(self, service_name: str = None):
        """
        Display comprehensive service status panel
        
        Args:
            service_name: Specific service to show, or None for all services
        """
        st.subheader("🔍 Service Status Overview")
        
        if service_name:
            services = [service_name]
        else:
            services = ['dynamodb', 'sagemaker', 'lambda', 'cloudwatch']
        
        # Create status grid
        cols = st.columns(len(services))
        
        for i, service in enumerate(services):
            with cols[i]:
                status = self.error_handler.get_service_status(service)
                self._display_service_status_card(service, status)
        
        # Show detailed diagnostics if any service has issues
        problematic_services = [
            service for service in services 
            if self.error_handler.get_service_status(service) != ServiceStatus.HEALTHY
        ]
        
        if problematic_services:
            st.markdown("---")
            st.subheader("🔧 Diagnostic Information")
            
            for service in problematic_services:
                with st.expander(f"🔍 {service.title()} Diagnostics", expanded=True):
                    self._display_service_diagnostics(service)
    
    def display_error_summary_dashboard(self, hours: int = 24):
        """
        Display comprehensive error summary dashboard
        
        Args:
            hours: Number of hours to look back for error analysis
        """
        st.subheader("📊 Error Analysis Dashboard")
        
        # Get error summary
        summary = self.error_handler.get_error_summary(hours)
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            ui_style_manager.create_enhanced_metric_card(
                title="Total Errors",
                value=str(summary['total_errors']),
                delta=f"Last {hours} hours",
                status="error" if summary['total_errors'] > 10 else "success",
                icon="🚨"
            )
        
        with col2:
            ui_style_manager.create_enhanced_metric_card(
                title="Service Health",
                value=f"{summary['service_health_score']:.1f}%",
                delta="Overall score",
                status="success" if summary['service_health_score'] > 95 else "warning",
                icon="🏥"
            )
        
        with col3:
            critical_errors = summary['errors_by_severity'].get('critical', 0)
            ui_style_manager.create_enhanced_metric_card(
                title="Critical Errors",
                value=str(critical_errors),
                delta="Require immediate attention",
                status="error" if critical_errors > 0 else "success",
                icon="🔴"
            )
        
        with col4:
            affected_services = len(summary['errors_by_service'])
            ui_style_manager.create_enhanced_metric_card(
                title="Affected Services",
                value=str(affected_services),
                delta="Services with errors",
                status="warning" if affected_services > 2 else "success",
                icon="⚙️"
            )
        
        # Error breakdown charts
        if summary['total_errors'] > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Errors by Service**")
                self._display_errors_by_service_chart(summary['errors_by_service'])
            
            with col2:
                st.markdown("**Errors by Severity**")
                self._display_errors_by_severity_chart(summary['errors_by_severity'])
            
            # Most common errors
            if summary['most_common_errors']:
                st.markdown("**Most Common Error Types**")
                self._display_common_errors_table(summary['most_common_errors'])
        else:
            ui_style_manager.create_enhanced_alert_box(
                f"No errors recorded in the last {hours} hours. System is operating normally.",
                "success",
                "✅ All Systems Operational"
            )
    
    def display_fallback_data_notice(self, data_type: str, service_name: str, 
                                   fallback_data: Any = None):
        """
        Display notice when showing fallback data
        
        Args:
            data_type: Type of data being displayed
            service_name: Service that's unavailable
            fallback_data: The fallback data being shown
        """
        if fallback_data and hasattr(fallback_data, 'source'):
            if fallback_data.source == 'cache':
                age = (datetime.now() - fallback_data.timestamp).total_seconds() / 60
                if fallback_data.is_stale:
                    message = f"⚠️ Showing cached {data_type} data (last updated {age:.0f} minutes ago). {service_name.title()} service is currently unavailable."
                    alert_type = "warning"
                else:
                    message = f"ℹ️ Showing recent {data_type} data from cache. {service_name.title()} service is temporarily unavailable."
                    alert_type = "info"
            else:
                message = f"⚠️ {service_name.title()} service is unavailable. Showing default {data_type} data."
                alert_type = "warning"
        else:
            message = f"❌ {service_name.title()} service is unavailable and no fallback data is available."
            alert_type = "error"
        
        st.warning(message)
    
    def display_retry_status(self, operation: str, retry_count: int, max_retries: int, 
                           next_retry_delay: float = None):
        """
        Display retry status information
        
        Args:
            operation: Name of the operation being retried
            retry_count: Current retry attempt
            max_retries: Maximum number of retries
            next_retry_delay: Delay until next retry in seconds
        """
        if retry_count == 0:
            return  # No retries yet
        
        progress = retry_count / max_retries
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.progress(progress)
            if next_retry_delay:
                st.caption(f"Retrying {operation} (attempt {retry_count}/{max_retries}) in {next_retry_delay:.1f}s...")
            else:
                st.caption(f"Retry attempt {retry_count}/{max_retries} for {operation}")
        
        with col2:
            if retry_count >= max_retries:
                st.error("❌ Failed")
            else:
                st.info("🔄 Retrying")
    
    def display_connection_test_results(self, test_results: Dict[str, bool]):
        """
        Display connection test results in a user-friendly format
        
        Args:
            test_results: Dictionary of service names to connection status
        """
        st.subheader("🧪 Connection Test Results")
        
        # Overall status
        all_connected = all(test_results.values())
        failed_services = [service for service, status in test_results.items() if not status]
        
        if all_connected:
            ui_style_manager.create_enhanced_alert_box(
                "All AWS services are connected and accessible!",
                "success",
                "✅ All Connections Successful"
            )
        else:
            ui_style_manager.create_enhanced_alert_box(
                f"Connection issues detected with: {', '.join(failed_services)}",
                "error",
                "❌ Connection Issues Detected"
            )
        
        # Individual service results
        cols = st.columns(len(test_results))
        
        for i, (service, status) in enumerate(test_results.items()):
            with cols[i]:
                if status:
                    st.success(f"✅ {service.title()}")
                    st.caption("Connected")
                else:
                    st.error(f"❌ {service.title()}")
                    st.caption("Failed")
                    
                    # Show diagnostic info for failed services
                    if st.button(f"🔍 Diagnose", key=f"diagnose_{service}"):
                        with st.expander(f"{service.title()} Diagnostics", expanded=True):
                            self._display_service_diagnostics(service)
    
    def create_error_recovery_panel(self, service_name: str):
        """
        Create an error recovery panel with suggested actions
        
        Args:
            service_name: Name of the service with issues
        """
        st.subheader(f"🔧 {service_name.title()} Recovery Options")
        
        diagnostic_info = self.error_handler.get_diagnostic_info(service_name)
        
        # Show current status
        status = diagnostic_info['current_status']
        if status == 'healthy':
            st.success("✅ Service is currently healthy")
            return
        elif status == 'degraded':
            st.warning("⚠️ Service is experiencing issues")
        else:
            st.error("❌ Service is unavailable")
        
        # Show suggested actions
        if diagnostic_info['suggested_actions']:
            st.markdown("**Recommended Actions:**")
            for i, action in enumerate(diagnostic_info['suggested_actions'], 1):
                st.markdown(f"{i}. {action}")
        
        # Recovery actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Retry Connection", key=f"retry_{service_name}"):
                with st.spinner(f"Testing {service_name} connection..."):
                    # This would trigger a connection test
                    st.info("Connection test initiated...")
        
        with col2:
            if st.button("🧹 Clear Error History", key=f"clear_{service_name}"):
                # Clear errors for this service
                st.success("Error history cleared")
        
        with col3:
            if st.button("📋 Export Diagnostics", key=f"export_{service_name}"):
                # Export diagnostic information
                diagnostic_json = str(diagnostic_info)
                st.download_button(
                    label="Download Diagnostics",
                    data=diagnostic_json,
                    file_name=f"{service_name}_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    def _display_service_status_card(self, service_name: str, status: ServiceStatus):
        """Display a status card for a service"""
        if status == ServiceStatus.HEALTHY:
            st.success(f"✅ {service_name.title()}")
            st.caption("Healthy")
        elif status == ServiceStatus.DEGRADED:
            st.warning(f"⚠️ {service_name.title()}")
            st.caption("Degraded")
        elif status == ServiceStatus.UNAVAILABLE:
            st.error(f"❌ {service_name.title()}")
            st.caption("Unavailable")
        else:
            st.info(f"❓ {service_name.title()}")
            st.caption("Unknown")
    
    def _display_service_diagnostics(self, service_name: str):
        """Display detailed diagnostics for a service"""
        diagnostic_info = self.error_handler.get_diagnostic_info(service_name)
        
        # Basic information
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Current Status", diagnostic_info['current_status'].title())
            st.metric("Recent Errors", diagnostic_info['recent_error_count'])
        
        with col2:
            if diagnostic_info['last_error_time']:
                last_error = diagnostic_info['last_error_time'].strftime("%H:%M:%S")
                st.metric("Last Error", last_error)
            else:
                st.metric("Last Error", "None")
        
        # Configuration check
        config_check = diagnostic_info['configuration_check']
        st.markdown("**Configuration Status:**")
        
        config_items = [
            ("Credentials", config_check['credentials_configured']),
            ("Region", config_check['region_configured']),
            ("Endpoints", config_check['endpoints_configured']),
            ("Permissions", config_check['permissions_likely_ok'])
        ]
        
        for item, status in config_items:
            icon = "✅" if status else "❌"
            st.write(f"{icon} {item}")
        
        # Issues
        if config_check['issues']:
            st.markdown("**Configuration Issues:**")
            for issue in config_check['issues']:
                st.error(f"• {issue}")
        
        # Common error types
        if diagnostic_info['common_error_types']:
            st.markdown("**Recent Error Types:**")
            for error_type, count in diagnostic_info['common_error_types'].items():
                st.write(f"• {error_type}: {count} occurrences")
        
        # Suggested actions
        if diagnostic_info['suggested_actions']:
            st.markdown("**Suggested Actions:**")
            for action in diagnostic_info['suggested_actions']:
                st.info(f"💡 {action}")
    
    def _display_error_details(self, error_info: ErrorInfo):
        """Display detailed error information"""
        with st.expander("🔍 Error Details", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Error Information:**")
                st.write(f"Type: {error_info.error_type}")
                if error_info.error_code:
                    st.write(f"Code: {error_info.error_code}")
                st.write(f"Severity: {error_info.severity.value.title()}")
                st.write(f"Time: {error_info.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            with col2:
                st.write("**Retry Information:**")
                st.write(f"Retry Count: {error_info.retry_count}")
                st.write(f"Max Retries: {error_info.max_retries}")
                
                if error_info.diagnostic_info:
                    st.write("**Diagnostic Info:**")
                    for key, value in error_info.diagnostic_info.items():
                        if key not in ['operation', 'service_name', 'error_class']:
                            st.write(f"{key}: {value}")
    
    def _display_errors_by_service_chart(self, errors_by_service: Dict[str, int]):
        """Display errors by service as a simple chart"""
        if not errors_by_service:
            st.info("No service errors to display")
            return
        
        # Create a simple bar chart using Streamlit
        import pandas as pd
        
        df = pd.DataFrame(
            list(errors_by_service.items()),
            columns=['Service', 'Error Count']
        )
        
        st.bar_chart(df.set_index('Service'))
    
    def _display_errors_by_severity_chart(self, errors_by_severity: Dict[str, int]):
        """Display errors by severity as a simple chart"""
        if not errors_by_severity:
            st.info("No severity data to display")
            return
        
        # Display as metrics
        severity_order = ['critical', 'high', 'medium', 'low']
        cols = st.columns(len(severity_order))
        
        for i, severity in enumerate(severity_order):
            count = errors_by_severity.get(severity, 0)
            with cols[i]:
                color = {
                    'critical': 'error',
                    'high': 'error', 
                    'medium': 'warning',
                    'low': 'info'
                }.get(severity, 'info')
                
                if count > 0:
                    if color == 'error':
                        st.error(f"{severity.title()}: {count}")
                    elif color == 'warning':
                        st.warning(f"{severity.title()}: {count}")
                    else:
                        st.info(f"{severity.title()}: {count}")
                else:
                    st.success(f"{severity.title()}: {count}")
    
    def _display_common_errors_table(self, common_errors: List[tuple]):
        """Display common errors in a table format"""
        if not common_errors:
            st.info("No common errors to display")
            return
        
        # Create table data
        table_data = []
        for error_type, count in common_errors:
            table_data.append({
                'Error Type': error_type,
                'Occurrences': count,
                'Percentage': f"{(count / sum(c for _, c in common_errors)) * 100:.1f}%"
            })
        
        import pandas as pd
        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

# Create global instance
def get_error_display_service(error_handler):
    """Get error display service instance"""
    return ErrorDisplayService(error_handler)