"""
Session Management Service for Cold Start Dashboard
Handles concurrent user sessions, performance optimization, and user instructions
"""

import streamlit as st
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
import hashlib
import json

@dataclass
class UserSession:
    """Represents a user session"""
    session_id: str
    start_time: datetime
    last_activity: datetime
    user_agent: str = "Unknown"
    ip_address: str = "Unknown"
    page_views: int = 0
    current_page: str = "Overview"
    is_active: bool = True
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SessionMetrics:
    """Session performance and usage metrics"""
    total_sessions: int
    active_sessions: int
    peak_concurrent: int
    average_session_duration: float
    total_page_views: int
    performance_score: float
    memory_usage_mb: float
    cpu_usage_percent: float

class SessionManager:
    """Manages user sessions and concurrent access"""
    
    def __init__(self, max_concurrent_users: int = 10, session_timeout: int = 3600):
        self.max_concurrent_users = max_concurrent_users
        self.session_timeout = session_timeout
        self.sessions: Dict[str, UserSession] = {}
        self.session_lock = threading.Lock()
        self.metrics_history: List[SessionMetrics] = []
        self.start_time = datetime.now()
        
        # Performance optimization settings
        self.cache_ttl = 300  # 5 minutes
        self.cleanup_interval = 60  # 1 minute
        self.last_cleanup = datetime.now()
        
    def get_or_create_session(self) -> UserSession:
        """Get existing session or create new one"""
        # Get session ID from Streamlit session state
        if 'session_id' not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
        
        session_id = st.session_state.session_id
        
        with self.session_lock:
            # Check if session exists and is valid
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_activity = datetime.now()
                session.page_views += 1
                return session
            
            # Create new session
            if len(self.get_active_sessions()) >= self.max_concurrent_users:
                # Clean up expired sessions first
                self.cleanup_expired_sessions()
                
                # Check again after cleanup
                if len(self.get_active_sessions()) >= self.max_concurrent_users:
                    raise Exception(f"Maximum concurrent users ({self.max_concurrent_users}) exceeded")
            
            # Create new session
            session = UserSession(
                session_id=session_id,
                start_time=datetime.now(),
                last_activity=datetime.now(),
                user_agent=self._get_user_agent(),
                ip_address=self._get_client_ip(),
                page_views=1,
                current_page="Overview"
            )
            
            self.sessions[session_id] = session
            return session
    
    def update_session_activity(self, page_name: str = None):
        """Update session activity and current page"""
        if 'session_id' not in st.session_state:
            return
        
        session_id = st.session_state.session_id
        
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_activity = datetime.now()
                if page_name:
                    session.current_page = page_name
    
    def get_active_sessions(self) -> List[UserSession]:
        """Get list of currently active sessions"""
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=self.session_timeout)
        
        active_sessions = []
        for session in self.sessions.values():
            if session.last_activity > timeout_threshold and session.is_active:
                active_sessions.append(session)
        
        return active_sessions
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=self.session_timeout)
        
        with self.session_lock:
            expired_sessions = []
            for session_id, session in self.sessions.items():
                if session.last_activity <= timeout_threshold:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
        
        self.last_cleanup = current_time
    
    def get_session_metrics(self) -> SessionMetrics:
        """Get current session metrics"""
        active_sessions = self.get_active_sessions()
        
        # Calculate metrics
        total_sessions = len(self.sessions)
        active_count = len(active_sessions)
        
        # Peak concurrent (from history or current)
        peak_concurrent = active_count
        if self.metrics_history:
            peak_concurrent = max(peak_concurrent, max(m.active_sessions for m in self.metrics_history))
        
        # Average session duration
        if active_sessions:
            durations = [(datetime.now() - s.start_time).total_seconds() for s in active_sessions]
            avg_duration = sum(durations) / len(durations)
        else:
            avg_duration = 0.0
        
        # Total page views
        total_page_views = sum(s.page_views for s in self.sessions.values())
        
        # Performance score (simplified)
        capacity_usage = active_count / self.max_concurrent_users
        performance_score = max(0, 100 - (capacity_usage * 50))  # Decreases as capacity fills
        
        # Mock system metrics (would need actual system monitoring)
        memory_usage_mb = 150 + (active_count * 25)  # Estimated memory usage
        cpu_usage_percent = min(100, 10 + (active_count * 5))  # Estimated CPU usage
        
        return SessionMetrics(
            total_sessions=total_sessions,
            active_sessions=active_count,
            peak_concurrent=peak_concurrent,
            average_session_duration=avg_duration,
            total_page_views=total_page_views,
            performance_score=performance_score,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent
        )
    
    def optimize_performance(self) -> Dict[str, Any]:
        """Apply performance optimizations based on current load"""
        active_sessions = self.get_active_sessions()
        session_count = len(active_sessions)
        
        optimizations = {
            "cache_enabled": True,
            "auto_refresh_interval": 30,
            "max_records_display": 50,
            "chart_complexity": "full",
            "real_time_updates": True
        }
        
        # Adjust settings based on load
        if session_count > self.max_concurrent_users * 0.7:  # High load
            optimizations.update({
                "auto_refresh_interval": 60,  # Slower refresh
                "max_records_display": 25,    # Fewer records
                "chart_complexity": "simple", # Simpler charts
                "real_time_updates": False    # Disable real-time updates
            })
        elif session_count > self.max_concurrent_users * 0.5:  # Medium load
            optimizations.update({
                "auto_refresh_interval": 45,
                "max_records_display": 35,
                "chart_complexity": "medium"
            })
        
        return optimizations
    
    def _get_user_agent(self) -> str:
        """Get user agent from request headers (simplified)"""
        # In a real implementation, this would extract from HTTP headers
        return "Unknown Browser"
    
    def _get_client_ip(self) -> str:
        """Get client IP address (simplified)"""
        # In a real implementation, this would extract from request headers
        return "Unknown IP"
    
    def create_session_status_display(self):
        """Create Streamlit display for session status"""
        # Ensure session exists
        try:
            session = self.get_or_create_session()
        except Exception as e:
            st.error(f"❌ Session limit exceeded: {str(e)}")
            st.info("Please try again later when capacity is available.")
            return
        
        # Update activity
        self.update_session_activity()
        
        # Periodic cleanup
        if (datetime.now() - self.last_cleanup).total_seconds() > self.cleanup_interval:
            self.cleanup_expired_sessions()
        
        # Get metrics
        metrics = self.get_session_metrics()
        
        # Store metrics in session state for other components
        st.session_state.session_metrics = metrics
        
        # Display session info in sidebar
        with st.sidebar:
            st.markdown("---")
            st.markdown("**👥 Session Info**")
            
            # Session status
            capacity_usage = (metrics.active_sessions / self.max_concurrent_users) * 100
            
            if capacity_usage < 50:
                status_color = "🟢"
                status_text = "Low Load"
            elif capacity_usage < 80:
                status_color = "🟡"
                status_text = "Medium Load"
            else:
                status_color = "🔴"
                status_text = "High Load"
            
            st.caption(f"{status_color} {status_text} ({metrics.active_sessions}/{self.max_concurrent_users} users)")
            
            # Session duration
            session_duration = datetime.now() - session.start_time
            duration_str = str(session_duration).split('.')[0]  # Remove microseconds
            st.caption(f"⏱️ Session: {duration_str}")
            
            # Performance optimization notice
            if capacity_usage > 70:
                st.warning("⚠️ High load detected. Some features may be optimized for performance.")
    
    def create_admin_panel(self):
        """Create admin panel for session management"""
        st.subheader("👥 Session Management")
        
        metrics = self.get_session_metrics()
        active_sessions = self.get_active_sessions()
        
        # Metrics overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Active Sessions",
                metrics.active_sessions,
                delta=f"Peak: {metrics.peak_concurrent}"
            )
        
        with col2:
            capacity_usage = (metrics.active_sessions / self.max_concurrent_users) * 100
            st.metric(
                "Capacity Usage",
                f"{capacity_usage:.1f}%",
                delta=f"Max: {self.max_concurrent_users}"
            )
        
        with col3:
            avg_duration_min = metrics.average_session_duration / 60
            st.metric(
                "Avg Session Duration",
                f"{avg_duration_min:.1f} min",
                delta=f"Total views: {metrics.total_page_views}"
            )
        
        with col4:
            st.metric(
                "Performance Score",
                f"{metrics.performance_score:.1f}",
                delta=f"Memory: {metrics.memory_usage_mb:.0f}MB"
            )
        
        # Performance optimizations
        st.markdown("---")
        st.subheader("⚡ Performance Optimizations")
        
        optimizations = self.optimize_performance()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Current Optimizations:**")
            for key, value in optimizations.items():
                icon = "✅" if value else "❌"
                if isinstance(value, bool):
                    st.write(f"{icon} {key.replace('_', ' ').title()}: {'Enabled' if value else 'Disabled'}")
                else:
                    st.write(f"⚙️ {key.replace('_', ' ').title()}: {value}")
        
        with col2:
            st.markdown("**System Resources:**")
            st.write(f"💾 Memory Usage: {metrics.memory_usage_mb:.0f} MB")
            st.write(f"🖥️ CPU Usage: {metrics.cpu_usage_percent:.1f}%")
            st.write(f"⏱️ Uptime: {str(datetime.now() - self.start_time).split('.')[0]}")
        
        # Active sessions table
        if st.checkbox("Show Active Sessions"):
            if active_sessions:
                session_data = []
                for session in active_sessions:
                    duration = datetime.now() - session.start_time
                    session_data.append({
                        'Session ID': session.session_id[:8] + '...',
                        'Start Time': session.start_time.strftime('%H:%M:%S'),
                        'Duration': str(duration).split('.')[0],
                        'Current Page': session.current_page,
                        'Page Views': session.page_views,
                        'Last Activity': session.last_activity.strftime('%H:%M:%S')
                    })
                
                st.dataframe(session_data, use_container_width=True)
            else:
                st.info("No active sessions")
        
        # Capacity warnings
        if capacity_usage > 90:
            st.error("🚨 **Critical**: Capacity nearly exceeded! Performance may be severely impacted.")
        elif capacity_usage > 75:
            st.warning("⚠️ **Warning**: High capacity usage. Consider optimizing or limiting new sessions.")
        elif capacity_usage > 50:
            st.info("ℹ️ **Info**: Moderate load detected. Monitoring performance optimizations.")

class ConcurrentUserHandler:
    """High-level handler for concurrent user management"""
    
    def __init__(self, config):
        self.session_manager = SessionManager(
            max_concurrent_users=config.max_concurrent_users,
            session_timeout=config.session_timeout
        )
        self.config = config
    
    def initialize_session(self) -> bool:
        """Initialize user session and return success status"""
        try:
            session = self.session_manager.get_or_create_session()
            
            # Store session info in Streamlit session state
            st.session_state.user_session = session
            st.session_state.session_initialized = True
            
            return True
            
        except Exception as e:
            st.session_state.session_error = str(e)
            st.session_state.session_initialized = False
            return False
    
    def update_page_activity(self, page_name: str):
        """Update current page activity"""
        self.session_manager.update_session_activity(page_name)
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """Get current performance optimization settings"""
        return self.session_manager.optimize_performance()
    
    def create_user_instructions(self):
        """Create user instructions for external examiners"""
        st.markdown("### 📋 Welcome to the Cold Start Dashboard")
        
        # Check session status
        if not st.session_state.get('session_initialized', False):
            if 'session_error' in st.session_state:
                st.error(f"❌ {st.session_state.session_error}")
                st.info("The dashboard has reached its maximum capacity. Please try again later.")
                return
        
        # Welcome message
        st.success("✅ **Session Active** - Welcome to the Cold Start Prevention Dashboard!")
        
        # Navigation instructions
        st.markdown("""
        **🧭 How to Navigate:**
        
        Use the **sidebar on the left** to explore different sections:
        
        - **🏠 Overview**: System summary and architecture
        - **🤖 Live Predictions**: Interactive ML model demonstrations  
        - **📊 System Monitoring**: Real-time AWS service health
        - **📈 Data Visualization**: Live data charts and analytics
        - **🚦 Traffic Generation**: Generate test traffic
        - **🔥 Warming System**: Lambda warming controls
        - **💰 Cost Analytics**: Cost optimization metrics
        
        **⚡ Performance Tips:**
        - The dashboard auto-refreshes every 30 seconds
        - Some features may be optimized during high load
        - Use the refresh button to manually update data
        - Charts and visualizations are interactive - click and explore!
        """)
        
        # Current session info
        metrics = self.session_manager.get_session_metrics()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"👥 **Active Users**: {metrics.active_sessions}")
        
        with col2:
            capacity = (metrics.active_sessions / self.config.max_concurrent_users) * 100
            st.info(f"📊 **System Load**: {capacity:.0f}%")
        
        with col3:
            st.info(f"⏱️ **Session Timeout**: {self.config.session_timeout // 60} min")
        
        # Performance notice
        performance_settings = self.get_performance_settings()
        if not performance_settings.get("real_time_updates", True):
            st.warning("⚠️ **Performance Mode**: Some real-time features are optimized due to high load.")
    
    def cleanup(self):
        """Clean up session resources"""
        self.session_manager.cleanup_expired_sessions()

# Global concurrent user handler
concurrent_user_handler = None

def get_concurrent_user_handler(config) -> ConcurrentUserHandler:
    """Get or create global concurrent user handler"""
    global concurrent_user_handler
    if concurrent_user_handler is None:
        concurrent_user_handler = ConcurrentUserHandler(config)
    return concurrent_user_handler