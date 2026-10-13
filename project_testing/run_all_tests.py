"""
Run All Tests — COLDSTART Project Test Suite
Runs all 10 test scripts and prints a final summary table.

Run from project root:
    python project_testing/run_all_tests.py
"""
import subprocess, sys, os, time

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; BOLD="\033[1m"; E="\033[0m"

TESTS = [
    ("UT1", "UT1_data_collection.py",    "Unit",        "Data Collection"),
    ("UT2", "UT2_preprocessing.py",      "Unit",        "Preprocessing"),
    ("UT3", "UT3_prediction.py",         "Unit",        "Prediction Module"),
    ("IT1", "IT1_api_to_lambda.py",      "Integration", "API to Lambda (S3)"),
    ("IT2", "IT2_lambda_to_dynamodb.py", "Integration", "Lambda to DynamoDB"),
    ("IT3", "IT3_ml_model_integration.py","Integration","ML Model Integration"),
    ("ST1", "ST1_end_to_end_workflow.py","System",      "End-to-End Workflow"),
    ("ST2", "ST2_cold_start_prediction.py","System",    "Cold Start Prediction"),
    ("ST3", "ST3_pre_warming_trigger.py","System",      "Pre-warming Trigger"),
    ("PT1", "PT1_response_time.py",      "Performance", "Response Time"),
    ("PT2", "PT2_load_handling.py",      "Performance", "Load Handling"),
    ("UAT1","UAT1_user_interaction.py",  "UAT",         "User Interaction"),
    ("UAT2","UAT2_system_usability.py",  "UAT",         "System Usability"),
]

test_dir = os.path.dirname(os.path.abspath(__file__))
summary  = []

print(f"\n{BOLD}{'='*70}{E}")
print(f"{BOLD}COLDSTART — Full Test Suite ({len(TESTS)} tests){E}")
print(f"{'='*70}")
print(f"Started: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*70}\n")

for tid, fname, ttype, desc in TESTS:
    script = os.path.join(test_dir, fname)
    print(f"{B}[{tid}]{E} {ttype}: {desc}")
    start  = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True, timeout=120
    )
    elapsed = time.time() - start
    passed  = result.returncode == 0 and "FAIL" not in result.stdout
    # Check output lines for pass/fail
    lines   = result.stdout.splitlines()
    fail_count = sum(1 for l in lines if "FAIL" in l and not "Overall" in l)
    pass_count = sum(1 for l in lines if "PASS" in l and not "Overall" in l)

    status = f"{G}PASS{E}" if fail_count == 0 else f"{R}FAIL{E}"
    print(f"     Status: {status}  |  {pass_count} checks passed, {fail_count} failed  |  {elapsed:.1f}s")

    # Print last few relevant lines
    for line in lines[-4:]:
        if line.strip() and '===' not in line:
            print(f"     {line}")
    print()

    summary.append((tid, ttype, desc, fail_count == 0, elapsed))

# Final summary table
print(f"\n{BOLD}{'='*70}{E}")
print(f"{BOLD}FINAL TEST SUMMARY{E}")
print(f"{'='*70}")
print(f"  {'ID':<6} {'Type':<14} {'Description':<35} {'Result':<8} {'Time'}")
print(f"  {'-'*65}")
for tid, ttype, desc, passed, elapsed in summary:
    result_str = f"{G}PASS{E}" if passed else f"{R}FAIL{E}"
    print(f"  {tid:<6} {ttype:<14} {desc:<35} {result_str}    {elapsed:.1f}s")

total  = len(summary)
passed = sum(1 for _, _, _, p, _ in summary if p)
print(f"\n  {BOLD}Total: {passed}/{total} test scripts passed{E}")
print(f"{'='*70}\n")
