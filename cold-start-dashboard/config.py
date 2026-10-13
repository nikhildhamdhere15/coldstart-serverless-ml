"""
Configuration management for Cold Start Dashboard
Handles AWS credentials, endpoints, and application settings
"""

import os
from dataclasses import dataclass
from typing import Optional
import boto3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class AWSConfig:
    """AWS service configuration"""
    region: str
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    
    # DynamoDB Configuration
    dynamodb_table_name: str = "ETLFeatureData"
    
    # SageMaker Endpoints
    xgboost_endpoint: str = "cold-start-xgboost-serverless"
    random_forest_endpoint: str = "cold-start-rf-serverless"
    
    # Lambda Functions
    traffic_generator_function: str = "TrafficGenerator"
    data_aggregator_function: str = "DataAggregator"
    intelligent_warmer_function: str = "IntelligentLambdaWarmer"
    
    # API Gateway
    api_gateway_url: Optional[str] = None

@dataclass
class DashboardConfig:
    """Dashboard application configuration"""
    title: str = "Cold Start Prevention Dashboard"
    page_icon: str = "🚀"
    layout: str = "wide"
    auto_refresh_interval: int = 30  # seconds
    max_records_display: int = 50
    prediction_timeout: int = 10  # seconds
    
    # External Access Configuration
    ngrok_auth_token: Optional[str] = None
    public_port: int = 8501
    server_address: str = "0.0.0.0"  # Allow external connections
    enable_cors: bool = False
    enable_xsrf_protection: bool = False
    session_timeout: int = 3600  # 1 hour
    max_concurrent_users: int = 10
    
    # Security settings for external access
    show_error_details: bool = False
    gather_usage_stats: bool = False
    toolbar_mode: str = "minimal"
    
    # Performance Configuration
    cache_ttl: int = 300  # 5 minutes
    health_check_interval: int = 300  # 5 minutes
    max_retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds
    
    # UI Configuration
    theme: str = "light"
    enable_animations: bool = True
    chart_height: int = 400
    table_page_size: int = 20
    
    # Logging Configuration
    log_level: str = "INFO"
    enable_cloudwatch_logging: bool = True
    log_retention_days: int = 7

@dataclass
class FeatureFlags:
    """Feature flags for enabling/disabling dashboard features"""
    enable_live_predictions: bool = True
    enable_system_monitoring: bool = True
    enable_data_visualization: bool = True
    enable_traffic_generation: bool = True
    enable_warming_system: bool = True
    enable_cost_analytics: bool = True
    enable_external_access: bool = True
    enable_performance_tracking: bool = True
    enable_error_recovery: bool = True
    enable_advanced_charts: bool = True

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self):
        self.aws_config = self._load_aws_config()
        self.dashboard_config = self._load_dashboard_config()
        self.feature_flags = self._load_feature_flags()
    
    def _load_aws_config(self) -> AWSConfig:
        """Load AWS configuration from environment variables"""
        return AWSConfig(
            region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            session_token=os.getenv("AWS_SESSION_TOKEN"),
            dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", "ETLFeatureData"),
            xgboost_endpoint=os.getenv("XGBOOST_ENDPOINT", "cold-start-xgboost-serverless"),
            random_forest_endpoint=os.getenv("RF_ENDPOINT", "cold-start-rf-serverless"),
            traffic_generator_function=os.getenv("TRAFFIC_GENERATOR_FUNCTION", "TrafficGenerator"),
            data_aggregator_function=os.getenv("DATA_AGGREGATOR_FUNCTION", "DataAggregator"),
            intelligent_warmer_function=os.getenv("INTELLIGENT_WARMER_FUNCTION", "IntelligentLambdaWarmer"),
            api_gateway_url=os.getenv("API_GATEWAY_URL")
        )
    
    def _load_dashboard_config(self) -> DashboardConfig:
        """Load dashboard configuration from environment variables"""
        return DashboardConfig(
            title=os.getenv("DASHBOARD_TITLE", "Cold Start Prevention Dashboard"),
            auto_refresh_interval=int(os.getenv("AUTO_REFRESH_INTERVAL", "30")),
            max_records_display=int(os.getenv("MAX_RECORDS_DISPLAY", "50")),
            prediction_timeout=int(os.getenv("PREDICTION_TIMEOUT", "10")),
            ngrok_auth_token=os.getenv("NGROK_AUTH_TOKEN"),
            public_port=int(os.getenv("PUBLIC_PORT", "8501")),
            server_address=os.getenv("SERVER_ADDRESS", "0.0.0.0"),
            enable_cors=os.getenv("ENABLE_CORS", "false").lower() == "true",
            enable_xsrf_protection=os.getenv("ENABLE_XSRF_PROTECTION", "false").lower() == "true",
            session_timeout=int(os.getenv("SESSION_TIMEOUT", "3600")),
            max_concurrent_users=int(os.getenv("MAX_CONCURRENT_USERS", "10")),
            show_error_details=os.getenv("SHOW_ERROR_DETAILS", "false").lower() == "true",
            gather_usage_stats=os.getenv("GATHER_USAGE_STATS", "false").lower() == "true",
            toolbar_mode=os.getenv("TOOLBAR_MODE", "minimal"),
            cache_ttl=int(os.getenv("CACHE_TTL", "300")),
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "300")),
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            retry_delay=float(os.getenv("RETRY_DELAY", "1.0")),
            theme=os.getenv("THEME", "light"),
            enable_animations=os.getenv("ENABLE_ANIMATIONS", "true").lower() == "true",
            chart_height=int(os.getenv("CHART_HEIGHT", "400")),
            table_page_size=int(os.getenv("TABLE_PAGE_SIZE", "20")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            enable_cloudwatch_logging=os.getenv("ENABLE_CLOUDWATCH_LOGGING", "true").lower() == "true",
            log_retention_days=int(os.getenv("LOG_RETENTION_DAYS", "7"))
        )
    
    def _load_feature_flags(self) -> FeatureFlags:
        """Load feature flags from environment variables"""
        return FeatureFlags(
            enable_live_predictions=os.getenv("ENABLE_LIVE_PREDICTIONS", "true").lower() == "true",
            enable_system_monitoring=os.getenv("ENABLE_SYSTEM_MONITORING", "true").lower() == "true",
            enable_data_visualization=os.getenv("ENABLE_DATA_VISUALIZATION", "true").lower() == "true",
            enable_traffic_generation=os.getenv("ENABLE_TRAFFIC_GENERATION", "true").lower() == "true",
            enable_warming_system=os.getenv("ENABLE_WARMING_SYSTEM", "true").lower() == "true",
            enable_cost_analytics=os.getenv("ENABLE_COST_ANALYTICS", "true").lower() == "true",
            enable_external_access=os.getenv("ENABLE_EXTERNAL_ACCESS", "true").lower() == "true",
            enable_performance_tracking=os.getenv("ENABLE_PERFORMANCE_TRACKING", "true").lower() == "true",
            enable_error_recovery=os.getenv("ENABLE_ERROR_RECOVERY", "true").lower() == "true",
            enable_advanced_charts=os.getenv("ENABLE_ADVANCED_CHARTS", "true").lower() == "true"
        )
    
    def get_aws_session(self) -> boto3.Session:
        """Create AWS session with configured credentials"""
        session_kwargs = {"region_name": self.aws_config.region}
        
        if self.aws_config.access_key_id:
            session_kwargs.update({
                "aws_access_key_id": self.aws_config.access_key_id,
                "aws_secret_access_key": self.aws_config.secret_access_key
            })
            
        if self.aws_config.session_token:
            session_kwargs["aws_session_token"] = self.aws_config.session_token
            
        return boto3.Session(**session_kwargs)
    
    def validate_configuration(self) -> dict:
        """Validate configuration and return status"""
        status = {
            "aws_region": bool(self.aws_config.region),
            "credentials_configured": bool(
                self.aws_config.access_key_id and self.aws_config.secret_access_key
            ) or self._has_default_credentials(),
            "endpoints_configured": bool(
                self.aws_config.xgboost_endpoint and self.aws_config.random_forest_endpoint
            ),
            "functions_configured": bool(
                self.aws_config.traffic_generator_function and 
                self.aws_config.data_aggregator_function and
                self.aws_config.intelligent_warmer_function
            ),
            "external_access_configured": bool(self.dashboard_config.ngrok_auth_token) if self.feature_flags.enable_external_access else True,
            "logging_configured": bool(self.dashboard_config.enable_cloudwatch_logging),
            "performance_settings_valid": self.dashboard_config.cache_ttl > 0 and self.dashboard_config.health_check_interval > 0
        }
        return status
    
    def _has_default_credentials(self) -> bool:
        """Check if AWS default credentials are available"""
        try:
            session = boto3.Session()
            session.get_credentials()
            return True
        except Exception:
            return False
    
    def get_streamlit_config(self) -> dict:
        """Get Streamlit-specific configuration"""
        return {
            "server.port": self.dashboard_config.public_port,
            "server.address": self.dashboard_config.server_address,
            "server.enableCORS": self.dashboard_config.enable_cors,
            "server.enableXsrfProtection": self.dashboard_config.enable_xsrf_protection,
            "browser.showErrorDetails": self.dashboard_config.show_error_details,
            "browser.gatherUsageStats": self.dashboard_config.gather_usage_stats,
            "ui.hideTopBar": self.dashboard_config.toolbar_mode == "minimal",
            "theme.base": self.dashboard_config.theme,
            "logger.level": self.dashboard_config.log_level
        }
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a specific feature is enabled"""
        return getattr(self.feature_flags, f"enable_{feature_name}", False)
    
    def get_performance_config(self) -> dict:
        """Get performance-related configuration"""
        return {
            "cache_ttl": self.dashboard_config.cache_ttl,
            "health_check_interval": self.dashboard_config.health_check_interval,
            "max_retry_attempts": self.dashboard_config.max_retry_attempts,
            "retry_delay": self.dashboard_config.retry_delay,
            "max_concurrent_users": self.dashboard_config.max_concurrent_users,
            "session_timeout": self.dashboard_config.session_timeout
        }

# Global configuration instance
config_manager = ConfigManager()