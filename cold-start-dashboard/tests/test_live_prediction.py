"""
Property-based tests for Live ML Prediction Service
**Feature: cold-start-dashboard, Property 1: Prediction Input Validation**
**Feature: cold-start-dashboard, Property 2: Dual Endpoint Prediction**
**Feature: cold-start-dashboard, Property 4: Prediction Result Completeness**
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch
from datetime import datetime
import json

from services.live_prediction import LivePredictionService, PredictionRequest, PredictionResponse


@given(
    hour=st.integers(min_value=0, max_value=23),
    day=st.integers(min_value=0, max_value=6),
    traffic=st.floats(min_value=0.01, max_value=2.0),
    endpoint=st.sampled_from(['auth', 'profile', 'search']),
    new_user=st.booleans(),
    mobile=st.booleans()
)
@settings(max_examples=100)
def test_property_prediction_input_validation(hour, day, traffic, endpoint, new_user, mobile):
    """
    **Property 1: Prediction Input Validation**
    For any set of prediction parameters (hour 0-23, day 0-6, traffic 0.01-2.0, 
    endpoint type, user flags), the dashboard should generate a valid feature vector 
    and return probability values between 0 and 1.
    **Validates: Requirements 1.1, 1.5**
    """
    # Create prediction request
    request = PredictionRequest(
        hour_of_day=hour,
        day_of_week=day,
        traffic_intensity=traffic,
        endpoint_type=endpoint,
        user_type_new=new_user,
        device_mobile=mobile
    )
    
    # Mock SageMaker client
    mock_sagemaker = Mock()
    mock_sagemaker.invoke_endpoint.return_value = {
        'Body': Mock(read=Mock(return_value=b'0.5'))
    }
    
    # Create service with mocked client
    service = LivePredictionService(sagemaker_client=mock_sagemaker)
    
    # Test feature vector generation
    features = service.format_features(request)
    
    # Verify feature vector properties
    assert isinstance(features, list), "Features should be a list"
    assert len(features) == 9, "Feature vector should have 9 elements"
    
    # Verify all features are numeric
    for i, feature in enumerate(features):
        assert isinstance(feature, (int, float)), f"Feature {i} should be numeric, got {type(feature)}"
        assert not (isinstance(feature, float) and (feature != feature)), f"Feature {i} should not be NaN"
    
    # Verify feature ranges and types
    assert features[0] == float(hour), "Hour feature should match input"
    assert features[1] == float(day), "Day feature should match input"
    assert features[2] == float(traffic), "Traffic feature should match input"
    
    # Verify endpoint encoding (one-hot)
    endpoint_features = features[3:6]  # auth, profile, search
    assert sum(endpoint_features) == 1.0, "Exactly one endpoint should be encoded"
    assert all(f in [0.0, 1.0] for f in endpoint_features), "Endpoint features should be binary"
    
    # Verify user type and device features
    assert features[6] in [0.0, 1.0], "User type feature should be binary"
    assert features[7] in [0.0, 1.0], "Device feature should be binary"
    assert features[8] in [0.0, 1.0], "Business hours feature should be binary"
    
    # Test prediction with valid inputs
    response = service.predict_cold_start_risk(request)
    
    # Verify response structure
    assert isinstance(response, PredictionResponse), "Should return PredictionResponse"
    assert response.success, "Prediction should succeed with valid inputs"
    
    # Verify probability ranges
    assert 0.0 <= response.xgboost_probability <= 1.0, "XGBoost probability should be 0-1"
    assert 0.0 <= response.random_forest_probability <= 1.0, "Random Forest probability should be 0-1"
    assert 0.0 <= response.ensemble_probability <= 1.0, "Ensemble probability should be 0-1"
    assert 0.0 <= response.model_agreement <= 1.0, "Model agreement should be 0-1"
    
    # Verify response completeness
    assert response.prediction_label in ['cold_start', 'warm'], "Prediction label should be valid"
    assert isinstance(response.recommendation, str), "Recommendation should be string"
    assert len(response.recommendation) > 0, "Recommendation should not be empty"
    assert isinstance(response.timestamp, datetime), "Timestamp should be datetime"


@given(
    hour=st.integers().filter(lambda x: x < 0 or x > 23),
)
def test_invalid_hour_raises_error(hour):
    """Test that invalid hour values raise ValueError"""
    with pytest.raises(ValueError, match="hour_of_day must be 0-23"):
        PredictionRequest(
            hour_of_day=hour,
            day_of_week=1,
            traffic_intensity=1.0,
            endpoint_type='auth',
            user_type_new=False,
            device_mobile=False
        )


@given(
    day=st.integers().filter(lambda x: x < 0 or x > 6),
)
def test_invalid_day_raises_error(day):
    """Test that invalid day values raise ValueError"""
    with pytest.raises(ValueError, match="day_of_week must be 0-6"):
        PredictionRequest(
            hour_of_day=12,
            day_of_week=day,
            traffic_intensity=1.0,
            endpoint_type='auth',
            user_type_new=False,
            device_mobile=False
        )


@given(
    traffic=st.floats().filter(lambda x: x < 0.01 or x > 2.0 or x != x),  # Include NaN
)
def test_invalid_traffic_raises_error(traffic):
    """Test that invalid traffic values raise ValueError"""
    with pytest.raises(ValueError, match="traffic_intensity must be 0.01-2.0"):
        PredictionRequest(
            hour_of_day=12,
            day_of_week=1,
            traffic_intensity=traffic,
            endpoint_type='auth',
            user_type_new=False,
            device_mobile=False
        )


@given(
    endpoint=st.text().filter(lambda x: x not in ['auth', 'profile', 'search']),
)
def test_invalid_endpoint_raises_error(endpoint):
    """Test that invalid endpoint values raise ValueError"""
    with pytest.raises(ValueError, match="endpoint_type must be 'auth', 'profile', or 'search'"):
        PredictionRequest(
            hour_of_day=12,
            day_of_week=1,
            traffic_intensity=1.0,
            endpoint_type=endpoint,
            user_type_new=False,
            device_mobile=False
        )


