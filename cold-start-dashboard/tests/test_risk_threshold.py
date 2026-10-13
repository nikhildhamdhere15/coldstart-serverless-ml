"""
Property-based test for risk threshold warnings
**Feature: cold-start-dashboard, Property 3: Risk Threshold Warning**
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock
from datetime import datetime

from services.live_prediction import LivePredictionService, PredictionRequest, PredictionResponse


@given(
    hour=st.integers(min_value=0, max_value=23),
    day=st.integers(min_value=0, max_value=6),
    traffic=st.floats(min_value=0.01, max_value=2.0),
    endpoint=st.sampled_from(['auth', 'profile', 'search']),
    new_user=st.booleans(),
    mobile=st.booleans(),
    high_risk_prob=st.floats(min_value=0.71, max_value=1.0)  # High risk probabilities > 0.7
)
@settings(max_examples=100)
def test_property_risk_threshold_warning(hour, day, traffic, endpoint, new_user, mobile, high_risk_prob):
    """
    **Property 3: Risk Threshold Warning**
    For any prediction with ensemble probability > 0.7, the dashboard should display 
    high-risk warning and warming recommendation.
    **Validates: Requirements 1.3**
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
    
    # Mock SageMaker client to return high-risk probabilities
    mock_sagemaker = Mock()
    
    def mock_invoke_endpoint(EndpointName, ContentType, Body):
        # Return probabilities that will result in high risk ensemble
        # Since ensemble = 0.7 * xgb + 0.3 * rf, we need to ensure ensemble > 0.7
        if 'xgboost' in EndpointName.lower():
            return {'Body': Mock(read=Mock(return_value=str(high_risk_prob).encode()))}
        elif 'rf' in EndpointName.lower() or 'forest' in EndpointName.lower():
            return {'Body': Mock(read=Mock(return_value=str(high_risk_prob).encode()))}
        else:
            return {'Body': Mock(read=Mock(return_value=str(high_risk_prob).encode()))}
    
    mock_sagemaker.invoke_endpoint.side_effect = mock_invoke_endpoint
    
    # Create service with mocked client
    service = LivePredictionService(sagemaker_client=mock_sagemaker)
    
    # Make prediction
    response = service.predict_cold_start_risk(request)
    
    # Verify prediction was successful
    assert response.success, "Prediction should succeed"
    
    # Verify ensemble probability is high risk (> 0.7)
    assert response.ensemble_probability > 0.7, f"Ensemble probability should be > 0.7, got {response.ensemble_probability}"
    
    # Verify high-risk detection
    assert service.is_high_risk_prediction(response.ensemble_probability), "Should detect high risk"
    
    # Verify recommendation contains high-risk warning
    recommendation = response.recommendation.upper()
    assert 'HIGH RISK' in recommendation, "Recommendation should contain 'HIGH RISK' warning"
    assert 'PRE-WARMING' in recommendation or 'WARMING' in recommendation, "Recommendation should mention warming"
    assert endpoint in recommendation.lower(), "Recommendation should mention the specific endpoint"
    
    # Test detailed warming recommendation
    warming_rec = service.get_warming_recommendation(request, response.ensemble_probability)
    
    # Verify warming recommendation structure
    assert isinstance(warming_rec, dict), "Warming recommendation should be a dict"
    assert warming_rec['should_warm'] == True, "Should recommend warming for high risk"
    assert 'risk_level' in warming_rec, "Should include risk level"
    assert 'message' in warming_rec, "Should include message"
    assert 'target_endpoint' in warming_rec, "Should include target endpoint"
    assert 'probability' in warming_rec, "Should include probability"
    
    # Verify risk level categorization
    if response.ensemble_probability > 0.9:
        assert warming_rec['risk_level'] == 'critical', "Should be critical risk for > 0.9"
    elif response.ensemble_probability > 0.8:
        assert warming_rec['risk_level'] == 'high', "Should be high risk for > 0.8"
    else:
        assert warming_rec['risk_level'] == 'moderate', "Should be moderate risk for 0.7-0.8"
    
    # Verify target endpoint matches request
    assert warming_rec['target_endpoint'] == endpoint, "Target endpoint should match request"
    
    # Verify probability matches response
    assert warming_rec['probability'] == response.ensemble_probability, "Probability should match response"


@given(
    hour=st.integers(min_value=0, max_value=23),
    day=st.integers(min_value=0, max_value=6),
    traffic=st.floats(min_value=0.01, max_value=2.0),
    endpoint=st.sampled_from(['auth', 'profile', 'search']),
    new_user=st.booleans(),
    mobile=st.booleans(),
    low_risk_prob=st.floats(min_value=0.0, max_value=0.7)  # Low risk probabilities <= 0.7
)
@settings(max_examples=100)
def test_property_no_warning_for_low_risk(hour, day, traffic, endpoint, new_user, mobile, low_risk_prob):
    """
    **Property 3b: No Warning for Low Risk**
    For any prediction with ensemble probability <= 0.7, the system should NOT display 
    high-risk warning or warming recommendation.
    **Validates: Requirements 1.3**
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
    
    # Mock SageMaker client to return low-risk probabilities
    mock_sagemaker = Mock()
    
    def mock_invoke_endpoint(EndpointName, ContentType, Body):
        return {'Body': Mock(read=Mock(return_value=str(low_risk_prob).encode()))}
    
    mock_sagemaker.invoke_endpoint.side_effect = mock_invoke_endpoint
    
    # Create service with mocked client
    service = LivePredictionService(sagemaker_client=mock_sagemaker)
    
    # Make prediction
    response = service.predict_cold_start_risk(request)
    
    # Verify prediction was successful
    assert response.success, "Prediction should succeed"
    
    # Verify ensemble probability is NOT high risk (<= 0.7)
    assert response.ensemble_probability <= 0.7, f"Ensemble probability should be <= 0.7, got {response.ensemble_probability}"
    
    # Verify NOT high-risk detection
    assert not service.is_high_risk_prediction(response.ensemble_probability), "Should NOT detect high risk"
    
    # Verify recommendation does NOT contain high-risk warning
    recommendation = response.recommendation.upper()
    assert 'HIGH RISK' not in recommendation, "Recommendation should NOT contain 'HIGH RISK' for low risk predictions"
    
    # Test warming recommendation for low risk
    warming_rec = service.get_warming_recommendation(request, response.ensemble_probability)
    
    # Verify no warming recommended for low risk
    assert warming_rec['should_warm'] == False, "Should NOT recommend warming for low risk"
    assert warming_rec['risk_level'] == 'low', "Risk level should be 'low'"
    assert 'no warming required' in warming_rec['message'].lower(), "Message should indicate no warming required"