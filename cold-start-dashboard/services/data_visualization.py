"""
Data Visualization Service
Handles DynamoDB data querying, formatting, and statistical calculations for dashboard display
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class DynamoDBRecord:
    """Model for DynamoDB record data"""
    timestamp: datetime
    endpoint_type: str
    cold_start_label: int  # 0 or 1
    hour_of_day: int
    traffic_intensity: float
    user_type_new: int
    device_mobile: int
    is_business_hours: int
    
    @classmethod
    def from_dynamodb_item(cls, item: dict):
        """Create DynamoDBRecord from DynamoDB item"""
        # Convert Decimal types to appropriate Python types
        def convert_decimal(value):
            if isinstance(value, Decimal):
                return float(value) if value % 1 != 0 else int(value)
            return value
        
        # Parse timestamp - handle different possible formats
        timestamp_str = str(item.get('timestamp', ''))
        try:
            # Try ISO format first
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try Unix timestamp
                timestamp = datetime.fromtimestamp(float(timestamp_str))
            except (ValueError, TypeError):
                # Default to current time if parsing fails
                timestamp = datetime.utcnow()
        
        return cls(
            timestamp=timestamp,
            endpoint_type=str(item.get('endpoint_type', 'unknown')),
            cold_start_label=convert_decimal(item.get('cold_start_label', 0)),
            hour_of_day=convert_decimal(item.get('hour_of_day', 0)),
            traffic_intensity=convert_decimal(item.get('traffic_intensity', 0.0)),
            user_type_new=convert_decimal(item.get('user_type_new', 0)),
            device_mobile=convert_decimal(item.get('device_mobile', 0)),
            is_business_hours=convert_decimal(item.get('is_business_hours', 0))
        )

@dataclass
class DataStatistics:
    """Statistical calculations for dashboard display"""
    total_requests: int
    cold_start_count: int
    cold_start_ratio: float
    endpoint_distribution: Dict[str, int]
    traffic_levels: Dict[str, int]  # low, medium, high
    business_hours_ratio: float
    mobile_user_ratio: float
    new_user_ratio: float
    time_range: Tuple[datetime, datetime]

@dataclass
class TrendData:
    """Time series trend data"""
    hourly_counts: Dict[int, int]  # hour -> request count
    hourly_cold_starts: Dict[int, int]  # hour -> cold start count
    endpoint_trends: Dict[str, List[int]]  # endpoint -> hourly counts
    cold_start_trend: List[float]  # hourly cold start ratios

class DataVisualizationService:
    """
    Service for querying, formatting, and analyzing DynamoDB data for dashboard visualization
    """
    
    def __init__(self, dynamodb_resource=None):
        """
        Initialize the Data Visualization Service
        
        Args:
            dynamodb_resource: Optional DynamoDB resource. If None, will be created.
        """
        self.dynamodb_resource = dynamodb_resource
        self.table_name = config_manager.aws_config.dynamodb_table_name
        self.max_records = config_manager.dashboard_config.max_records_display
        self._cache = {}
        self._cache_ttl = 60  # Cache TTL in seconds
        
        # Initialize table reference
        if self.dynamodb_resource:
            self.table = self.dynamodb_resource.Table(self.table_name)
        else:
            self.table = None
    
    def get_recent_requests(self, limit: int = None) -> List[DynamoDBRecord]:
        """
        Get recent requests from DynamoDB with proper limiting
        
        Args:
            limit: Maximum number of records to return (defaults to config max)
            
        Returns:
            List of DynamoDBRecord objects, limited to specified count
        """
        try:
            if not self.table:
                logger.error("DynamoDB table not initialized")
                return []
            
            # Use provided limit or default from config, ensure it doesn't exceed max
            actual_limit = min(limit or self.max_records, self.max_records)
            
            # Check cache first
            cache_key = f"recent_requests_{actual_limit}"
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]["data"]
            
            # Query DynamoDB - scan with limit (in production, you'd want a better query pattern)
            response = self.table.scan(
                Limit=actual_limit * 2,  # Get more records to account for filtering
                Select='ALL_ATTRIBUTES'
            )
            
            # Convert to DynamoDBRecord objects
            records = []
            for item in response.get('Items', []):
                try:
                    record = DynamoDBRecord.from_dynamodb_item(item)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse DynamoDB item: {str(e)}")
                    continue
            
            # Sort by timestamp (most recent first) and limit
            records.sort(key=lambda x: x.timestamp, reverse=True)
            limited_records = records[:actual_limit]
            
            # Cache the result
            self._cache[cache_key] = {
                "data": limited_records,
                "timestamp": datetime.utcnow()
            }
            
            logger.info(f"Retrieved {len(limited_records)} recent requests from DynamoDB")
            return limited_records
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB query failed: {error_code} - {str(e)}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get recent requests: {str(e)}")
            return []
    
    def calculate_cold_start_ratio(self, data: List[DynamoDBRecord]) -> float:
        """
        Calculate cold start ratio from data records
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            Cold start ratio as a float between 0.0 and 1.0
        """
        if not data:
            return 0.0
        
        cold_start_count = sum(1 for record in data if record.cold_start_label == 1)
        total_count = len(data)
        
        return cold_start_count / total_count if total_count > 0 else 0.0
    
    def calculate_statistics(self, data: List[DynamoDBRecord]) -> DataStatistics:
        """
        Calculate comprehensive statistics from data records
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            DataStatistics object with calculated metrics
        """
        if not data:
            return DataStatistics(
                total_requests=0,
                cold_start_count=0,
                cold_start_ratio=0.0,
                endpoint_distribution={},
                traffic_levels={},
                business_hours_ratio=0.0,
                mobile_user_ratio=0.0,
                new_user_ratio=0.0,
                time_range=(datetime.utcnow(), datetime.utcnow())
            )
        
        total_requests = len(data)
        cold_start_count = sum(1 for record in data if record.cold_start_label == 1)
        cold_start_ratio = cold_start_count / total_requests
        
        # Calculate endpoint distribution
        endpoint_distribution = {}
        for record in data:
            endpoint = record.endpoint_type
            endpoint_distribution[endpoint] = endpoint_distribution.get(endpoint, 0) + 1
        
        # Calculate traffic level distribution
        traffic_levels = {"low": 0, "medium": 0, "high": 0}
        for record in data:
            if record.traffic_intensity <= 0.5:
                traffic_levels["low"] += 1
            elif record.traffic_intensity <= 1.0:
                traffic_levels["medium"] += 1
            else:
                traffic_levels["high"] += 1
        
        # Calculate ratios
        business_hours_count = sum(1 for record in data if record.is_business_hours == 1)
        mobile_user_count = sum(1 for record in data if record.device_mobile == 1)
        new_user_count = sum(1 for record in data if record.user_type_new == 1)
        
        business_hours_ratio = business_hours_count / total_requests
        mobile_user_ratio = mobile_user_count / total_requests
        new_user_ratio = new_user_count / total_requests
        
        # Calculate time range
        timestamps = [record.timestamp for record in data]
        time_range = (min(timestamps), max(timestamps))
        
        return DataStatistics(
            total_requests=total_requests,
            cold_start_count=cold_start_count,
            cold_start_ratio=cold_start_ratio,
            endpoint_distribution=endpoint_distribution,
            traffic_levels=traffic_levels,
            business_hours_ratio=business_hours_ratio,
            mobile_user_ratio=mobile_user_ratio,
            new_user_ratio=new_user_ratio,
            time_range=time_range
        )
    
    def calculate_trends(self, data: List[DynamoDBRecord]) -> TrendData:
        """
        Calculate trend data for time series visualization
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            TrendData object with trend calculations
        """
        if not data:
            return TrendData(
                hourly_counts={},
                hourly_cold_starts={},
                endpoint_trends={},
                cold_start_trend=[]
            )
        
        # Initialize hourly data structures
        hourly_counts = {hour: 0 for hour in range(24)}
        hourly_cold_starts = {hour: 0 for hour in range(24)}
        endpoint_trends = {}
        
        # Process each record
        for record in data:
            hour = record.hour_of_day
            
            # Count total requests per hour
            hourly_counts[hour] += 1
            
            # Count cold starts per hour
            if record.cold_start_label == 1:
                hourly_cold_starts[hour] += 1
            
            # Track endpoint trends
            endpoint = record.endpoint_type
            if endpoint not in endpoint_trends:
                endpoint_trends[endpoint] = [0] * 24
            endpoint_trends[endpoint][hour] += 1
        
        # Calculate cold start trend (ratio per hour)
        cold_start_trend = []
        for hour in range(24):
            total = hourly_counts[hour]
            cold_starts = hourly_cold_starts[hour]
            ratio = cold_starts / total if total > 0 else 0.0
            cold_start_trend.append(ratio)
        
        return TrendData(
            hourly_counts=hourly_counts,
            hourly_cold_starts=hourly_cold_starts,
            endpoint_trends=endpoint_trends,
            cold_start_trend=cold_start_trend
        )
    
    def format_data_for_display(self, data: List[DynamoDBRecord]) -> List[Dict[str, Any]]:
        """
        Format data records for dashboard table display
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            List of dictionaries formatted for display
        """
        formatted_data = []
        
        for record in data:
            # Format timestamp
            formatted_timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Format cold start indicator
            cold_start_indicator = "🔴 Cold Start" if record.cold_start_label == 1 else "🟢 Warm"
            
            # Format traffic level
            if record.traffic_intensity <= 0.5:
                traffic_level = "🟢 Low"
            elif record.traffic_intensity <= 1.0:
                traffic_level = "🟡 Medium"
            else:
                traffic_level = "🔴 High"
            
            # Format endpoint type
            endpoint_display = {
                'auth': '🔐 Auth',
                'profile': '👤 Profile', 
                'search': '🔍 Search'
            }.get(record.endpoint_type, f"❓ {record.endpoint_type}")
            
            # Format user type indicators
            user_indicators = []
            if record.user_type_new == 1:
                user_indicators.append("🆕 New")
            if record.device_mobile == 1:
                user_indicators.append("📱 Mobile")
            if record.is_business_hours == 1:
                user_indicators.append("🏢 Business Hours")
            
            user_context = " | ".join(user_indicators) if user_indicators else "👤 Regular"
            
            formatted_record = {
                "Timestamp": formatted_timestamp,
                "Endpoint": endpoint_display,
                "Status": cold_start_indicator,
                "Traffic Level": traffic_level,
                "User Context": user_context,
                "Traffic Intensity": f"{record.traffic_intensity:.2f}",
                "Hour": str(record.hour_of_day)
            }
            
            formatted_data.append(formatted_record)
        
        return formatted_data
    
    def get_data_summary(self, data: List[DynamoDBRecord]) -> Dict[str, Any]:
        """
        Get a comprehensive data summary for dashboard display
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            Dictionary with summary statistics and formatted data
        """
        statistics = self.calculate_statistics(data)
        trends = self.calculate_trends(data)
        formatted_data = self.format_data_for_display(data)
        
        return {
            "statistics": statistics,
            "trends": trends,
            "formatted_data": formatted_data,
            "last_updated": datetime.utcnow(),
            "data_freshness": self._calculate_data_freshness(data)
        }
    
    def filter_data_by_timerange(self, data: List[DynamoDBRecord], 
                                hours_back: int = 24) -> List[DynamoDBRecord]:
        """
        Filter data to only include records within specified time range
        
        Args:
            data: List of DynamoDBRecord objects
            hours_back: Number of hours back from now to include
            
        Returns:
            Filtered list of DynamoDBRecord objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        return [record for record in data if record.timestamp >= cutoff_time]
    
    def filter_data_by_endpoint(self, data: List[DynamoDBRecord], 
                               endpoint_type: str) -> List[DynamoDBRecord]:
        """
        Filter data by endpoint type
        
        Args:
            data: List of DynamoDBRecord objects
            endpoint_type: Endpoint type to filter by
            
        Returns:
            Filtered list of DynamoDBRecord objects
        """
        return [record for record in data if record.endpoint_type == endpoint_type]
    
    def get_endpoint_performance_comparison(self, data: List[DynamoDBRecord]) -> Dict[str, Dict[str, float]]:
        """
        Compare performance metrics across different endpoints
        
        Args:
            data: List of DynamoDBRecord objects
            
        Returns:
            Dictionary with endpoint performance comparisons
        """
        endpoint_metrics = {}
        
        # Group data by endpoint
        endpoints = set(record.endpoint_type for record in data)
        
        for endpoint in endpoints:
            endpoint_data = self.filter_data_by_endpoint(data, endpoint)
            
            if endpoint_data:
                cold_start_ratio = self.calculate_cold_start_ratio(endpoint_data)
                avg_traffic = sum(r.traffic_intensity for r in endpoint_data) / len(endpoint_data)
                request_count = len(endpoint_data)
                
                endpoint_metrics[endpoint] = {
                    "cold_start_ratio": cold_start_ratio,
                    "average_traffic_intensity": avg_traffic,
                    "request_count": request_count,
                    "performance_score": 1.0 - cold_start_ratio  # Higher is better
                }
        
        return endpoint_metrics
    
    def _calculate_data_freshness(self, data: List[DynamoDBRecord]) -> str:
        """Calculate how fresh the data is"""
        if not data:
            return "No data available"
        
        most_recent = max(record.timestamp for record in data)
        age = datetime.utcnow() - most_recent
        
        if age.total_seconds() < 300:  # 5 minutes
            return "Very Fresh (< 5 min)"
        elif age.total_seconds() < 900:  # 15 minutes
            return "Fresh (< 15 min)"
        elif age.total_seconds() < 3600:  # 1 hour
            return "Recent (< 1 hour)"
        else:
            hours = int(age.total_seconds() / 3600)
            return f"Older ({hours}h ago)"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache:
            return False
        
        cache_time = self._cache[cache_key]["timestamp"]
        return (datetime.utcnow() - cache_time).total_seconds() < self._cache_ttl
    
    def clear_cache(self):
        """Clear all cached data"""
        self._cache.clear()
        logger.info("Data visualization cache cleared")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information"""
        return {
            "cached_items": len(self._cache),
            "cache_keys": list(self._cache.keys()),
            "cache_ttl": self._cache_ttl
        }
    
    def format_timestamp_for_display(self, timestamp: datetime) -> str:
        """
        Format timestamp for consistent display across the dashboard
        
        Args:
            timestamp: datetime object to format
            
        Returns:
            Formatted timestamp string
        """
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    def format_endpoint_for_display(self, endpoint_type: str) -> str:
        """
        Format endpoint type with appropriate icons and labels
        
        Args:
            endpoint_type: Raw endpoint type string
            
        Returns:
            Formatted endpoint display string
        """
        endpoint_mappings = {
            'auth': '🔐 Authentication',
            'profile': '👤 User Profile', 
            'search': '🔍 Search Service'
        }
        return endpoint_mappings.get(endpoint_type, f"❓ {endpoint_type.title()}")
    
    def format_cold_start_indicator(self, cold_start_label: int) -> str:
        """
        Format cold start status with visual indicators
        
        Args:
            cold_start_label: 0 for warm, 1 for cold start
            
        Returns:
            Formatted status string with icon
        """
        return "🔴 Cold Start" if cold_start_label == 1 else "🟢 Warm Start"
    
    def format_traffic_level(self, traffic_intensity: float) -> str:
        """
        Format traffic intensity level with visual indicators
        
        Args:
            traffic_intensity: Traffic intensity value (0.01-2.0)
            
        Returns:
            Formatted traffic level string with icon
        """
        if traffic_intensity <= 0.5:
            return "🟢 Low Traffic"
        elif traffic_intensity <= 1.0:
            return "🟡 Medium Traffic"
        else:
            return "🔴 High Traffic"
    
    def format_user_context_indicators(self, record: DynamoDBRecord) -> str:
        """
        Format user context with multiple indicators
        
        Args:
            record: DynamoDBRecord with user context data
            
        Returns:
            Formatted user context string with multiple indicators
        """
        indicators = []
        
        if record.user_type_new == 1:
            indicators.append("🆕 New User")
        if record.device_mobile == 1:
            indicators.append("📱 Mobile Device")
        if record.is_business_hours == 1:
            indicators.append("🏢 Business Hours")
        
        return " | ".join(indicators) if indicators else "👤 Regular User"
    
    def create_data_table_headers(self) -> List[str]:
        """
        Create standardized column headers for data tables
        
        Returns:
            List of column header strings
        """
        return [
            "Timestamp",
            "Endpoint", 
            "Status",
            "Traffic Level",
            "User Context",
            "Traffic Intensity",
            "Hour of Day"
        ]
    
    def format_percentage(self, value: float, decimal_places: int = 1) -> str:
        """
        Format decimal value as percentage
        
        Args:
            value: Decimal value (0.0 to 1.0)
            decimal_places: Number of decimal places to show
            
        Returns:
            Formatted percentage string
        """
        return f"{value * 100:.{decimal_places}f}%"
    
    def format_count_with_total(self, count: int, total: int) -> str:
        """
        Format count with total and percentage
        
        Args:
            count: Count value
            total: Total value
            
        Returns:
            Formatted string like "25 of 100 (25.0%)"
        """
        if total == 0:
            return "0 of 0 (0.0%)"
        
        percentage = (count / total) * 100
        return f"{count} of {total} ({percentage:.1f}%)"