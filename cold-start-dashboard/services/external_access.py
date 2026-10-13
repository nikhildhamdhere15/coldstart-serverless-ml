"""
External Access Service for Cold Start Dashboard
Manages external access, public URLs, and user instructions
"""

import streamlit as st
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from services.ngrok_service import get_ngrok_manager
from config import config_manager

@dataclass
class AccessInfo:
    """Information about dashboard access"""
    local_url: str
    public_url: Optional[str]
    is_public_available: bool
    ngrok_status: str
    session_count: int
    uptime: timedelta
    last_updated: datetime

class ExternalAccessService:
    """Service for managing external access to the dashboard"""
    
    def __init__(self):
        self.config = config_manager.dashboard_config
        self.ngrok_manager = None
        self.start_time = datetime.now()
        self.session_counter = 0
        
        # Initialize ngrok if auth token is available
        if self.config.ngrok_auth_token:
            self.ngrok_manager = get_ngrok_manager(self.config.ngrok_auth_token)
    
    def initialize_public_access(self) -> Dict[str, Any]:
        """Initialize public access via ngrok"""
        if not self.config.ngrok_auth_token:
            return {
                "success": False,
                "error": "No ngrok auth token configured",
                "public_url": None
            }
        
        if not self.ngrok_manager:
            self.ngrok_manager = get_ngrok_manager(self.config.ngrok_auth_token)
        
        # Set up public access
        result = self.ngrok_manager.setup_public_access(self.config.public_port)
        
        if result["success"]:
            # Store public URL in session state
            st.session_state.public_url = result["public_url"]
            st.session_state.public_access_enabled = True
        
        return result
    
    def get_access_info(self) -> AccessInfo:
        """Get current access information"""
        local_url = f"http://localhost:{self.config.public_port}"
        public_url = None
        is_public_available = False
        ngrok_status = "Not configured"
        
        if self.ngrok_manager:
            access_info = self.ngrok_manager.get_access_info()
            public_url = access_info.get("public_url")
            is_public_available = bool(public_url)
            
            ngrok_status_obj = access_info.get("ngrok_status", {})
            if ngrok_status_obj.get("is_running"):
                ngrok_status = "Running"
            elif ngrok_status_obj.get("is_installed"):
                ngrok_status = "Installed but not running"
            else:
                ngrok_status = "Not installed"
        
        # Get session count from Streamlit session state
        session_count = getattr(st.session_state, 'session_count', 0)
        
        return AccessInfo(
            local_url=local_url,
            public_url=public_url,
            is_public_available=is_public_available,
            ngrok_status=ngrok_status,
            session_count=session_count,
            uptime=datetime.now() - self.start_time,
            last_updated=datetime.now()
        )
    
    def create_access_panel(self):
        """Create Streamlit panel showing access information"""
        st.subheader("🌐 Dashboard Access Information")
        
        access_info = self.get_access_info()
        
        # Local access information
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏠 Local Access**")
            st.code(access_info.local_url)
            st.caption("Access from this machine")
        
        with col2:
            st.markdown("**🌍 Public Access**")
            if access_info.is_public_available:
                st.code(access_info.public_url)
                st.caption("Share with external examiners")
                
                # Copy button (simulated)
                if st.button("📋 Copy Public URL", key="copy_public_url"):
                    st.success("URL copied to clipboard! (Share this with examiners)")
            else:
                st.info("Not configured")
                st.caption(f"Status: {access_info.ngrok_status}")
        
        # Status information
        st.markdown("---")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Active Sessions",
                access_info.session_count,
                help="Number of active user sessions"
            )
        
        with col2:
            uptime_str = str(access_info.uptime).split('.')[0]  # Remove microseconds
            st.metric(
                "Uptime",
                uptime_str,
                help="Time since dashboard started"
            )
        
        with col3:
            status_color = "🟢" if access_info.is_public_available else "🟡"
            st.metric(
                "Public Status",
                f"{status_color} {'Available' if access_info.is_public_available else 'Local Only'}",
                help="Public access availability"
            )
        
        with col4:
            st.metric(
                "Last Updated",
                access_info.last_updated.strftime("%H:%M:%S"),
                help="Last status check time"
            )
        
        # Public access setup
        if not access_info.is_public_available and self.config.ngrok_auth_token:
            st.markdown("---")
            st.markdown("**🚀 Enable Public Access**")
            
            if st.button("🌐 Start Public Access", type="primary"):
                with st.spinner("Setting up public access..."):
                    result = self.initialize_public_access()
                
                if result["success"]:
                    st.success(f"✅ Public access enabled!")
                    st.info(f"🌍 Public URL: {result['public_url']}")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to enable public access: {result.get('error', 'Unknown error')}")
        
        elif not self.config.ngrok_auth_token:
            st.markdown("---")
            st.info("💡 To enable public access, set the NGROK_AUTH_TOKEN environment variable")
    
    def create_user_instructions(self):
        """Create user instructions panel for external examiners"""
        st.subheader("📋 Instructions for External Examiners")
        
        access_info = self.get_access_info()
        
        if access_info.is_public_available:
            st.success("🌍 **Public Access is Available**")
            
            # Instructions for external users
            st.markdown("""
            **How to Access the Dashboard:**
            
            1. **Open your web browser** (Chrome, Firefox, Safari, or Edge)
            2. **Navigate to the public URL** shown above
            3. **Wait for the dashboard to load** (may take 10-15 seconds on first visit)
            4. **Use the sidebar** to navigate between different sections
            
            **Dashboard Sections:**
            - 🏠 **Overview**: System summary and recent activity
            - 🤖 **Live Predictions**: Interactive ML model predictions
            - 📊 **System Monitoring**: Real-time AWS service health
            - 📈 **Data Visualization**: Live data charts and analytics
            - 🚦 **Traffic Generation**: Generate test traffic for demonstration
            - 🔥 **Warming System**: Lambda warming controls and metrics
            - 💰 **Cost Analytics**: Cost optimization and ROI analysis
            """)
            
            # Technical information
            with st.expander("🔧 Technical Information"):
                st.markdown(f"""
                **Dashboard Configuration:**
                - **Session Timeout**: {self.config.session_timeout // 60} minutes
                - **Auto Refresh**: {self.config.auto_refresh_interval} seconds
                - **Max Concurrent Users**: {self.config.max_concurrent_users}
                - **Public Port**: {self.config.public_port}
                
                **System Requirements:**
                - Modern web browser with JavaScript enabled
                - Stable internet connection
                - No special software installation required
                
                **Troubleshooting:**
                - If the page doesn't load, wait 30 seconds and refresh
                - If you see connection errors, the dashboard may be restarting
                - For best experience, use Chrome or Firefox browsers
                """)
        
        else:
            st.warning("🔒 **Public Access Not Available**")
            st.markdown("""
            Public access is currently not configured. The dashboard is only accessible locally.
            
            **For Local Access:**
            - Use the local URL shown above
            - Access is limited to this machine only
            - External examiners cannot access the dashboard remotely
            """)
    
    def create_session_management_panel(self):
        """Create session management panel for monitoring concurrent users"""
        st.subheader("👥 Session Management")
        
        # Initialize session tracking if not exists
        if 'session_tracking' not in st.session_state:
            st.session_state.session_tracking = {
                'sessions': {},
                'total_sessions': 0,
                'peak_concurrent': 0
            }
        
        # Update current session
        session_id = st.session_state.get('session_id', 'unknown')
        current_time = datetime.now()
        
        st.session_state.session_tracking['sessions'][session_id] = {
            'last_seen': current_time,
            'user_agent': 'Unknown',  # Would need additional setup to get real user agent
            'start_time': st.session_state.session_tracking['sessions'].get(session_id, {}).get('start_time', current_time)
        }
        
        # Clean up old sessions (older than session timeout)
        timeout_threshold = current_time - timedelta(seconds=self.config.session_timeout)
        active_sessions = {}
        
        for sid, session_data in st.session_state.session_tracking['sessions'].items():
            if session_data['last_seen'] > timeout_threshold:
                active_sessions[sid] = session_data
        
        st.session_state.session_tracking['sessions'] = active_sessions
        
        # Update metrics
        current_count = len(active_sessions)
        st.session_state.session_count = current_count
        
        if current_count > st.session_state.session_tracking['peak_concurrent']:
            st.session_state.session_tracking['peak_concurrent'] = current_count
        
        # Display session information
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Active Sessions",
                current_count,
                help="Currently active user sessions"
            )
        
        with col2:
            st.metric(
                "Peak Concurrent",
                st.session_state.session_tracking['peak_concurrent'],
                help="Maximum concurrent sessions since startup"
            )
        
        with col3:
            capacity_usage = (current_count / self.config.max_concurrent_users) * 100
            st.metric(
                "Capacity Usage",
                f"{capacity_usage:.1f}%",
                help=f"Usage of max capacity ({self.config.max_concurrent_users} users)"
            )
        
        # Session details
        if st.checkbox("Show Session Details"):
            if active_sessions:
                session_data = []
                for sid, data in active_sessions.items():
                    duration = current_time - data['start_time']
                    session_data.append({
                        'Session ID': sid[:8] + '...',  # Truncate for privacy
                        'Duration': str(duration).split('.')[0],  # Remove microseconds
                        'Last Seen': data['last_seen'].strftime('%H:%M:%S')
                    })
                
                st.dataframe(session_data, use_container_width=True)
            else:
                st.info("No active sessions")
        
        # Capacity warning
        if capacity_usage > 80:
            st.warning(f"⚠️ High capacity usage ({capacity_usage:.1f}%). Performance may be affected.")
        elif capacity_usage > 100:
            st.error("🚨 Capacity exceeded! New users may experience issues.")
    
    def cleanup(self):
        """Clean up external access resources"""
        if self.ngrok_manager:
            self.ngrok_manager.cleanup()

# Global external access service instance
external_access_service = ExternalAccessService()