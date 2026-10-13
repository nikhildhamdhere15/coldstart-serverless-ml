# COLDSTART — Project Test Suite

## How to Run Tests

From the project root directory:

```bash
# Run a single test
python project_testing/UT1_data_collection.py

# Run all tests at once
python project_testing/run_all_tests.py
```

## Test Files

| File | ID | Type | What it Tests |
|------|----|------|---------------|
| UT1_data_collection.py | UT1 | Unit | S3 bucket, JSON record structure, ml_label |
| UT2_preprocessing.py | UT2 | Unit | Feature vector shape, one-hot encoding, ranges |
| UT3_prediction.py | UT3 | Unit | Model output, CBW gate, priority assignment |
| IT1_api_to_lambda.py | IT1 | Integration | Traffic generator → S3 write/read |
| IT2_lambda_to_dynamodb.py | IT2 | Integration | ETL Lambda → DynamoDB feature storage |
| IT3_ml_model_integration.py | IT3 | Integration | DataAggregator Lambda → ML predictions |
| ST1_end_to_end_workflow.py | ST1 | System | Full pipeline DynamoDB→ML→Warmer→CloudWatch |
| ST2_cold_start_prediction.py | ST2 | System | Prediction accuracy on known scenarios |
| ST3_pre_warming_trigger.py | ST3 | System | IntelligentLambdaWarmer invocation + logs |
| PT1_response_time.py | PT1 | Performance | Single/100 prediction latency < 50 ms |
| PT2_load_handling.py | PT2 | Performance | 500 sequential + 10-thread concurrent load |
| UAT1_user_interaction.py | UAT1 | UAT | Dashboard backend connectivity |
| UAT2_system_usability.py | UAT2 | UAT | Config, model files, all AWS services |
