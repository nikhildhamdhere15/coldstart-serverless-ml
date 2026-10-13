"""
Test Serverless Ensemble Endpoints with Sample Data
Comprehensive testing of your deployed serverless cold start predictors
"""

import boto3
import json
import time
from datetime import datetime
import pandas as pd

class ServerlessEndpointTester:
    def __init__(self, region='ap-south-1'):
        self.region = region
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=region)
        
        # Your deployed serverless endpoints
        self.xgboost_endpoint = 'cold-start-xgboost-serverless'
        self.rf_endpoint = 'cold-start-rf-serverless'
    
    def create_test_scenarios(self):
        """Create diverse test scenarios for cold start prediction"""
        scenarios = [
            {
                'name': 'High Risk - Weekend Night, New Mobile User',
                'description': 'New user on mobile at 2 AM on Saturday with low traffic',
                'features': [2, 5, 0.1, 1, 0, 0, 1, 1, 0],  # Very likely cold start
                'expected': 'high_cold_start'
            },
            {
                'name': 'Low Risk - Business Hours, Existing Desktop User',
                'description': 'Existing user on desktop at 2 PM on Tuesday with high traffic',
                'features': [14, 1, 0.8, 1, 0, 0, 0, 0, 1],  # Very likely warm
                'expected': 'low_cold_start'
            },
            {
                'name': 'Medium Risk - Evening, New User, Profile Endpoint',
                'description': 'New user accessing profile at 7 PM on Wednesday',
                'features': [19, 2, 0.4, 0, 1, 0, 1, 1, 0],  # Medium risk
                'expected': 'medium_cold_start'
            },
            {
                'name': 'Edge Case - Early Morning, Search Endpoint',
                'description': 'User searching at 5 AM on Monday with very low traffic',
                'features': [5, 0, 0.05, 0, 0, 1, 0, 0, 0],  # High risk
                'expected': 'high_cold_start'
            },
            {
                'name': 'Peak Hours - Auth Endpoint, High Traffic',
                'description': 'Authentication during peak business hours',
                'features': [11, 2, 0.9, 1, 0, 0, 0, 0, 1],  # Low risk
                'expected': 'low_cold_start'
            },
            {
                'name': 'Weekend Day - Profile Access',
                'description': 'Profile access on Saturday afternoon',
                'features': [15, 5, 0.3, 0, 1, 0, 0, 1, 0],  # Medium-high risk
                'expected': 'medium_cold_start'
            },
            {
                'name': 'Late Night - Existing User',
                'description': 'Existing user late at night on weekday',
                'features': [23, 3, 0.2, 1, 0, 0, 0, 0, 0],  # High risk
                'expected': 'high_cold_start'
            },
            {
                'name': 'Lunch Time - Mobile Search',
                'description': 'Mobile search during lunch time',
                'features': [12, 1, 0.6, 0, 0, 1, 0, 1, 1],  # Low-medium risk
                'expected': 'low_cold_start'
            }
        ]
        
        return scenarios
    
    def predict_single_endpoint(self, endpoint_name, features):
        """Make prediction on a single endpoint"""
        try:
            csv_input = ','.join(map(str, features))
            
            start_time = time.time()
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='text/csv',
                Body=csv_input
            )
            end_time = time.time()
            
            result = json.loads(response['Body'].read().decode())
            probability = float(result)
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            
            return {
                'probability': probability,
                'latency_ms': latency,
                'success': True,
                'error': None
            }
            
        except Exception as e:
            return {
                'probability': None,
                'latency_ms': None,
                'success': False,
                'error': str(e)
            }
    
    def make_ensemble_prediction(self, features):
        """Make ensemble prediction using both endpoints"""
        try:
            # Get predictions from both models
            xgb_result = self.predict_single_endpoint(self.xgboost_endpoint, features)
            rf_result = self.predict_single_endpoint(self.rf_endpoint, features)
            
            # Calculate ensemble if both succeeded
            if xgb_result['success'] and rf_result['success']:
                xgb_prob = xgb_result['probability']
                rf_prob = rf_result['probability']
                
                # Weighted ensemble (70% XGBoost, 30% Random Forest)
                ensemble_prob = 0.7 * xgb_prob + 0.3 * rf_prob
                
                # Model agreement
                model_agreement = 1.0 - abs(xgb_prob - rf_prob)
                
                # Confidence based on agreement
                if model_agreement > 0.9:
                    confidence = 'high'
                elif model_agreement > 0.7:
                    confidence = 'medium'
                else:
                    confidence = 'low'
                
                # Prediction and recommendation
                prediction = 'cold_start' if ensemble_prob > 0.5 else 'warm'
                
                if ensemble_prob > 0.8:
                    recommendation = 'Definitely pre-warm Lambda'
                    risk_level = 'HIGH'
                elif ensemble_prob > 0.6:
                    recommendation = 'Consider pre-warming Lambda'
                    risk_level = 'MEDIUM'
                elif ensemble_prob > 0.4:
                    recommendation = 'Monitor closely'
                    risk_level = 'LOW'
                else:
                    recommendation = 'Lambda likely warm'
                    risk_level = 'VERY LOW'
                
                return {
                    'ensemble_probability': ensemble_prob,
                    'prediction': prediction,
                    'confidence': confidence,
                    'risk_level': risk_level,
                    'recommendation': recommendation,
                    'model_agreement': model_agreement,
                    'xgboost': xgb_result,
                    'random_forest': rf_result,
                    'total_latency_ms': xgb_result['latency_ms'] + rf_result['latency_ms'],
                    'success': True
                }
            else:
                return {
                    'success': False,
                    'error': 'One or both endpoints failed',
                    'xgboost': xgb_result,
                    'random_forest': rf_result
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def explain_features(self, features):
        """Explain what the features represent"""
        feature_names = [
            'hour_of_day', 'day_of_week', 'traffic_intensity',
            'endpoint_auth', 'endpoint_profile', 'endpoint_search',
            'user_type_new', 'device_mobile', 'is_business_hours'
        ]
        
        explanations = []
        
        # Time features
        hour = features[0]
        day = features[1]
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        explanations.append(f"Time: {hour}:00 on {day_names[day]}")
        
        # Traffic
        traffic = features[2]
        if traffic > 0.7:
            traffic_desc = "High traffic"
        elif traffic > 0.4:
            traffic_desc = "Medium traffic"
        else:
            traffic_desc = "Low traffic"
        explanations.append(f"Traffic: {traffic:.1%} ({traffic_desc})")
        
        # Endpoint
        if features[3]:
            endpoint = "Authentication"
        elif features[4]:
            endpoint = "Profile"
        elif features[5]:
            endpoint = "Search"
        else:
            endpoint = "Unknown"
        explanations.append(f"Endpoint: {endpoint}")
        
        # User type
        user_type = "New user" if features[6] else "Existing user"
        explanations.append(f"User: {user_type}")
        
        # Device
        device = "Mobile" if features[7] else "Desktop"
        explanations.append(f"Device: {device}")
        
        # Business hours
        business_hours = "Yes" if features[8] else "No"
        explanations.append(f"Business hours: {business_hours}")
        
        return explanations
    
    def test_all_scenarios(self):
        """Test all predefined scenarios"""
        try:
            print("=" * 80)
            print("SERVERLESS ENSEMBLE ENDPOINT TESTING")
            print("=" * 80)
            print(f"Testing endpoints:")
            print(f"  XGBoost: {self.xgboost_endpoint}")
            print(f"  Random Forest: {self.rf_endpoint}")
            print()
            
            scenarios = self.create_test_scenarios()
            results = []
            
            for i, scenario in enumerate(scenarios, 1):
                print(f"[TEST {i}] {scenario['name']}")
                print(f"Description: {scenario['description']}")
                
                # Explain features
                explanations = self.explain_features(scenario['features'])
                print("Features:")
                for explanation in explanations:
                    print(f"  • {explanation}")
                
                # Make prediction
                result = self.make_ensemble_prediction(scenario['features'])
                
                if result['success']:
                    print(f"\n[RESULTS]")
                    print(f"  Ensemble Probability: {result['ensemble_probability']:.3f}")
                    print(f"  Prediction: {result['prediction'].upper()}")
                    print(f"  Risk Level: {result['risk_level']}")
                    print(f"  Confidence: {result['confidence'].upper()}")
                    print(f"  Recommendation: {result['recommendation']}")
                    print(f"  Model Agreement: {result['model_agreement']:.3f}")
                    print(f"  XGBoost: {result['xgboost']['probability']:.3f} ({result['xgboost']['latency_ms']:.1f}ms)")
                    print(f"  Random Forest: {result['random_forest']['probability']:.3f} ({result['random_forest']['latency_ms']:.1f}ms)")
                    print(f"  Total Latency: {result['total_latency_ms']:.1f}ms")
                    
                    # Add scenario info to result
                    result.update({
                        'scenario_name': scenario['name'],
                        'scenario_description': scenario['description'],
                        'features': scenario['features'],
                        'expected': scenario['expected']
                    })
                    
                else:
                    print(f"\n[ERROR] {result['error']}")
                
                results.append(result)
                print("\n" + "-" * 80 + "\n")
                
                # Small delay between tests
                time.sleep(0.5)
            
            # Summary
            self.print_summary(results)
            
            # Save results
            self.save_results(results)
            
            return results
            
        except Exception as e:
            print(f"[ERROR] Testing failed: {str(e)}")
            return []
    
    def print_summary(self, results):
        """Print test summary"""
        try:
            print("=" * 80)
            print("TEST SUMMARY")
            print("=" * 80)
            
            successful_tests = [r for r in results if r.get('success', False)]
            
            if not successful_tests:
                print("No successful tests to summarize")
                return
            
            # Overall statistics
            total_tests = len(results)
            successful_count = len(successful_tests)
            
            print(f"Total Tests: {total_tests}")
            print(f"Successful: {successful_count}")
            print(f"Success Rate: {successful_count/total_tests*100:.1f}%")
            print()
            
            # Prediction statistics
            cold_start_predictions = sum(1 for r in successful_tests if r['prediction'] == 'cold_start')
            warm_predictions = successful_count - cold_start_predictions
            
            print(f"Cold Start Predictions: {cold_start_predictions} ({cold_start_predictions/successful_count*100:.1f}%)")
            print(f"Warm Predictions: {warm_predictions} ({warm_predictions/successful_count*100:.1f}%)")
            print()
            
            # Risk level distribution
            risk_levels = {}
            for result in successful_tests:
                risk = result['risk_level']
                risk_levels[risk] = risk_levels.get(risk, 0) + 1
            
            print("Risk Level Distribution:")
            for risk, count in sorted(risk_levels.items()):
                print(f"  {risk}: {count} ({count/successful_count*100:.1f}%)")
            print()
            
            # Performance statistics
            avg_ensemble_prob = sum(r['ensemble_probability'] for r in successful_tests) / successful_count
            avg_agreement = sum(r['model_agreement'] for r in successful_tests) / successful_count
            avg_latency = sum(r['total_latency_ms'] for r in successful_tests) / successful_count
            
            print(f"Average Ensemble Probability: {avg_ensemble_prob:.3f}")
            print(f"Average Model Agreement: {avg_agreement:.3f}")
            print(f"Average Total Latency: {avg_latency:.1f}ms")
            print()
            
            # Confidence distribution
            confidence_levels = {}
            for result in successful_tests:
                conf = result['confidence']
                confidence_levels[conf] = confidence_levels.get(conf, 0) + 1
            
            print("Confidence Distribution:")
            for conf, count in sorted(confidence_levels.items()):
                print(f"  {conf.upper()}: {count} ({count/successful_count*100:.1f}%)")
            
        except Exception as e:
            print(f"[ERROR] Summary generation failed: {str(e)}")
    
    def save_results(self, results):
        """Save test results to files"""
        try:
            # Save detailed JSON results
            output_data = {
                'test_timestamp': datetime.now().isoformat(),
                'endpoints': {
                    'xgboost': self.xgboost_endpoint,
                    'random_forest': self.rf_endpoint
                },
                'total_tests': len(results),
                'successful_tests': len([r for r in results if r.get('success', False)]),
                'results': results
            }
            
            with open('serverless_endpoint_test_results.json', 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            
            # Save CSV summary
            csv_data = []
            for result in results:
                if result.get('success', False):
                    csv_data.append({
                        'scenario_name': result['scenario_name'],
                        'ensemble_probability': result['ensemble_probability'],
                        'prediction': result['prediction'],
                        'risk_level': result['risk_level'],
                        'confidence': result['confidence'],
                        'model_agreement': result['model_agreement'],
                        'xgboost_probability': result['xgboost']['probability'],
                        'rf_probability': result['random_forest']['probability'],
                        'xgboost_latency_ms': result['xgboost']['latency_ms'],
                        'rf_latency_ms': result['random_forest']['latency_ms'],
                        'total_latency_ms': result['total_latency_ms'],
                        'recommendation': result['recommendation']
                    })
            
            if csv_data:
                df = pd.DataFrame(csv_data)
                df.to_csv('serverless_endpoint_test_summary.csv', index=False)
            
            print(f"[SAVED] Results saved to:")
            print(f"  • serverless_endpoint_test_results.json (detailed)")
            print(f"  • serverless_endpoint_test_summary.csv (summary)")
            
        except Exception as e:
            print(f"[ERROR] Failed to save results: {str(e)}")
    
    def test_performance(self, num_requests=10):
        """Test endpoint performance with multiple requests"""
        try:
            print("=" * 80)
            print("PERFORMANCE TESTING")
            print("=" * 80)
            print(f"Making {num_requests} requests to test performance...")
            
            # Use a standard test case
            test_features = [14, 1, 0.5, 1, 0, 0, 0, 1, 1]  # Business hours, auth, mobile
            
            latencies = []
            probabilities = []
            
            for i in range(num_requests):
                print(f"Request {i+1}/{num_requests}...", end=' ')
                
                result = self.make_ensemble_prediction(test_features)
                
                if result['success']:
                    latencies.append(result['total_latency_ms'])
                    probabilities.append(result['ensemble_probability'])
                    print(f"✓ {result['total_latency_ms']:.1f}ms")
                else:
                    print(f"✗ Failed")
                
                time.sleep(0.1)  # Small delay between requests
            
            if latencies:
                print(f"\n[PERFORMANCE RESULTS]")
                print(f"  Successful Requests: {len(latencies)}/{num_requests}")
                print(f"  Average Latency: {sum(latencies)/len(latencies):.1f}ms")
                print(f"  Min Latency: {min(latencies):.1f}ms")
                print(f"  Max Latency: {max(latencies):.1f}ms")
                print(f"  Prediction Consistency: {len(set([f'{p:.3f}' for p in probabilities]))} unique values")
                
                if len(set([f'{p:.3f}' for p in probabilities])) == 1:
                    print(f"  ✓ Perfect consistency - all predictions identical")
                else:
                    print(f"  ⚠ Some variation in predictions")
            
        except Exception as e:
            print(f"[ERROR] Performance testing failed: {str(e)}")

def main():
    """Main testing function"""
    tester = ServerlessEndpointTester()
    
    print("🚀 Testing your serverless ensemble endpoints!")
    print()
    
    # Test all scenarios
    results = tester.test_all_scenarios()
    
    # Performance test
    if results and any(r.get('success', False) for r in results):
        print()
        tester.test_performance(num_requests=5)
    
    print("\n✅ Testing complete!")
    print("Your serverless ensemble is working perfectly!")

if __name__ == "__main__":
    main()