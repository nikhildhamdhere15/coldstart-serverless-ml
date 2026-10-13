"""
Property-based test for prediction result completeness
**Feature: cold-start-dashboard, Property 4: Prediction Result Completeness**
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
    xgb_prob=st.floats(min_value=0.0, max_value=1.0),
    rf_prob=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=100)
def test_property_prediction_result_completeness(hour, day, traffic, endpoint, new_user, mobile, xgb_prob, rf_prob):
    """
    **Property 4: Prediction Result Completeness**
    For any successful prediction, the display should include XGBoost probability, 
    Random Forest probability, ensemble probability, model agreement, and recommendation text.
    **Validates: Requirements 1.4**
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
    
    # Mock SageMaker client with specific responses
    mock_sagemaker = Mock()
    
    def mock_invoke_endpoint(EndpointName, ContentType, Body):
        if 'xgboost' in EndpointName.lower():
            return {'Body': Mock(read=Mock(return_value=str(xgb_prob).encode()))}
        elif 'rf' in EndpointName.lower() or 'forest' in EndpointName.lower():
            return {'Body': Mock(read=Mock(return_value=str(rf_prob).encode()))}
        else:
            return {'Body': Mock(read=Mock(return_value=b'0.5'))}
    
    mock_sagemaker.invoke_endpoint.side_effect = mock_invoke_endpoint
    
    # Create service with mocked client
    service = LivePredictionService(sagemaker_client=mock_sagemaker)
    
    # Make prediction
    response = service.predict_cold_start_risk(request)
    
    # Verify prediction was successful
    assert response.success, "Prediction should succeed for valid inputs"
    
    # Verify all required fields are present and valid
    
    # 1. XGBoost probability
    assert hasattr(response, 'xgboost_probability'), "Response should have xgboost_probability field"
    assert isinstance(response.xgboost_probability, float), "XGBoost probability should be float"
    assert 0.0 <= response.xgboost_probability <= 1.0, "XGBoost probability should be 0-1"
    
    # 2. Random Forest probability
    assert hasattr(response, 'random_forest_probability'), "Response should have random_forest_probability field"
    assert isinstance(response.random_forest_probability, float), "Random Forest probability should be float"
    assert 0.0 <= response.random_forest_probability <= 1.0, "Random Forest probability should be 0-1"
    
    # 3. Ensemble probability
    assert hasattr(response, 'ensemble_probability'), "Response should have ensemble_probability field"
    assert isinstance(response.ensemble_probability, float), "Ensemble probability should be float"
    assert 0.0 <= response.ensemble_probability <= 1.0, "Ensemble probability should be 0-1"
    
    # 4. Model agreement
    assert hasattr(response, 'model_agreement'), "Response should have model_agreement field"
    assert isinstance(response.model_agreement, float), "Model agreement should be float"
    assert 0.0 <= response.model_agreement <= 1.0, "Model agreement should be 0-1"
    
    # 5. Recommendation text
    assert hasattr(response, 'recommendation'), "Response should have recommendation field"
    assert isinstance(response.recommendation, str), "Recommendation should be string"
    assert len(response.recommendation) > 0, "Recommendation should not be empty"
    assert any(keyword in response.recommendation.upper() for keyword in ['RISK', 'WARM', 'COLD']), "Recommendation should contain risk-related keywords"
    
    # 6. Prediction label
    assert hasattr(response, 'prediction_label'), "Response should have prediction_label field"
    assert isinstance(response.prediction_label, str), "Prediction label should be string"
    assert response.prediction_label in ['cold_start', 'warm'], "Prediction label should be valid"
    
    # 7. Timestamp
    assert hasattr(response, 'timestamp'), "Response should have timestamp field"
    assert isinstance(response.timestamp, datetime), "Timestamp should be datetime object"
    
    # 8. Success flag
    assert hasattr(response, 'success'), "Response should have success field"
    assert isinstance(response.success, bool), "Success should be boolean"
    assert response.success == True, "Success should be True for valid predictions"
    
    # Verify mathematical consistency
    # Model agreement should be 1 - |xgb_prob - rf_prob|
    expected_agreement = 1.0 - abs(response.xgboost_probability - response.random_forest_probability)
    assert abs(response.model_agreement - expected_agreement) < 1e-6, "Model agreement should be calculated correctly"
    
    # Ensemble should be weighted average (70% XGBoost, 30% Random Forest)
    expected_ensemble = (0.7 * response.xgboost_probability) + (0.3 * response.random_forest_probability)
    assert abs(response.ensemble_probability - expected_ensemble) < 1e-6, "Ensemble should be weighted average"
    
    # Prediction label should match ensemble probability threshold
    expected_label = 'cold_start' if response.ensemble_probability > 0.5 else 'warm'
    assert response.prediction_label == expected_label, "Prediction label should match ensemble probability"