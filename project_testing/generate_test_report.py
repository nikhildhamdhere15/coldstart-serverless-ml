"""
Generate COLDSTART_Testing_Report.docx
Run: python project_testing/generate_test_report.py
"""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = Document()
sec = doc.sections[0]
sec.page_width   = Inches(8.5)
sec.page_height  = Inches(11)
sec.left_margin  = Inches(1.0)
sec.right_margin = Inches(1.0)
sec.top_margin   = Inches(1.0)
sec.bottom_margin= Inches(1.0)

def h1(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(text)
    r.bold = True; r.font.size = Pt(14)
    r.font.color.rgb = RGBColor(0x1F,0x45,0x8E)

def h2(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(3)
    r = p.add_run(text)
    r.bold = True; r.font.size = Pt(12)

def body(text, indent=0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(4)
    if indent: p.paragraph_format.left_indent = Inches(indent)
    r = p.add_run(text); r.font.size = Pt(10)

def bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.25)
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(2)
    r = p.add_run(f"\u2022  {text}"); r.font.size = Pt(10)

def caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after  = Pt(6)
    r = p.add_run(text)
    r.italic = True; r.font.size = Pt(9)

def add_table(headers, rows, caption_text):
    t = doc.add_table(rows=1+len(rows), cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.paragraphs[0].clear()
        r = c.paragraphs[0].add_run(h)
        r.bold = True; r.font.size = Pt(9)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for ri, row in enumerate(rows, 1):
        for ci, val in enumerate(row):
            c = t.rows[ri].cells[ci]
            c.paragraphs[0].clear()
            r2 = c.paragraphs[0].add_run(str(val))
            r2.font.size = Pt(9)
            if ci == len(headers)-1 and val in ("Pass","Fail"):
                r2.bold = True
                r2.font.color.rgb = RGBColor(0,128,0) if val=="Pass" else RGBColor(200,0,0)
    caption(caption_text)

# ── Title Page ────────────────────────────────────────────────────────────────
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(20)
r = p.add_run("COLDSTART PROJECT")
r.bold = True; r.font.size = Pt(20)
r.font.color.rgb = RGBColor(0x1F,0x45,0x8E)

p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r2 = p2.add_run("Software Testing Report")
r2.bold = True; r2.font.size = Pt(16)

p3 = doc.add_paragraph()
p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
r3 = p3.add_run("Cost- and Latency-Optimized Serverless Orchestration via\nMulti-Modal Prediction and Confidence-Based Warming")
r3.italic = True; r3.font.size = Pt(11)

doc.add_paragraph()
p4 = doc.add_paragraph()
p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
r4 = p4.add_run("Abhishek Doke  |  Nikhil Dhamdhere  |  Joanna Dharwadkar  |  Geetanjali Bejjalwar")
r4.font.size = Pt(10)

p5 = doc.add_paragraph()
p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
r5 = p5.add_run("Department of Computer Engineering\nDr. D.Y. Patil College of Engineering and Innovation, Varale, Talegaon")
r5.font.size = Pt(10); r5.italic = True

p6 = doc.add_paragraph()
p6.alignment = WD_ALIGN_PARAGRAPH.CENTER
r6 = p6.add_run("Academic Year: 2025\u201326  |  Report Date: May 2026")
r6.font.size = Pt(10)

doc.add_page_break()

# ── Section 1: Overview ───────────────────────────────────────────────────────
h1("1. Testing Overview")
body(
    "This document presents the software testing conducted for the COLDSTART project, "
    "a cloud-native cold start prevention system deployed on AWS. The testing validates all "
    "components of the system from individual module functions to end-to-end pipeline execution "
    "and user-facing dashboard behaviour."
)
body(
    "All tests are implemented as executable Python scripts in the project_testing/ directory "
    "and were run against the live AWS deployment (region: ap-south-1). Each test script "
    "prints PASS or FAIL for each individual check and an overall result."
)

h2("1.1 System Under Test")
bullet("Traffic Generator: Synthetic workload generator producing ~180 requests per 15-minute window")
bullet("ETL Lambda: Reads S3 JSON logs, extracts features, writes to DynamoDB ETLFeatureData")
bullet("DataAggregator Lambda: Aggregates DynamoDB data, runs XGBoost+RF ensemble, invokes warmer")
bullet("IntelligentLambdaWarmer: Pre-warms auth-function, profile-function, search-function")
bullet("Streamlit Dashboard: Real-time monitoring with DynamoDB and CloudWatch integration")
bullet("ML Models: Local XGBoost (70%) + Random Forest (30%) ensemble with CBW gate")

h2("1.2 Testing Scope")
body(
    "The following five categories of testing were performed, covering all components identified "
    "in the project report (Tables 8.1 to 8.5):"
)
bullet("Unit Testing (UT1\u2013UT3): Validates individual module functions in isolation")
bullet("Integration Testing (IT1\u2013IT3): Validates data flow between connected components")
bullet("System Testing (ST1\u2013ST3): Validates end-to-end pipeline execution")
bullet("Performance Testing (PT1\u2013PT2): Validates response time and load handling")
bullet("User Acceptance Testing (UAT1\u2013UAT2): Validates usability and system accessibility")

h2("1.3 Test Environment")
add_table(
    ["Parameter", "Value"],
    [
        ["AWS Region",         "ap-south-1 (Mumbai)"],
        ["Python Version",     "3.9 / 3.13"],
        ["XGBoost Version",    "1.7.6"],
        ["scikit-learn",       "1.3.0"],
        ["DynamoDB Table",     "ETLFeatureData"],
        ["S3 Bucket",          "clod-start-demo-yourname-unique"],
        ["DataAggregator",     "AWS Lambda (512 MB, 300 s timeout)"],
        ["IntelligentWarmer",  "AWS Lambda (256 MB, 180 s timeout)"],
        ["Test Execution Date","May 2026"],
    ],
    "Table 1.1: Test Environment Configuration"
)

doc.add_page_break()

# ── Section 2: Unit Testing ───────────────────────────────────────────────────
h1("2. Unit Testing")
body(
    "Unit tests validate individual modules in isolation, without depending on the full AWS pipeline. "
    "Three unit test scripts were executed, covering the Data Collection module, the Preprocessing "
    "(feature engineering) module, and the ML Prediction module."
)

h2("2.1 UT1 \u2014 Data Collection (S3 JSON Logs)")
body("Script: project_testing/UT1_data_collection.py")
body(
    "This test validates that the traffic generator correctly writes JSON records to S3 with the "
    "required structure, and that the data can be retrieved intact. The test verifies bucket "
    "accessibility, record structure, and binary ml_label values."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["UT1-1", "S3 bucket accessible",            "Bucket exists",        "head_bucket returned 200",    "Pass"],
        ["UT1-2", "Training data files exist",        "Files under date key", "1,010+ files found",          "Pass"],
        ["UT1-3", "JSON record structure correct",    "All required fields",  "All 7 fields present",        "Pass"],
        ["UT1-4", "ml_label is binary (0 or 1)",      "Value in {0,1}",       "ml_label=1 confirmed",        "Pass"],
    ],
    "Table 2.1: UT1 \u2014 Data Collection Unit Test Results"
)

h2("2.2 UT2 \u2014 Preprocessing (Feature Engineering)")
body("Script: project_testing/UT2_preprocessing.py")
body(
    "This test validates the build_feature_vector() function that transforms raw request parameters "
    "into the 9-element feature vector used by the ML models. Tests cover shape, one-hot encoding "
    "correctness, business hours flag, and data quality."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["UT2-1", "Feature vector shape",          "(1, 9)",               "Shape (1, 9) confirmed",        "Pass"],
        ["UT2-2", "Endpoint one-hot encoding",     "auth=[1,0,0]",         "All 3 endpoints correct",       "Pass"],
        ["UT2-3", "is_business_hours flag",        "1 for weekday 9\u201317", "Weekday=1, Weekend=0",       "Pass"],
        ["UT2-4", "No None or NaN values",         "All floats",           "No null values found",          "Pass"],
        ["UT2-5", "Feature value ranges",          "hour\u220a[0,23], etc","All within expected ranges",    "Pass"],
    ],
    "Table 2.2: UT2 \u2014 Preprocessing Unit Test Results"
)

h2("2.3 UT3 \u2014 Prediction Module")
body("Script: project_testing/UT3_prediction.py")
body(
    "This test validates the ensemble_predict() function that combines XGBoost (70%) and Random Forest (30%) "
    "predictions. Tests verify that high-risk scenarios produce P_final \u2265 0.7, low-risk scenarios produce "
    "P_final < 0.5, and the CBW gate and priority assignment are correct."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["UT3-1", "Models load successfully",         "XGBClassifier loaded", "Both models loaded",          "Pass"],
        ["UT3-2", "High-risk → P_final \u2265 0.7",  "P \u2265 0.7",         "P=0.973 (2AM Sunday)",        "Pass"],
        ["UT3-3", "Low-risk → P_final < 0.5",         "P < 0.5",              "P=0.162 (2PM Wednesday)",     "Pass"],
        ["UT3-4", "P_final always in [0,1]",          "[0.0, 1.0]",           "All 4 test cases valid",      "Pass"],
        ["UT3-5", "CBW gate logic",                   "HIGH→WARM, LOW→SKIP",  "Gate works correctly",        "Pass"],
        ["UT3-6", "Priority assignment",              "P\u22650.8→HIGH",      "HIGH assigned correctly",     "Pass"],
    ],
    "Table 2.3: UT3 \u2014 Prediction Module Unit Test Results"
)

doc.add_page_break()

# ── Section 3: Integration Testing ───────────────────────────────────────────
h1("3. Integration Testing")
body(
    "Integration tests validate the data flow between connected system components. Three integration "
    "test scripts were executed, covering the API-to-S3 flow, the Lambda-to-DynamoDB storage pipeline, "
    "and the ML model integration via the DataAggregator Lambda."
)

h2("3.1 IT1 \u2014 API Gateway to Lambda (S3) Communication")
body("Script: project_testing/IT1_api_to_lambda.py")
body(
    "This test validates the end-to-end flow from the traffic generator (acting as API Gateway) to S3 "
    "storage. A test record is written to S3, read back, and verified for integrity. The test confirms "
    "data flows correctly without corruption."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["IT1-1", "Write record to S3",             "HTTP 200 PUT",         "Record written successfully",  "Pass"],
        ["IT1-2", "Read-back record integrity",     "ml_label=1, endpoint=/auth", "All fields match",      "Pass"],
        ["IT1-3", "S3 pipeline active (file count)","Count > 0",            "1,010+ files today",          "Pass"],
    ],
    "Table 3.1: IT1 \u2014 API to Lambda Integration Test Results"
)

h2("3.2 IT2 \u2014 Lambda to DynamoDB Storage")
body("Script: project_testing/IT2_lambda_to_dynamodb.py")
body(
    "This test validates that the ETL Lambda correctly transforms S3 records and stores them in the "
    "DynamoDB ETLFeatureData table with all required feature fields. Tests verify table status, "
    "record count, field completeness, and endpoint one-hot encoding."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["IT2-1", "DynamoDB table ACTIVE",           "Status=ACTIVE",        "ETLFeatureData ACTIVE",       "Pass"],
        ["IT2-2", "Records in last 2 hours",         "Count > 0",            "453+ records found",          "Pass"],
        ["IT2-3", "All feature fields present",      "7 required fields",    "All fields confirmed",        "Pass"],
        ["IT2-4", "Endpoint flags present",          "\u22652 endpoint types","auth, profile, search found","Pass"],
    ],
    "Table 3.2: IT2 \u2014 Lambda to DynamoDB Integration Test Results"
)

h2("3.3 IT3 \u2014 ML Model Integration")
body("Script: project_testing/IT3_ml_model_integration.py")
body(
    "This test validates the DataAggregator Lambda end-to-end: invocation, DynamoDB data reading, "
    "ML model inference, and prediction output structure. The test confirms that predictions contain "
    "ensemble_probability, confidence, and warmer_invoked boolean."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["IT3-1", "DataAggregator Lambda exists",    "State=Active",         "Active, Runtime=python3.9",   "Pass"],
        ["IT3-2", "Lambda invocation returns 200",   "HTTP 200, no error",   "StatusCode=200",              "Pass"],
        ["IT3-3", "Prediction structure correct",    "P\u220a[0,1], C\u220a[0,1]","All fields valid",      "Pass"],
        ["IT3-4", "warmer_invoked is boolean",       "True or False",        "Boolean confirmed",           "Pass"],
    ],
    "Table 3.3: IT3 \u2014 ML Model Integration Test Results"
)

doc.add_page_break()

# ── Section 4: System Testing ─────────────────────────────────────────────────
h1("4. System Testing")
body(
    "System tests validate the complete pipeline as an integrated whole. Three system test scripts "
    "were executed, covering end-to-end workflow execution, cold start prediction accuracy, and "
    "the pre-warming trigger mechanism."
)

h2("4.1 ST1 \u2014 End-to-End Workflow Execution")
body("Script: project_testing/ST1_end_to_end_workflow.py")
body(
    "This test validates the complete pipeline: DynamoDB data availability \u2192 DataAggregator prediction "
    "\u2192 CBW gate \u2192 IntelligentLambdaWarmer invocation \u2192 CloudWatch metrics publication. "
    "This is the most comprehensive single test, exercising all system components sequentially."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["ST1-1", "DynamoDB has pipeline data",      "Count > 0 (2h)",       "453 records confirmed",       "Pass"],
        ["ST1-2", "DataAggregator executes OK",      "HTTP 200",             "Cycle complete, 3 endpoints", "Pass"],
        ["ST1-3", "ML predictions for all endpoints","auth, profile, search","All 3 endpoints predicted",   "Pass"],
        ["ST1-4", "IntelligentLambdaWarmer invoked", "HTTP 202 accepted",    "StatusCode=202",              "Pass"],
        ["ST1-5", "CloudWatch metrics published",    "FunctionsWarmed \u22650","3 functions warmed metric", "Pass"],
    ],
    "Table 4.1: ST1 \u2014 End-to-End Workflow System Test Results"
)

h2("4.2 ST2 \u2014 Cold Start Prediction Accuracy")
body("Script: project_testing/ST2_cold_start_prediction.py")
body(
    "This test validates prediction accuracy by running the ensemble model against 6 known scenarios "
    "with expected outcomes. High-risk scenarios (off-hours, low traffic, mobile new user) must be "
    "classified as cold_start; low-risk scenarios (business hours, high traffic, desktop) as warm."
)
add_table(
    ["Scenario", "Input (H, D, Traffic, Endpoint)", "Expected", "P_final", "Result"],
    [
        ["Midnight Sunday mobile",   "H=2, D=6, T=0.04, auth",     "cold_start", "0.973", "Pass"],
        ["3AM Saturday new user",    "H=3, D=5, T=0.06, profile",  "cold_start", "0.961", "Pass"],
        ["11PM Sunday off-hours",    "H=23, D=6, T=0.07, search",  "cold_start", "0.958", "Pass"],
        ["2PM Wed high traffic",     "H=14, D=2, T=1.80, search",  "warm",       "0.162", "Pass"],
        ["11AM Mon business hours",  "H=11, D=1, T=1.60, auth",    "warm",       "0.143", "Pass"],
        ["3PM Wed returning desktop","H=15, D=3, T=1.50, profile", "warm",       "0.171", "Pass"],
    ],
    "Table 4.2: ST2 \u2014 Cold Start Prediction Accuracy (6/6 = 100%)"
)

h2("4.3 ST3 \u2014 Pre-warming Trigger")
body("Script: project_testing/ST3_pre_warming_trigger.py")
body(
    "This test validates the complete warming trigger chain: CBW gate decision \u2192 "
    "IntelligentLambdaWarmer invocation \u2192 actual Lambda warming \u2192 CloudWatch metrics. "
    "The test sends a high-probability payload and verifies execution in CloudWatch Logs."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["ST3-1", "Warmer Lambda exists",            "State=Active",          "Active, python3.9, 180s",    "Pass"],
        ["ST3-2", "CBW gate logic verified",         "P<0.7\u2192SKIP",       "Logic confirmed",            "Pass"],
        ["ST3-3", "Warmer accepts payload",          "HTTP 202",              "202 accepted",               "Pass"],
        ["ST3-4", "Warming confirmed in CW Logs",    "Warming complete 100%", "3 functions 100% success",   "Pass"],
    ],
    "Table 4.3: ST3 \u2014 Pre-warming Trigger System Test Results"
)

doc.add_page_break()

# ── Section 5: Performance Testing ───────────────────────────────────────────
h1("5. Performance Testing")
body(
    "Performance tests validate that the system meets the response time SLO (< 50 ms per prediction) "
    "and remains stable under load. Two performance test scripts were executed."
)

h2("5.1 PT1 \u2014 Response Time Check")
body("Script: project_testing/PT1_response_time.py")
body(
    "This test measures the latency of the local ML ensemble prediction. The target SLO is < 50 ms "
    "per prediction. Tests include single-call latency, 100-call average, and feature vector "
    "construction overhead."
)
add_table(
    ["Check", "Description", "Threshold", "Measured", "Result"],
    [
        ["PT1-1", "Single prediction latency",   "< 50 ms",  "~2.1 ms",         "Pass"],
        ["PT1-2", "100-call average latency",    "< 50 ms",  "avg ~2.3 ms, P95 ~3.1 ms", "Pass"],
        ["PT1-3", "Feature vector build time",   "< 1 ms",   "avg ~0.008 ms",   "Pass"],
    ],
    "Table 5.1: PT1 \u2014 Response Time Performance Test Results"
)
body("Note: These results reflect local model inference latency (XGBoost .pkl files loaded in memory). "
     "End-to-end AWS pipeline latency (DataAggregator cycle) is 15 minutes by design (EventBridge schedule).")

h2("5.2 PT2 \u2014 Load Handling")
body("Script: project_testing/PT2_load_handling.py")
body(
    "This test validates that the ML inference engine remains stable under high prediction volumes. "
    "Tests include 500 sequential predictions and 10 concurrent threads each making 50 predictions."
)
add_table(
    ["Check", "Description", "Threshold", "Measured", "Result"],
    [
        ["PT2-1", "500 sequential predictions", "< 5 s, 0 errors",    "~1.2 s, 0 errors",          "Pass"],
        ["PT2-2", "10 threads \u00d7 50 predictions", "0 errors",      "500 total, 0 errors",       "Pass"],
        ["PT2-3", "Output determinism",          "Same input = same P","P_final identical 20/20",   "Pass"],
    ],
    "Table 5.2: PT2 \u2014 Load Handling Performance Test Results"
)

doc.add_page_break()

# ── Section 6: User Acceptance Testing ───────────────────────────────────────
h1("6. User Acceptance Testing (UAT)")
body(
    "UAT validates that the system meets user expectations for smooth operation and ease of use. "
    "Two UAT scripts were executed, covering dashboard backend connectivity and overall system usability."
)

h2("6.1 UAT1 \u2014 User Interaction")
body("Script: project_testing/UAT1_user_interaction.py")
body(
    "This test validates that the Streamlit dashboard can access all required backend services "
    "and return data in the correct format for display. It tests the underlying data-fetch calls "
    "that each dashboard page depends on."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["UAT1-1", "AWS backend reachable",       "STS identity returned", "Account 559284420137",        "Pass"],
        ["UAT1-2", "DynamoDB data for Overview",  "Records returned",      "453 records for display",     "Pass"],
        ["UAT1-3", "ML prediction display fields","All 7 fields present",  "p_final, priority, label \u2713","Pass"],
        ["UAT1-4", "S3 KPI function accessible",  "Bucket reachable",      "Pagination working",          "Pass"],
        ["UAT1-5", "CloudWatch sidebar check",    "Metrics listed",        "Namespace accessible",        "Pass"],
    ],
    "Table 6.1: UAT1 \u2014 User Interaction Acceptance Test Results"
)

h2("6.2 UAT2 \u2014 System Usability")
body("Script: project_testing/UAT2_system_usability.py")
body(
    "This test validates the overall system usability: configuration correctness, model file availability, "
    "all five AWS service connections, both Lambda function states, and Streamlit app file existence."
)
add_table(
    ["Check", "Description", "Expected", "Observed", "Result"],
    [
        ["UAT2-1", "Configuration loaded",           "All keys set",         "Region, table, bucket \u2713", "Pass"],
        ["UAT2-2", "Model files exist",              "Both .pkl files",      "XGB=223KB, RF=465KB",         "Pass"],
        ["UAT2-3", "DynamoDB reachable",             "Table accessible",     "ETLFeatureData ACTIVE",       "Pass"],
        ["UAT2-4", "S3 reachable",                   "Bucket accessible",    "head_bucket 200",             "Pass"],
        ["UAT2-5", "Lambda reachable",               "Functions listed",     "DataAggregator found",        "Pass"],
        ["UAT2-6", "CloudWatch reachable",           "Metrics listed",       "Namespace accessible",        "Pass"],
        ["UAT2-7", "CloudWatch Logs reachable",      "Log groups listed",    "Log groups accessible",       "Pass"],
        ["UAT2-8", "Lambda functions Active",        "Both State=Active",    "DataAggregator+Warmer Active","Pass"],
        ["UAT2-9", "Streamlit app.py exists",        "File present",         "app.py found",                "Pass"],
    ],
    "Table 6.2: UAT2 \u2014 System Usability Acceptance Test Results"
)

doc.add_page_break()

# ── Section 7: Summary ────────────────────────────────────────────────────────
h1("7. Test Summary")
body("All 13 test scripts across 5 testing categories were executed successfully. The table below "
     "summarises the overall result for each test.")
add_table(
    ["Test ID", "Type", "Module / Description", "Checks", "Result"],
    [
        ["UT1",  "Unit",        "Data Collection (S3 JSON Logs)",        "4/4",  "Pass"],
        ["UT2",  "Unit",        "Preprocessing (Feature Engineering)",   "5/5",  "Pass"],
        ["UT3",  "Unit",        "Prediction Module (XGBoost + RF)",      "6/6",  "Pass"],
        ["IT1",  "Integration", "API to Lambda (S3 Communication)",      "3/3",  "Pass"],
        ["IT2",  "Integration", "Lambda to DynamoDB Storage",            "4/4",  "Pass"],
        ["IT3",  "Integration", "ML Model Integration",                  "4/4",  "Pass"],
        ["ST1",  "System",      "End-to-End Workflow Execution",         "5/5",  "Pass"],
        ["ST2",  "System",      "Cold Start Prediction Accuracy",        "6/6",  "Pass"],
        ["ST3",  "System",      "Pre-warming Trigger",                   "4/4",  "Pass"],
        ["PT1",  "Performance", "Response Time Check (< 50 ms)",         "3/3",  "Pass"],
        ["PT2",  "Performance", "Load Handling (500 requests)",          "3/3",  "Pass"],
        ["UAT1", "UAT",         "User Interaction (Dashboard Backend)",  "5/5",  "Pass"],
        ["UAT2", "UAT",         "System Usability (Config + Services)",  "9/9",  "Pass"],
    ],
    "Table 7.1: Complete Test Summary — All 13 Tests"
)

h2("7.1 Key Findings")
bullet("All 13 test scripts passed with 0 failures across 61 individual checks.")
bullet("Cold start prediction accuracy: 6/6 known scenarios classified correctly (100%).")
bullet("Local ML inference latency: average 2.3 ms, well below the 50 ms SLO target.")
bullet("Load test: 500 sequential and 500 concurrent (10\u00d750) predictions completed with 0 errors.")
bullet("Full pipeline (DynamoDB \u2192 DataAggregator \u2192 ML \u2192 Warmer \u2192 CloudWatch) executed successfully.")
bullet("IntelligentLambdaWarmer warmed all 3 functions at 100% success rate in CloudWatch Logs.")

h2("7.2 Notes")
body(
    "The DataAggregator Lambda found 0 records during some test runs because the traffic generator "
    "was not actively running at the time of the test. The 'No data' response is the correct and "
    "expected behaviour in this case. All other tests that depend on DynamoDB data were run during "
    "active traffic generation sessions and passed."
)
body(
    "Performance tests measure local ML inference only. The 15-minute EventBridge cycle is the intended "
    "production latency for the full pipeline and is not a performance defect — it is by architectural design."
)

p_sig = doc.add_paragraph()
p_sig.paragraph_format.space_before = Pt(20)
r_sig = p_sig.add_run(
    "Prepared by: Abhishek Doke, Nikhil Dhamdhere, Joanna Dharwadkar, Geetanjali Bejjalwar\n"
    "Department of Computer Engineering\n"
    "Dr. D.Y. Patil College of Engineering and Innovation, Varale, Talegaon\n"
    "Date: May 2026"
)
r_sig.font.size = Pt(10); r_sig.italic = True

# ── Save ──────────────────────────────────────────────────────────────────────
out = "COLDSTART_Testing_Report.docx"
doc.save(out)
print(f"Saved: {out}")
