"""
Property-based tests for Data Visualization Service
**Feature: cold-start-dashboard, Property 8: Data Record Limiting**
**Feature: cold-start-dashboard, Property 9: Statistical Calculation Accuracy**
**Feature: cold-start-dashboard, Property 11: Data Display Formatting**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import boto3

from services.data_visualization import (
    DataVisualizationService, 
    DynamoDBRecord, 
    DataStatistics,
    TrendData
)


# Test data generators
@st.composite
def generate_dynamodb_item(draw):
    """Generate a valid DynamoDB item for testing"""
    timestamp = draw(st.datetimes(
        min_value=datetime(2023, 1, 1),
        max_value=datetime.utcnow()
    ))
    
    return {
        'timestamp': timestamp.isoformat(),
        'endpoint_type': draw(st.sampled_from(['auth', 'profile', 'search'])),
        'cold_start_label': Decimal(draw(st.integers(min_value=0, max_value=1))),
        'hour_of_day': Decimal(draw(st.integers(min_value=0, max_value=23))),
        'traffic_intensity': Decimal(str(draw(st.floats(min_value=0.01, max_value=2.0)))),
        'user_type_new': Decimal(draw(st.integers(min_value=0, max_value=1))),
        'device_mobile': Decimal(draw(st.integers(min_value=0, max_value=1))),
        'is_business_hours': Decimal(draw(st.integers(min_value=0, max_value=1)))
    }


@st.composite
def generate_dynamodb_record(draw):
    """Generate a DynamoDBRecord for testing"""
    timestamp = draw(st.datetimes(
        min_value=datetime(2023, 1, 1),
        max_value=datetime.utcnow()
    ))
    
    return DynamoDBRecord(
        timestamp=timestamp,
        endpoint_type=draw(st.sampled_from(['auth', 'profile', 'search'])),
        cold_start_label=draw(st.integers(min_value=0, max_value=1)),
        hour_of_day=draw(st.integers(min_value=0, max_value=23)),
        traffic_intensity=draw(st.floats(min_value=0.01, max_value=2.0)),
        user_type_new=draw(st.integers(min_value=0, max_value=1)),
        device_mobile=draw(st.integers(min_value=0, max_value=1)),
        is_business_hours=draw(st.integers(min_value=0, max_value=1))
    )


@given(
    requested_limit=st.integers(min_value=1, max_value=100),
    available_records=st.integers(min_value=0, max_value=200)
)
@settings(max_examples=100)
def test_property_data_record_limiting(requested_limit, available_records):
    """
    **Property 8: Data Record Limiting**
    For any DynamoDB query, the dashboard should return exactly the requested number 
    of recent records (max 50) with all required fields present.
    **Validates: Requirements 3.1**
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Generate mock items
    mock_items = []
    for i in range(available_records):
        timestamp = datetime.utcnow() - timedelta(minutes=i)
        mock_items.append({
            'timestamp': timestamp.isoformat(),
            'endpoint_type': 'auth',
            'cold_start_label': Decimal('0'),
            'hour_of_day': Decimal('12'),
            'traffic_intensity': Decimal('1.0'),
            'user_type_new': Decimal('0'),
            'device_mobile': Decimal('0'),
            'is_business_hours': Decimal('1')
        })
    
    # Configure mock response
    mock_table.scan.return_value = {'Items': mock_items}
    
    # Create service with mock table
    service = DataVisualizationService()
    service.table = mock_table
    service.max_records = 50  # Set the configured maximum
    
    # Test the limiting behavior
    result = service.get_recent_requests(limit=requested_limit)
    
    # Calculate expected limit (should not exceed max_records or available records)
    expected_limit = min(requested_limit, service.max_records, available_records)
    
    # Verify record limiting
    assert len(result) <= expected_limit, f"Should return at most {expected_limit} records"
    assert len(result) <= service.max_records, f"Should never exceed max_records ({service.max_records})"
    
    # If we have enough records, we should get exactly what we asked for (up to max)
    if available_records >= min(requested_limit, service.max_records):
        assert len(result) == min(requested_limit, service.max_records), \
            "Should return exactly the requested number (up to max)"
    else:
        # If we don't have enough records, we should get all available
        assert len(result) == available_records, "Should return all available records when less than requested"
    
    # Verify all returned records have required fields
    for record in result:
        assert isinstance(record, DynamoDBRecord), "Should return DynamoDBRecord objects"
        assert isinstance(record.timestamp, datetime), "Timestamp should be datetime"
        assert record.endpoint_type in ['auth', 'profile', 'search'], "Endpoint should be valid"
        assert record.cold_start_label in [0, 1], "Cold start label should be 0 or 1"
        assert 0 <= record.hour_of_day <= 23, "Hour should be 0-23"
        assert 0.01 <= record.traffic_intensity <= 2.0, "Traffic intensity should be valid range"
        assert record.user_type_new in [0, 1], "User type should be 0 or 1"
        assert record.device_mobile in [0, 1], "Device mobile should be 0 or 1"
        assert record.is_business_hours in [0, 1], "Business hours should be 0 or 1"
    
    # Verify records are sorted by timestamp (most recent first)
    if len(result) > 1:
        for i in range(len(result) - 1):
            assert result[i].timestamp >= result[i + 1].timestamp, \
                "Records should be sorted by timestamp (most recent first)"


@given(
    records=st.lists(generate_dynamodb_record(), min_size=0, max_size=100)
)
@settings(max_examples=100)
def test_property_statistical_calculation_accuracy(records):
    """
    **Property 9: Statistical Calculation Accuracy**
    For any dataset of DynamoDB records, cold start ratio should equal the count 
    of records with cold_start_label=1 divided by total records.
    **Validates: Requirements 3.3**
    """
    service = DataVisualizationService()
    
    # Test cold start ratio calculation
    calculated_ratio = service.calculate_cold_start_ratio(records)
    
    if not records:
        assert calculated_ratio == 0.0, "Empty dataset should have 0.0 cold start ratio"
    else:
        # Calculate expected ratio manually
        cold_start_count = sum(1 for record in records if record.cold_start_label == 1)
        expected_ratio = cold_start_count / len(records)
        
        # Verify accuracy
        assert abs(calculated_ratio - expected_ratio) < 1e-10, \
            f"Cold start ratio should be accurate: expected {expected_ratio}, got {calculated_ratio}"
        
        # Verify ratio is in valid range
        assert 0.0 <= calculated_ratio <= 1.0, "Cold start ratio should be between 0.0 and 1.0"
    
    # Test comprehensive statistics calculation
    statistics = service.calculate_statistics(records)
    
    # Verify statistics accuracy
    assert statistics.total_requests == len(records), "Total requests should match record count"
    
    if records:
        # Verify cold start count and ratio
        expected_cold_starts = sum(1 for record in records if record.cold_start_label == 1)
        assert statistics.cold_start_count == expected_cold_starts, \
            "Cold start count should be accurate"
        
        expected_ratio = expected_cold_starts / len(records)
        assert abs(statistics.cold_start_ratio - expected_ratio) < 1e-10, \
            "Statistics cold start ratio should match calculated ratio"
        
        # Verify endpoint distribution
        expected_endpoints = {}
        for record in records:
            endpoint = record.endpoint_type
            expected_endpoints[endpoint] = expected_endpoints.get(endpoint, 0) + 1
        
        assert statistics.endpoint_distribution == expected_endpoints, \
            "Endpoint distribution should be accurate"
        
        # Verify traffic level distribution
        expected_traffic = {"low": 0, "medium": 0, "high": 0}
        for record in records:
            if record.traffic_intensity <= 0.5:
                expected_traffic["low"] += 1
            elif record.traffic_intensity <= 1.0:
                expected_traffic["medium"] += 1
            else:
                expected_traffic["high"] += 1
        
        assert statistics.traffic_levels == expected_traffic, \
            "Traffic level distribution should be accurate"
        
        # Verify ratio calculations
        business_hours_count = sum(1 for record in records if record.is_business_hours == 1)
        mobile_count = sum(1 for record in records if record.device_mobile == 1)
        new_user_count = sum(1 for record in records if record.user_type_new == 1)
        
        expected_business_ratio = business_hours_count / len(records)
        expected_mobile_ratio = mobile_count / len(records)
        expected_new_user_ratio = new_user_count / len(records)
        
        assert abs(statistics.business_hours_ratio - expected_business_ratio) < 1e-10, \
            "Business hours ratio should be accurate"
        assert abs(statistics.mobile_user_ratio - expected_mobile_ratio) < 1e-10, \
            "Mobile user ratio should be accurate"
        assert abs(statistics.new_user_ratio - expected_new_user_ratio) < 1e-10, \
            "New user ratio should be accurate"
        
        # Verify time range
        timestamps = [record.timestamp for record in records]
        expected_min = min(timestamps)
        expected_max = max(timestamps)
        assert statistics.time_range == (expected_min, expected_max), \
            "Time range should be accurate"
    else:
        # Empty dataset should have zero statistics
        assert statistics.cold_start_count == 0, "Empty dataset should have 0 cold starts"
        assert statistics.cold_start_ratio == 0.0, "Empty dataset should have 0.0 ratio"
        assert statistics.endpoint_distribution == {}, "Empty dataset should have empty distribution"


@given(
    records=st.lists(generate_dynamodb_record(), min_size=1, max_size=50)
)
@settings(max_examples=100)
def test_property_data_display_formatting(records):
    """
    **Property 11: Data Display Formatting**
    For any data record displayed, all required fields (timestamp, endpoint, 
    cold start indicator, traffic level) should be present and properly formatted.
    **Validates: Requirements 3.5**
    """
    service = DataVisualizationService()
    
    # Format data for display
    formatted_data = service.format_data_for_display(records)
    
    # Verify we get the same number of formatted records
    assert len(formatted_data) == len(records), \
        "Should format all input records"
    
    # Verify each formatted record has all required fields
    required_fields = [
        "Timestamp", "Endpoint", "Status", "Traffic Level", 
        "User Context", "Traffic Intensity", "Hour"
    ]
    
    for i, formatted_record in enumerate(formatted_data):
        original_record = records[i]
        
        # Verify all required fields are present
        for field in required_fields:
            assert field in formatted_record, f"Field '{field}' should be present in formatted record"
            assert formatted_record[field] is not None, f"Field '{field}' should not be None"
            assert isinstance(formatted_record[field], str), f"Field '{field}' should be string"
            assert len(formatted_record[field]) > 0, f"Field '{field}' should not be empty"
        
        # Verify timestamp formatting
        timestamp_str = formatted_record["Timestamp"]
        # Should be in format "YYYY-MM-DD HH:MM:SS"
        assert len(timestamp_str) == 19, "Timestamp should be 19 characters long"
        assert timestamp_str[4] == '-', "Timestamp should have dash at position 4"
        assert timestamp_str[7] == '-', "Timestamp should have dash at position 7"
        assert timestamp_str[10] == ' ', "Timestamp should have space at position 10"
        assert timestamp_str[13] == ':', "Timestamp should have colon at position 13"
        assert timestamp_str[16] == ':', "Timestamp should have colon at position 16"
        
        # Verify endpoint formatting
        endpoint_str = formatted_record["Endpoint"]
        if original_record.endpoint_type == 'auth':
            assert '🔐 Auth' in endpoint_str, "Auth endpoint should be properly formatted"
        elif original_record.endpoint_type == 'profile':
            assert '👤 Profile' in endpoint_str, "Profile endpoint should be properly formatted"
        elif original_record.endpoint_type == 'search':
            assert '🔍 Search' in endpoint_str, "Search endpoint should be properly formatted"
        
        # Verify cold start status formatting
        status_str = formatted_record["Status"]
        if original_record.cold_start_label == 1:
            assert '🔴 Cold Start' in status_str, "Cold start should be properly indicated"
        else:
            assert '🟢 Warm' in status_str, "Warm start should be properly indicated"
        
        # Verify traffic level formatting
        traffic_str = formatted_record["Traffic Level"]
        if original_record.traffic_intensity <= 0.5:
            assert '🟢 Low' in traffic_str, "Low traffic should be properly indicated"
        elif original_record.traffic_intensity <= 1.0:
            assert '🟡 Medium' in traffic_str, "Medium traffic should be properly indicated"
        else:
            assert '🔴 High' in traffic_str, "High traffic should be properly indicated"
        
        # Verify user context formatting
        user_context = formatted_record["User Context"]
        if original_record.user_type_new == 1:
            assert '🆕 New' in user_context, "New user should be indicated"
        if original_record.device_mobile == 1:
            assert '📱 Mobile' in user_context, "Mobile device should be indicated"
        if original_record.is_business_hours == 1:
            assert '🏢 Business Hours' in user_context, "Business hours should be indicated"
        
        # Verify traffic intensity formatting
        traffic_intensity_str = formatted_record["Traffic Intensity"]
        # Should be formatted as decimal with 2 places
        try:
            parsed_intensity = float(traffic_intensity_str)
            assert abs(parsed_intensity - original_record.traffic_intensity) < 0.01, \
                "Traffic intensity should be accurately formatted"
        except ValueError:
            pytest.fail("Traffic intensity should be parseable as float")
        
        # Verify hour formatting
        hour_str = formatted_record["Hour"]
        try:
            parsed_hour = int(hour_str)
            assert parsed_hour == original_record.hour_of_day, \
                "Hour should match original record"
        except ValueError:
            pytest.fail("Hour should be parseable as integer")


def test_empty_data_handling():
    """Test that service handles empty data gracefully"""
    service = DataVisualizationService()
    
    # Test empty list handling
    empty_records = []
    
    # Should not raise exceptions
    ratio = service.calculate_cold_start_ratio(empty_records)
    assert ratio == 0.0
    
    statistics = service.calculate_statistics(empty_records)
    assert statistics.total_requests == 0
    
    trends = service.calculate_trends(empty_records)
    assert len(trends.hourly_counts) == 0 or all(count == 0 for count in trends.hourly_counts.values())
    
    formatted = service.format_data_for_display(empty_records)
    assert formatted == []


def test_dynamodb_record_from_item():
    """Test DynamoDBRecord creation from DynamoDB item"""
    # Test with valid item
    item = {
        'timestamp': '2023-12-01T12:00:00',
        'endpoint_type': 'auth',
        'cold_start_label': Decimal('1'),
        'hour_of_day': Decimal('12'),
        'traffic_intensity': Decimal('1.5'),
        'user_type_new': Decimal('1'),
        'device_mobile': Decimal('0'),
        'is_business_hours': Decimal('1')
    }
    
    record = DynamoDBRecord.from_dynamodb_item(item)
    
    assert isinstance(record.timestamp, datetime)
    assert record.endpoint_type == 'auth'
    assert record.cold_start_label == 1
    assert record.hour_of_day == 12
    assert record.traffic_intensity == 1.5
    assert record.user_type_new == 1
    assert record.device_mobile == 0
    assert record.is_business_hours == 1


def test_service_initialization():
    """Test service initialization with and without DynamoDB resource"""
    # Test without resource
    service1 = DataVisualizationService()
    assert service1.table is None
    
    # Test with mock resource
    mock_resource = Mock()
    mock_table = Mock()
    mock_resource.Table.return_value = mock_table
    
    service2 = DataVisualizationService(dynamodb_resource=mock_resource)
    assert service2.table == mock_table