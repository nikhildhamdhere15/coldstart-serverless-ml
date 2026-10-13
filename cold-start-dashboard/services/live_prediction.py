"""
Live ML Prediction Service
Handles real-time ML predictions using SageMaker endpoints with ensemble calculations
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from config import config_manager
from services.error_handling import error_handler

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PredictionRequest:
    """Model for prediction request parameters"""
    hour_of_day: int  # 0-23
    day_of_week: int  # 0-6 (Monday=0)
    traffic_intensity: float  # 0.01-2.0
    endpoint_type: str  # 'auth', 'profile', 'search'
    user_type_new: bool
    device_mobile: bool
    
    def __post_init__(self):
        """Validate input parameters"""
        if not (0 <= self.hour_of_day <= 23):
            raise ValueError(f"hour_of_day must be 0-23, got {self.hour_of_day}")
        if not (0 <= self.day_of_week <= 6):
            raise ValueError(f"day_of_week must be 0-6, got {self.day_of_week}")
        if not (0.01 <= self.traffic_intensity <= 2.0):
            raise ValueError(f"traffic_intensity must be 0.01-2.0, got {self.traffic_intensity}")
        if self.endpoint_type not in ['auth', 'profile', 'search']:
            raise ValueError(f"endpoint_type must be 'auth', 'profile', or 'search', got {self.endpoint_type}")

@dataclass
class PredictionResponse:
    """Model for prediction response"""
    xgboost_probability: float
    random_forest_probability: float
    ensemble_probability: float
    prediction_label: str  # 'cold_start' or 'warm'
    recommendation: str
    model_agreement: float
    timestamp: datetime
    success: bool = True
    error_message: Optional[str] = None

class LivePredictionService:
    """
    Service for handling real-time ML predictions using SageMaker endpoints
    """
    
    def __init__(self, sagemaker_client=None):
        """
        Initialize the Live Prediction Service
        
        Args:
            sagemaker_client: Optional SageMaker runtime client. If None, will be created.
        """
        self.sagemaker_client = sagemaker_client
        self.xgboost_endpoint = config_manager.aws_config.xgboost_endpoint
        self.rf_endpoint = config_manager.aws_config.random_forest_endpoint
        self.prediction_timeout = config_manager.dashboard_config.prediction_timeout
        
        # Ensemble weights (70% XGBoost, 30% Random Forest)
        self.xgb_weight = 0.7
        self.rf_weight = 0.3
        
        # Endpoint type mappings for feature encoding
        self.endpoint_mappings = {
            'auth': [1, 0, 0],      # auth endpoint
            'profile': [0, 1, 0],   # profile endpoint  
            'search': [0, 0, 1]     # search endpoint
        }
    
    def predict_cold_start_risk(self, request: PredictionRequest) -> PredictionResponse:
        """
        Make cold start risk prediction using both ML models with comprehensive error handling
        
        Args:
            request: PredictionRequest with input parameters
            
        Returns:
            PredictionResponse with ensemble prediction results
        """
        try:
            # Format features for ML models
            features = self.format_features(request)
            
            # Get predictions from both endpoints with error handling
            xgb_prob, xgb_success = self._predict_single_endpoint_with_retry(
                self.xgboost_endpoint, features
            )
            rf_prob, rf_success = self._predict_single_endpoint_with_retry(
                self.rf_endpoint, features
            )
            
            # Handle complete failure
            if not xgb_success and not rf_success:
                # Try to get fallback prediction data
                fallback_data = error_handler.get_fallback_data('prediction', 'sagemaker')
                
                if fallback_data and fallback_data.data:
                    fallback_response = fallback_data.data.copy()
                    fallback_response['timestamp'] = datetime.now()
                    fallback_response['error_message'] = 'Both SageMaker endpoints failed - showing fallback prediction'
                    return PredictionResponse(**fallback_response)
                
                return PredictionResponse(
                    xgboost_probability=0.0,
                    random_forest_probability=0.0,
                    ensemble_probability=0.0,
                    prediction_label='unknown',
                    recommendation='Unable to make prediction - both endpoints failed. Please check service status.',
                    model_agreement=0.0,
                    timestamp=datetime.now(),
                    success=False,
                    error_message='Both SageMaker endpoints failed'
                )
            
            # Use available predictions or fallback values
            if not xgb_success:
                xgb_prob = rf_prob  # Use RF prediction as fallback
                logger.warning("XGBoost endpoint failed, using Random Forest prediction")
            
            if not rf_success:
                rf_prob = xgb_prob  # Use XGBoost prediction as fallback
                logger.warning("Random Forest endpoint failed, using XGBoost prediction")
            
            # Calculate ensemble prediction
            ensemble_prob = self._calculate_ensemble_prediction(xgb_prob, rf_prob)
            
            # Determine prediction label and recommendation
            prediction_label = 'cold_start' if ensemble_prob > 0.5 else 'warm'
            recommendation = self._generate_recommendation(ensemble_prob, request)
            
            # Calculate model agreement
            model_agreement = self._calculate_model_agreement(xgb_prob, rf_prob)
            
            response = PredictionResponse(
                xgboost_probability=xgb_prob,
                random_forest_probability=rf_prob,
                ensemble_probability=ensemble_prob,
                prediction_label=prediction_label,
                recommendation=recommendation,
                model_agreement=model_agreement,
                timestamp=datetime.now(),
                success=True
            )
            
            # Cache successful prediction for fallback
            error_handler.cache_successful_data('prediction', 'sagemaker', response.__dict__)
            
            return response
            
        except Exception as e:
            # Handle unexpected errors
            error_info = error_handler.handle_aws_error(e, 'sagemaker', 'predict_cold_start_risk')
            
            logger.error(f"Prediction failed: {error_info.message}")
            return PredictionResponse(
                xgboost_probability=0.0,
                random_forest_probability=0.0,
                ensemble_probability=0.0,
                prediction_label='error',
                recommendation=f'Prediction failed: {error_info.suggested_action}',
                model_agreement=0.0,
                timestamp=datetime.now(),
                success=False,
                error_message=error_info.message
            )
    
    def format_features(self, request: PredictionRequest) -> List[float]:
        """
        Convert UI inputs to ML feature vector
        
        Args:
            request: PredictionRequest with input parameters
            
        Returns:
            List of feature values for ML model input
        """
        # Calculate derived features
        is_business_hours = self._is_business_hours(request.hour_of_day, request.day_of_week)
        
        # Get endpoint encoding
        endpoint_encoding = self.endpoint_mappings[request.endpoint_type]
        
        # Create feature vector matching the ML model's expected input format
        # Based on the training data structure: 
        # [hour, day, traffic, endpoint_auth, endpoint_profile, endpoint_search, new_user, mobile, business_hours]
        features = [
            float(request.hour_of_day),
            float(request.day_of_week),
            float(request.traffic_intensity),
            float(endpoint_encoding[0]),  # endpoint_auth
            float(endpoint_encoding[1]),  # endpoint_profile
            float(endpoint_encoding[2]),  # endpoint_search
            float(1 if request.user_type_new else 0),
            float(1 if request.device_mobile else 0),
            float(1 if is_business_hours else 0)
        ]
        
        return features
    
    def _predict_single_endpoint_with_retry(self, endpoint_name: str, features: List[float]) -> Tuple[float, bool]:
        """
        Make prediction using a single SageMaker endpoint with retry logic
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            features: Feature vector for prediction
            
        Returns:
            Tuple of (probability, success_flag)
        """
        def _make_prediction():
            return self._predict_single_endpoint(endpoint_name, features)
        
        # Use error handler retry logic
        result, error_info = error_handler.retry_with_backoff(
            _make_prediction, 'sagemaker'
        )
        
        if error_info:
            logger.error(f"Endpoint {endpoint_name} failed after retries: {error_info.message}")
            return 0.0, False
        
        return result
    
    def _predict_single_endpoint(self, endpoint_name: str, features: List[float]) -> Tuple[float, bool]:
        """
        Make prediction using a single SageMaker endpoint
        
        Args:
            endpoint_name: Name of the SageMaker endpoint
            features: Feature vector for prediction
            
        Returns:
            Tuple of (probability, success_flag)
        """
        try:
            if not self.sagemaker_client:
                raise ValueError("SageMaker client not initialized")
            
            # Format features as CSV string for SageMaker
            feature_csv = ','.join(map(str, features))
            
            # Invoke SageMaker endpoint
            response = self.sagemaker_client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='text/csv',
                Body=feature_csv
            )
            
            # Parse response
            result = response['Body'].read().decode('utf-8')
            
            # Handle different response formats
            try:
                # Try parsing as JSON first
                result_data = json.loads(result)
                if isinstance(result_data, list) and len(result_data) > 0:
                    probability = float(result_data[0])
                elif isinstance(result_data, dict) and 'predictions' in result_data:
                    probability = float(result_data['predictions'][0])
                else:
                    probability = float(result_data)
            except (json.JSONDecodeError, KeyError):
                # Try parsing as plain number
                probability = float(result.strip())
            
            # Ensure probability is in valid range [0, 1]
            probability = max(0.0, min(1.0, probability))
            
            logger.debug(f"Prediction from {endpoint_name}: {probability}")
            return probability, True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"SageMaker endpoint {endpoint_name} failed: {error_code} - {str(e)}")
            return 0.0, False
            
        except Exception as e:
            logger.error(f"Prediction failed for endpoint {endpoint_name}: {str(e)}")
            return 0.0, False
    
    def _calculate_ensemble_prediction(self, xgb_prob: float, rf_prob: float) -> float:
        """
        Calculate ensemble prediction using weighted average
        
        Args:
            xgb_prob: XGBoost probability
            rf_prob: Random Forest probability
            
        Returns:
            Weighted ensemble probability
        """
        ensemble_prob = (self.xgb_weight * xgb_prob) + (self.rf_weight * rf_prob)
        return max(0.0, min(1.0, ensemble_prob))  # Ensure valid range
    
    def _calculate_model_agreement(self, xgb_prob: float, rf_prob: float) -> float:
        """
        Calculate agreement between models (1.0 - absolute difference)
        
        Args:
            xgb_prob: XGBoost probability
            rf_prob: Random Forest probability
            
        Returns:
            Model agreement score (0.0 to 1.0)
        """
        agreement = 1.0 - abs(xgb_prob - rf_prob)
        return max(0.0, min(1.0, agreement))
    
    def _generate_recommendation(self, ensemble_prob: float, request: PredictionRequest) -> str:
        """
        Generate actionable recommendation based on prediction
        
        Args:
            ensemble_prob: Ensemble prediction probability
            request: Original prediction request
            
        Returns:
            Recommendation string
        """
        if ensemble_prob > 0.7:
            return (f"HIGH RISK: {ensemble_prob:.1%} cold start probability. "
                   f"Consider pre-warming {request.endpoint_type} endpoint immediately.")
        elif ensemble_prob > 0.5:
            return (f"MODERATE RISK: {ensemble_prob:.1%} cold start probability. "
                   f"Monitor {request.endpoint_type} endpoint closely.")
        elif ensemble_prob > 0.3:
            return (f"LOW RISK: {ensemble_prob:.1%} cold start probability. "
                   f"Normal operation expected for {request.endpoint_type} endpoint.")
        else:
            return (f"VERY LOW RISK: {ensemble_prob:.1%} cold start probability. "
                   f"Optimal performance expected for {request.endpoint_type} endpoint.")
    
    def is_high_risk_prediction(self, ensemble_prob: float) -> bool:
        """
        Determine if a prediction indicates high cold start risk (>70%)
        
        Args:
            ensemble_prob: Ensemble prediction probability
            
        Returns:
            True if high risk (>0.7), False otherwise
        """
        return ensemble_prob > 0.7
    
    def get_warming_recommendation(self, request: PredictionRequest, ensemble_prob: float) -> dict:
        """
        Get detailed warming recommendation for high-risk predictions
        
        Args:
            request: Original prediction request
            ensemble_prob: Ensemble prediction probability
            
        Returns:
            Dict with warming recommendation details
        """
        if not self.is_high_risk_prediction(ensemble_prob):
            return {
                'should_warm': False,
                'risk_level': 'low',
                'message': 'No warming required - low cold start risk'
            }
        
        # Determine warming urgency based on risk level
        if ensemble_prob > 0.9:
            urgency = 'critical'
            message = f"CRITICAL: {ensemble_prob:.1%} cold start risk. Immediate warming required!"
        elif ensemble_prob > 0.8:
            urgency = 'high'
            message = f"HIGH: {ensemble_prob:.1%} cold start risk. Warming strongly recommended."
        else:
            urgency = 'moderate'
            message = f"MODERATE-HIGH: {ensemble_prob:.1%} cold start risk. Consider warming."
        
        return {
            'should_warm': True,
            'risk_level': urgency,
            'message': message,
            'target_endpoint': request.endpoint_type,
            'probability': ensemble_prob,
            'recommended_action': f"Pre-warm {request.endpoint_type} Lambda functions",
            'timing': 'immediate' if ensemble_prob > 0.8 else 'within_5_minutes'
        }
    
    def trigger_manual_warming(self, lambda_client, target_functions: list) -> dict:
        """
        Trigger manual warming for specified Lambda functions
        
        Args:
            lambda_client: AWS Lambda client
            target_functions: List of Lambda function names to warm
            
        Returns:
            Dict with warming results
        """
        results = {
            'triggered_at': datetime.now(),
            'functions': {},
            'overall_success': True
        }
        
        for function_name in target_functions:
            try:
                # Invoke the intelligent warmer function
                warmer_function = config_manager.aws_config.intelligent_warmer_function
                
                # Prepare warming payload
                warming_payload = {
                    'target_functions': [function_name],
                    'warming_reason': 'manual_high_risk_prediction',
                    'triggered_by': 'live_prediction_service'
                }
                
                # Invoke the warmer
                response = lambda_client.invoke(
                    FunctionName=warmer_function,
                    InvocationType='Event',  # Asynchronous invocation
                    Payload=json.dumps(warming_payload)
                )
                
                results['functions'][function_name] = {
                    'success': True,
                    'status_code': response['StatusCode'],
                    'message': 'Warming triggered successfully'
                }
                
                logger.info(f"Manual warming triggered for {function_name}")
                
            except Exception as e:
                results['functions'][function_name] = {
                    'success': False,
                    'error': str(e),
                    'message': f'Failed to trigger warming: {str(e)}'
                }
                results['overall_success'] = False
                logger.error(f"Failed to trigger warming for {function_name}: {str(e)}")
        
        return results
    
    def _is_business_hours(self, hour: int, day: int) -> bool:
        """
        Determine if the given time is during business hours
        
        Args:
            hour: Hour of day (0-23)
            day: Day of week (0-6, Monday=0)
            
        Returns:
            True if during business hours (Mon-Fri 9AM-5PM)
        """
        # Monday=0 to Friday=4
        is_weekday = 0 <= day <= 4
        # Business hours: 9 AM to 5 PM
        is_business_time = 9 <= hour <= 17
        
        return is_weekday and is_business_time
    
    def get_endpoint_status(self) -> Dict[str, bool]:
        """
        Check the availability of both SageMaker endpoints
        
        Returns:
            Dict with endpoint names as keys and availability as values
        """
        status = {}
        
        # Test with minimal feature vector
        test_features = [12.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        
        _, xgb_success = self._predict_single_endpoint(self.xgboost_endpoint, test_features)
        _, rf_success = self._predict_single_endpoint(self.rf_endpoint, test_features)
        
        status[self.xgboost_endpoint] = xgb_success
        status[self.rf_endpoint] = rf_success
        
        return status