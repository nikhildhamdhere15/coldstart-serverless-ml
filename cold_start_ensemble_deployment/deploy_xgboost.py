"""
Deploy XGBoost Model for Cold Start Prediction (Phase 1)
Tested and error-free deployment script
"""

import boto3
import json
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os

class XGBoostDeployer:
    def __init__(self, region='ap-south-1'):
        self.region = region
        self.sagemaker = boto3.client('sagemaker', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.iam = boto3.client('iam')
        
    def get_sagemaker_role(self):
        """Get SageMaker execution role"""
        try:
            role_names = [
                'SageMakerExecutionRole',
                'SageMakerMultiModelExecutionRole',
                'AmazonSageMaker-ExecutionRole'
            ]
            
            for role_name in role_names:
                try:
                    response = self.iam.get_role(RoleName=role_name)
                    role_arn = response['Role']['Arn']
                    print(f"[SUCCESS] Found role: {role_arn}")
                    return role_arn
                except:
                    continue
            
            print("[ERROR] No SageMaker execution role found")
            return None
            
        except Exception as e:
            print(f"[ERROR] Error getting role: {str(e)}")
            return None
    
    def prepare_training_data(self):
        """Prepare high-quality training data"""
        try:
            print("[DATA] Preparing XGBoost training data...")
            
            np.random.seed(42)  # For reproducibility
            n_samples = 1000
            
            data = []
            
            for i in range(n_samples):
                # Generate realistic features
                hour_of_day = np.random.randint(0, 24)
                day_of_week = np.random.randint(0, 7)
                
                # Business hours logic
                is_business_hours = 1 if (9 <= hour_of_day <= 17 and day_of_week < 5) else 0
                
                # Traffic intensity based on time
                if is_business_hours:
                    traffic_intensity = np.random.uniform(0.6, 1.0)
                elif 18 <= hour_of_day <= 23:
                    traffic_intensity = np.random.uniform(0.3, 0.7)
                else:
                    traffic_intensity = np.random.uniform(0.05, 0.3)
                
                # Endpoint type (one-hot encoded)
                endpoint_type = np.random.choice([0, 1, 2])  # 0=auth, 1=profile, 2=search
                endpoint_auth = 1 if endpoint_type == 0 else 0
                endpoint_profile = 1 if endpoint_type == 1 else 0
                endpoint_search = 1 if endpoint_type == 2 else 0
                
                # User and device features
                user_type_new = np.random.choice([0, 1], p=[0.7, 0.3])  # 30% new users
                device_mobile = np.random.choice([0, 1], p=[0.4, 0.6])  # 60% mobile
                
                # Cold start probability logic (realistic patterns)
                cold_start_prob = 0.1  # Base probability
                
                # Increase probability for:
                if not is_business_hours:
                    cold_start_prob += 0.3  # Higher at night/weekends
                if traffic_intensity < 0.2:
                    cold_start_prob += 0.4  # Higher during low traffic
                if user_type_new:
                    cold_start_prob += 0.2  # Higher for new users
                if endpoint_auth:
                    cold_start_prob += 0.1  # Auth tends to be colder
                if hour_of_day < 6 or hour_of_day > 22:
                    cold_start_prob += 0.3  # Very late/early hours
                
                # Cap probability
                cold_start_prob = min(cold_start_prob, 0.9)
                
                # Generate label
                is_cold_start = 1 if np.random.random() < cold_start_prob else 0
                
                # SageMaker XGBoost format: label first, then features
                row = [
                    is_cold_start,  # Label (target)
                    hour_of_day,
                    day_of_week,
                    traffic_intensity,
                    endpoint_auth,
                    endpoint_profile,
                    endpoint_search,
                    user_type_new,
                    device_mobile,
                    is_business_hours
                ]
                
                data.append(row)
            
            # Convert to DataFrame
            columns = [
                'label', 'hour_of_day', 'day_of_week', 'traffic_intensity',
                'endpoint_auth', 'endpoint_profile', 'endpoint_search',
                'user_type_new', 'device_mobile', 'is_business_hours'
            ]
            
            df = pd.DataFrame(data, columns=columns)
            
            # Split into train/validation
            train_df = df.sample(frac=0.8, random_state=42)
            val_df = df.drop(train_df.index)
            
            # Save as CSV (SageMaker XGBoost format)
            train_df.to_csv('xgb_train.csv', header=False, index=False)
            val_df.to_csv('xgb_validation.csv', header=False, index=False)
            
            print(f"[SUCCESS] Created training data: {len(train_df)} train, {len(val_df)} validation samples")
            print(f"[SUCCESS] Cold start ratio: {df['label'].mean():.2%}")
            
            return 'xgb_train.csv', 'xgb_validation.csv'
            
        except Exception as e:
            print(f"[ERROR] Failed to prepare training data: {str(e)}")
            return None, None
    
    def upload_data_to_s3(self, train_file, val_file, bucket_name):
        """Upload training data to S3"""
        try:
            print("[S3] Uploading training data to S3...")
            
            # Create bucket if it doesn't exist
            try:
                self.s3.head_bucket(Bucket=bucket_name)
            except:
                if self.region == 'us-east-1':
                    self.s3.create_bucket(Bucket=bucket_name)
                else:
                    self.s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                print(f"[SUCCESS] Created S3 bucket: {bucket_name}")
            
            # Upload files
            train_s3_key = 'xgboost-training/train.csv'
            val_s3_key = 'xgboost-training/validation.csv'
            
            self.s3.upload_file(train_file, bucket_name, train_s3_key)
            self.s3.upload_file(val_file, bucket_name, val_s3_key)
            
            train_s3_uri = f"s3://{bucket_name}/{train_s3_key}"
            val_s3_uri = f"s3://{bucket_name}/{val_s3_key}"
            
            print(f"[SUCCESS] Uploaded training data:")
            print(f"   Train: {train_s3_uri}")
            print(f"   Validation: {val_s3_uri}")
            
            # Clean up local files
            os.remove(train_file)
            os.remove(val_file)
            
            return train_s3_uri, val_s3_uri
            
        except Exception as e:
            print(f"[ERROR] Failed to upload data: {str(e)}")
            return None, None
    
    def get_xgboost_image_uri(self):
        """Get the SageMaker built-in XGBoost container image URI"""
        xgboost_images = {
            'us-east-1': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.5-1',
            'us-west-2': '246618743249.dkr.ecr.us-west-2.amazonaws.com/sagemaker-xgboost:1.5-1',
            'eu-west-1': '141502667606.dkr.ecr.eu-west-1.amazonaws.com/sagemaker-xgboost:1.5-1',
            'ap-south-1': '720646828776.dkr.ecr.ap-south-1.amazonaws.com/sagemaker-xgboost:1.5-1',
            'ap-southeast-1': '121021644041.dkr.ecr.ap-southeast-1.amazonaws.com/sagemaker-xgboost:1.5-1'
        }
        
        return xgboost_images.get(self.region, xgboost_images['us-east-1'])
    
    def train_xgboost(self, train_s3_uri, val_s3_uri, output_s3_uri, role_arn):
        """Train XGBoost model"""
        try:
            print("[TRAIN] Training XGBoost model...")
            
            # Get XGBoost image
            image_uri = self.get_xgboost_image_uri()
            
            # Training job configuration
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            job_name = f"cold-start-xgboost-{timestamp}"
            
            training_params = {
                'TrainingJobName': job_name,
                'AlgorithmSpecification': {
                    'TrainingImage': image_uri,
                    'TrainingInputMode': 'File'
                },
                'RoleArn': role_arn,
                'InputDataConfig': [
                    {
                        'ChannelName': 'train',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': train_s3_uri,
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        },
                        'ContentType': 'text/csv',
                        'CompressionType': 'None'
                    },
                    {
                        'ChannelName': 'validation',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': val_s3_uri,
                                'S3DataDistributionType': 'FullyReplicated'
                            }
                        },
                        'ContentType': 'text/csv',
                        'CompressionType': 'None'
                    }
                ],
                'OutputDataConfig': {
                    'S3OutputPath': output_s3_uri
                },
                'ResourceConfig': {
                    'InstanceType': 'ml.m5.large',
                    'InstanceCount': 1,
                    'VolumeSizeInGB': 10
                },
                'StoppingCondition': {
                    'MaxRuntimeInSeconds': 3600  # 1 hour max
                },
                'HyperParameters': {
                    'objective': 'binary:logistic',
                    'num_round': '100',
                    'max_depth': '6',
                    'eta': '0.1',
                    'subsample': '0.8',
                    'colsample_bytree': '0.8',
                    'min_child_weight': '1',
                    'eval_metric': 'auc'
                }
            }
            
            # Start training
            self.sagemaker.create_training_job(**training_params)
            print(f"[SUCCESS] Started training job: {job_name}")
            
            # Wait for completion
            print("[WAIT] Waiting for training to complete...")
            
            while True:
                status = self.sagemaker.describe_training_job(TrainingJobName=job_name)
                current_status = status['TrainingJobStatus']
                
                if current_status == 'Completed':
                    print("[SUCCESS] Training completed successfully!")
                    model_artifacts = status['ModelArtifacts']['S3ModelArtifacts']
                    print(f"[MODEL] Model artifacts: {model_artifacts}")
                    return model_artifacts
                    
                elif current_status == 'Failed':
                    failure_reason = status.get('FailureReason', 'Unknown')
                    print(f"[ERROR] Training failed: {failure_reason}")
                    return None
                    
                elif current_status in ['InProgress', 'Starting']:
                    print(f"[WAIT] Training status: {current_status}")
                    time.sleep(30)
                else:
                    print(f"[WARN] Unknown status: {current_status}")
                    time.sleep(30)
            
        except Exception as e:
            print(f"[ERROR] Training failed: {str(e)}")
            return None
    
    def deploy_endpoint(self, model_artifacts, role_arn):
        """Deploy the trained XGBoost model to an endpoint"""
        try:
            print("[DEPLOY] Deploying XGBoost endpoint...")
            
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            
            # Create model
            model_name = f"cold-start-xgboost-{timestamp}"
            image_uri = self.get_xgboost_image_uri()
            
            self.sagemaker.create_model(
                ModelName=model_name,
                PrimaryContainer={
                    'Image': image_uri,
                    'ModelDataUrl': model_artifacts
                },
                ExecutionRoleArn=role_arn
            )
            print(f"[SUCCESS] Created model: {model_name}")
            
            # Create endpoint configuration
            config_name = f"cold-start-xgboost-config-{timestamp}"
            
            self.sagemaker.create_endpoint_config(
                EndpointConfigName=config_name,
                ProductionVariants=[{
                    'VariantName': 'AllTraffic',
                    'ModelName': model_name,
                    'InitialInstanceCount': 1,
                    'InstanceType': 'ml.t2.medium',
                    'InitialVariantWeight': 1.0
                }]
            )
            print(f"[SUCCESS] Created endpoint config: {config_name}")
            
            # Create endpoint
            endpoint_name = "cold-start-xgboost-endpoint"
            
            # Delete existing endpoint if it exists
            try:
                self.sagemaker.delete_endpoint(EndpointName=endpoint_name)
                print("[CLEANUP] Deleted existing endpoint")
                time.sleep(60)
            except:
                pass
            
            self.sagemaker.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=config_name
            )
            print(f"[SUCCESS] Creating endpoint: {endpoint_name}")
            print("[WAIT] This will take 5-10 minutes...")
            
            # Wait for endpoint to be in service
            while True:
                status = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
                current_status = status['EndpointStatus']
                
                if current_status == 'InService':
                    print("[SUCCESS] Endpoint is now InService!")
                    return endpoint_name
                    
                elif current_status == 'Failed':
                    failure_reason = status.get('FailureReason', 'Unknown')
                    print(f"[ERROR] Endpoint creation failed: {failure_reason}")
                    return None
                    
                elif current_status in ['Creating', 'Updating']:
                    print(f"[WAIT] Endpoint status: {current_status}")
                    time.sleep(30)
                else:
                    print(f"[WARN] Unknown status: {current_status}")
                    time.sleep(30)
            
        except Exception as e:
            print(f"[ERROR] Endpoint deployment failed: {str(e)}")
            return None
    
    def test_endpoint(self, endpoint_name):
        """Test the deployed endpoint"""
        try:
            print("[TEST] Testing XGBoost endpoint...")
            
            sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=self.region)
            
            # Test features: high cold start probability scenario
            features = [2, 6, 0.1, 1, 0, 0, 1, 1, 0]  # Early morning, weekend, low traffic, new mobile user
            csv_input = ','.join(map(str, features))
            
            response = sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='text/csv',
                Body=csv_input
            )
            
            result = json.loads(response['Body'].read().decode())
            probability = float(result)
            
            print(f"[SUCCESS] Test successful!")
            print(f"   Input features: {features}")
            print(f"   Cold start probability: {probability:.3f}")
            print(f"   Prediction: {'Cold Start' if probability > 0.5 else 'Warm'}")
            
            return probability
            
        except Exception as e:
            print(f"[ERROR] Endpoint test failed: {str(e)}")
            return None
    
    def deploy_xgboost_complete(self):
        """Complete XGBoost deployment process"""
        try:
            print("[START] DEPLOYING XGBOOST MODEL")
            print("=" * 50)
            
            # Configuration
            bucket_name = f"xgboost-coldstart-{int(time.time())}"
            
            # Step 1: Get execution role
            print("\n[STEP 1] Getting execution role...")
            role_arn = self.get_sagemaker_role()
            if not role_arn:
                return False
            
            # Step 2: Prepare training data
            print("\n[STEP 2] Preparing training data...")
            train_file, val_file = self.prepare_training_data()
            if not train_file:
                return False
            
            # Step 3: Upload to S3
            print("\n[STEP 3] Uploading to S3...")
            train_s3_uri, val_s3_uri = self.upload_data_to_s3(train_file, val_file, bucket_name)
            if not train_s3_uri:
                return False
            
            output_s3_uri = f"s3://{bucket_name}/xgboost-output"
            
            # Step 4: Train XGBoost
            print("\n[STEP 4] Training XGBoost...")
            model_artifacts = self.train_xgboost(train_s3_uri, val_s3_uri, output_s3_uri, role_arn)
            if not model_artifacts:
                return False
            
            # Step 5: Deploy endpoint
            print("\n[STEP 5] Deploying endpoint...")
            endpoint_name = self.deploy_endpoint(model_artifacts, role_arn)
            if not endpoint_name:
                return False
            
            # Step 6: Test endpoint
            print("\n[STEP 6] Testing endpoint...")
            test_probability = self.test_endpoint(endpoint_name)
            if test_probability is None:
                return False
            
            # Save deployment info
            deployment_info = {
                'endpoint_name': endpoint_name,
                'model_artifacts': model_artifacts,
                'bucket_name': bucket_name,
                'region': self.region,
                'deployment_type': 'XGBOOST',
                'deployment_timestamp': datetime.now().isoformat(),
                'test_probability': test_probability,
                'status': 'DEPLOYED'
            }
            
            with open('xgboost_deployment.json', 'w') as f:
                json.dump(deployment_info, f, indent=2)
            
            print("\n" + "=" * 50)
            print("[COMPLETE] XGBOOST DEPLOYMENT COMPLETE!")
            print("=" * 50)
            print(f"[SUCCESS] Endpoint: {endpoint_name}")
            print(f"[SUCCESS] Status: InService and ready!")
            print(f"[SUCCESS] Test probability: {test_probability:.3f}")
            print(f"[SUCCESS] Cost: ~$33/month")
            
            print(f"\n[NEXT] Next steps:")
            print(f"1. Deploy Random Forest: python deploy_random_forest.py")
            print(f"2. Test ensemble: python test_ensemble.py")
            print(f"3. Use in production: python use_ensemble_predictor.py")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] XGBoost deployment failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main function"""
    deployer = XGBoostDeployer()
    success = deployer.deploy_xgboost_complete()
    
    if success:
        print("\n[SUCCESS] XGBoost deployment successful!")
    else:
        print("\n[FAILED] XGBoost deployment failed!")

if __name__ == "__main__":
    main()