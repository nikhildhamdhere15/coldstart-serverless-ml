"""
Generate COLDSTART_Updated_Paper.docx in IEEE conference paper style.
Run: python generate_paper_docx.py
"""

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# ── Page setup (IEEE — letter, narrow margins) ────────────────────────────────
section = doc.sections[0]
section.page_width  = Inches(8.5)
section.page_height = Inches(11)
section.left_margin   = Inches(0.75)
section.right_margin  = Inches(0.75)
section.top_margin    = Inches(1.0)
section.bottom_margin = Inches(1.0)

# ── Styles helper ─────────────────────────────────────────────────────────────
def set_font(run, name="Times New Roman", size=10, bold=False, italic=False, color=None):
    run.font.name  = name
    run.font.size  = Pt(size)
    run.bold       = bold
    run.italic     = italic
    if color:
        run.font.color.rgb = color

def para_fmt(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0,
             space_after=4, line_spacing=None, left_indent=0):
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if line_spacing:
        p.paragraph_format.line_spacing = Pt(line_spacing)
    if left_indent:
        p.paragraph_format.left_indent = Inches(left_indent)

def add_para(text, size=10, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
             space_before=0, space_after=4, left_indent=0, font="Times New Roman"):
    p = doc.add_paragraph()
    para_fmt(p, align=align, space_before=space_before, space_after=space_after, left_indent=left_indent)
    run = p.add_run(text)
    set_font(run, name=font, size=size, bold=bold, italic=italic)
    return p

def add_heading(number, title, size=10):
    p = doc.add_paragraph()
    para_fmt(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=8, space_after=3)
    run = p.add_run(f"{number}. {title.upper()}")
    set_font(run, size=size, bold=True)
    return p

def add_subheading(letter, title):
    p = doc.add_paragraph()
    para_fmt(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=5, space_after=2)
    run = p.add_run(f"{letter}. {title}")
    set_font(run, size=10, italic=True, bold=True)
    return p

def add_subsubheading(number, title):
    p = doc.add_paragraph()
    para_fmt(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=3, space_after=2)
    run = p.add_run(f"{number}) {title}")
    set_font(run, size=10, italic=True)
    return p

def add_bullet(text, indent=0.25):
    p = doc.add_paragraph()
    para_fmt(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=2, left_indent=indent)
    run = p.add_run(f"\u2022  {text}")
    set_font(run, size=10)
    return p

def add_equation(eq_text, number):
    p = doc.add_paragraph()
    para_fmt(p, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=4)
    run = p.add_run(eq_text)
    set_font(run, size=10, italic=True)
    run2 = p.add_run(f"    ({number})")
    set_font(run2, size=10)
    return p

def add_divider():
    p = doc.add_paragraph()
    para_fmt(p, space_before=2, space_after=2)
    run = p.add_run("\u2015" * 80)
    set_font(run, size=7)
    return p

# ══════════════════════════════════════════════════════════════════════════════
# TITLE BLOCK
# ══════════════════════════════════════════════════════════════════════════════
p_title = doc.add_paragraph()
para_fmt(p_title, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6)
r = p_title.add_run("COLDSTART: Cost- and Latency-Optimized Serverless Orchestration via Multi-Modal Prediction and Confidence-Based Warming")
set_font(r, size=16, bold=True)

p_authors = doc.add_paragraph()
para_fmt(p_authors, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=2)
r = p_authors.add_run("Abhishek Doke\u00b9, Nikhil Dhamdhere\u00b2, Joanna Dharwadkar\u00b3, Geetanjali Bejjalwar\u2074, Dr. Alpana Adsul\u2075")
set_font(r, size=11, bold=True)

p_dept = doc.add_paragraph()
para_fmt(p_dept, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=1)
r = p_dept.add_run("Department of Computer Engineering")
set_font(r, size=10, italic=True)

p_inst = doc.add_paragraph()
para_fmt(p_inst, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=1)
r = p_inst.add_run("Dr. D.Y. Patil College of Engineering and Innovation, Varale, Talegaon, India")
set_font(r, size=10, italic=True)

p_email = doc.add_paragraph()
para_fmt(p_email, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6)
r = p_email.add_run("{abhishekdoke233@gmail.com, dhamdherenikhil75@gmail.com, dharwadkarjoanna@gmail.com, bejjalwargeetanjali@gmail.com, hodcomputer@dypatilef.com}")
set_font(r, size=9, italic=True)

p_journal = doc.add_paragraph()
para_fmt(p_journal, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=8)
r = p_journal.add_run("Journal of Advanced Computing, Intelligence and Interdisciplinary Engineering (JACIIE)\nVolume 101, No. 1, June 2026")
set_font(r, size=9, italic=True)

add_divider()

# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT
# ══════════════════════════════════════════════════════════════════════════════
p_abs_head = doc.add_paragraph()
para_fmt(p_abs_head, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=6, space_after=2)
r1 = p_abs_head.add_run("Abstract\u2014")
set_font(r1, size=10, bold=True, italic=True)
r2 = p_abs_head.add_run(
    "Serverless computing (Function-as-a-Service, FaaS) is severely limited by the cold start problem\u2014"
    "a latency penalty incurred during container initialization. Current mitigation approaches, relying primarily on "
    "static keep-alive policies or single-source time-series prediction, fail to balance performance consistency with "
    "resource cost, often leading to a 40\u201360% waste in resource provisioning. We introduce COLDSTART (Cost- and "
    "Latency-Optimized Serverless Orchestration via Multi-Modal Prediction and Confidence-Based Warming), an intelligent "
    "orchestration framework designed to minimize cold start occurrences and resource overhead simultaneously.\n\n"
    "Our core contribution is a Multi-Modal Prediction (MMP) architecture that fuses four AWS-native data modalities\u2014"
    "Lambda invocation history, temporal context, user behavior, and system health\u2014into a unified feature space. "
    "This space is analyzed by a dual-model Ensemble Prediction Engine (XGBoost at 70% weight and Random Forest at 30% weight) "
    "deployed on AWS infrastructure to generate highly accurate invocation forecasts. We propose a Confidence-Based Warming (CBW) "
    "mechanism that gates resource allocation based on a calculated prediction confidence score (C), thereby minimizing expensive false positives.\n\n"
    "The COLDSTART framework is validated on a production AWS deployment using synthetically generated workloads designed to replicate "
    "real-world FaaS invocation patterns. The system achieved 94.2% F1 prediction accuracy, a 58.7% reduction in cold start events, and "
    "a 34.8% reduction in operational costs compared to a single-source ML baseline."
)
set_font(r2, size=10)

p_kw = doc.add_paragraph()
para_fmt(p_kw, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=4, space_after=6)
r_kw1 = p_kw.add_run("Keywords\u2014")
set_font(r_kw1, size=10, bold=True)
r_kw2 = p_kw.add_run("Serverless Computing, FaaS, Cold Start Mitigation, Multi-Modal Prediction, Ensemble Learning, Cost Optimization, Proactive Warming, AWS Lambda, Confidence-Based Warming.")
set_font(r_kw2, size=10, italic=True)

add_divider()

# ══════════════════════════════════════════════════════════════════════════════
# I. INTRODUCTION
# ══════════════════════════════════════════════════════════════════════════════
add_heading("I", "Introduction")

add_para(
    "The Function-as-a-Service (FaaS) model of serverless computing is a paradigm shift toward pay-per-use, "
    "fine-grained resource management. Major cloud providers\u2014including AWS Lambda, Azure Functions, and Google Cloud "
    "Functions\u2014leverage this model to offer unprecedented scalability. However, the FaaS model is inherently constrained by "
    "the cold start problem: an initialization delay ranging from hundreds of milliseconds to several seconds that occurs when a "
    "function instance must be created from scratch [1]. This delay undermines the reliability and Quality of Service (QoS) for "
    "latency-sensitive applications.",
    space_after=4
)

add_para(
    "The underlying difficulty lies in balancing performance consistency with cost efficiency. Proactive container initialization, "
    "while guaranteeing fast response times, results in unnecessary idle resource consumption, negating the core economic benefit of "
    "serverless platforms [13]. Existing solutions often fail because they lack the comprehensive contextual data required to predict "
    "complex, non-periodic invocation patterns, leading to either poor latency performance (false negatives) or significant resource "
    "waste (false positives).",
    space_after=4
)

add_para(
    "COLDSTART addresses this by designing an intelligent, closed-loop system that models and predicts application behavior using a "
    "rich, multi-modal context drawn from historical invocation patterns, temporal features, user behavior telemetry, and system health metrics.",
    space_after=6
)

add_subheading("A", "Research Motivation and Problem Formulation")
add_para(
    "Traditional predictive systems predominantly rely on univariate time-series data (i.e., historical function call counts) [3]. "
    "This approach fundamentally limits the model's ability to reason about user intent or external events such as upstream API load "
    "and scheduled workflows. We argue that a successful prediction of FaaS invocation requires fusion of heterogeneous data modalities, "
    "including user flow, system health, and temporal context.",
    space_after=4
)
add_para(
    "Furthermore, no existing approach adequately integrates prediction uncertainty into the financial cost of the corresponding resource "
    "action. An action taken with 95% confidence should be valued differently than one taken with 75% confidence. The core problem is "
    "formalized as: given a stream of multi-modal telemetry \u1d5d\u1d5c, determine the optimal set of pre-warming actions \u1d00\u1d5c "
    "that minimizes the total cost C\u209c\u2092\u209c\u2090\u2097 while maintaining a Service Level Objective (SLO) for latency L\u209b\u2097\u2092:",
    space_after=2
)
add_equation("min_{A_t}  ( C_warming(A_t) + C_penalty(L_SLO) )", "")

add_subheading("B", "Key Contributions")
add_para("This paper makes the following contributions, each addressing a specific limitation of prior work:", space_after=3)
add_bullet("Multi-Modal Data Fusion (MMP) Framework: A novel pipeline fusing four AWS-native data modalities for enriched, context-aware prediction, directly addressing the limitation of single-source models identified in [3].")
add_bullet("Dual-Model Ensemble Prediction Engine (EPE): A cost-efficient architecture combining XGBoost (70% weight) and Random Forest (30% weight) deployed on AWS, providing robust prediction without deep learning overhead.")
add_bullet("Confidence-Based Warming (CBW) Mechanism: A resource orchestration policy that gates pre-warming based on a calculated confidence score (C), explicitly minimizing false positives\u2014a gap unaddressed by priority-based approaches [2].")
add_bullet("Cost-Benefit Ratio (CBR) Adaptation: Dynamic risk threshold adjustment based on a live-calculated CBR, ensuring self-optimizing economic behavior.")
add_bullet("Production Validation on AWS: Unlike prior work using theoretical models, COLDSTART is validated on real AWS infrastructure with live DynamoDB, S3, Lambda, and CloudWatch integration.", )

add_subheading("C", "Differentiation from Prior Work")
add_para(
    "COLDSTART differs from existing approaches in three key dimensions. First, reinforcement learning approaches such as [3] "
    "optimize container lifetime but do not predict invocation probability\u2014they react to cold starts rather than preventing them. "
    "Second, priority-based scheduling methods like Incendio [2] rank functions by latency benefit but rely on single-source historical data "
    "without confidence gating. Third, workflow scheduling systems such as SSC [4] optimize resource allocation across function dependencies "
    "but do not address the fundamental prediction accuracy problem. COLDSTART integrates prediction, confidence scoring, and cost-aware gating "
    "into a unified framework that outperforms each of these approaches individually.",
    space_after=6
)

# ══════════════════════════════════════════════════════════════════════════════
# II. BACKGROUND
# ══════════════════════════════════════════════════════════════════════════════
add_heading("II", "Background and Related Work")
add_subheading("A", "Serverless Cold Start Mitigation Techniques")
add_para(
    "Early cold start mitigation efforts focused on two key areas: reducing setup time and prolonging container lifespan. "
    "Techniques include MicroVM snapshotting [7], optimizing deployment package sizes, and applying simple keep-alive heuristics [5]. "
    "However, these solutions address symptoms rather than the root cause of unpredictable demand.",
    space_after=4
)
add_bullet("Reinforcement Learning for Lifetime: Vahidinia et al. [3] employed an RL approach to dynamically set container idle time. However, this approach is reactive and does not predict whether a cold start will occur before the next invocation.")
add_bullet("Priority-Aware Scheduling: Incendio [2] allocates resources to containers whose warming yields the greatest latency reduction. This heuristic is effective but relies solely on historical invocation rates without confidence scoring.")
add_bullet("Systemic Optimization: SSC [4] integrates pre-warming with automatic workflow resource scheduling. However, it does not model user behavior or external trigger data.")
add_bullet("Container Reuse Policies: FaaSCache [6] improves container reuse through adaptive policies but does not incorporate predictive warming.")

add_subheading("B", "The Necessity of Multi-Modal Fusion")
add_para(
    "Recent literature in cloud computing highlights the limitations of single-source prediction models in dynamic, event-driven "
    "environments. Chen et al. [14] demonstrated that ensemble models combining heterogeneous data sources achieve significantly higher "
    "workload prediction accuracy than single-source baselines. Cao et al. [15] showed that multi-source data fusion enables superior task "
    "scheduling by capturing correlations across data modalities that single-source approaches miss entirely. COLDSTART's empirical results "
    "(Section VIII-B) confirm that multi-modal features improve F1 accuracy by 22.7 percentage points over the single-source baseline.",
    space_after=6
)

# ══════════════════════════════════════════════════════════════════════════════
# III. SYSTEM ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
add_heading("III", "COLDSTART System Architecture")
add_para(
    "The COLDSTART framework is implemented as a closed-loop control system deployed on AWS, composed of three layers: "
    "a Data Collection and ETL Layer, an ML Prediction Pipeline, and an Intelligent Orchestration Layer.",
    space_after=4
)

# Architecture diagram as a code-style block
p_arch = doc.add_paragraph()
para_fmt(p_arch, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=4, space_after=4, left_indent=0.3)
r_arch = p_arch.add_run(
    "Traffic Generator \u2192 S3 (JSON Logs) \u2192 ETL Lambda \u2192 DynamoDB (ETLFeatureData)\n"
    "                                    \u2193\n"
    "          DataAggregator Lambda (EventBridge, every 15 min)\n"
    "          \u2193 reads DynamoDB \u2192 XGBoost (70%) + RF (30%) \u2192 P_final + C\n"
    "          \u2193 CBW Gate: P_final \u2265 0.7 AND C \u2265 0.6\n"
    "          \u2193 async invokes IntelligentLambdaWarmer\n"
    "                    \u2193 warms auth-function, profile-function, search-function\n"
    "                    \u2193 publishes metrics \u2192 CloudWatch (ColdStart/IntelligentWarming)"
)
set_font(r_arch, name="Courier New", size=8)

add_para(
    "Fig. 1. COLDSTART Multi-Layer System Architecture on AWS. Traffic data flows from the generator through S3, ETL, and "
    "DynamoDB into the ML pipeline. The DataAggregator Lambda reads DynamoDB features every 15 minutes, runs the ensemble "
    "prediction, applies the CBW gate, and asynchronously invokes IntelligentLambdaWarmer when P_final \u2265 0.7 AND C \u2265 0.6.",
    italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=6
)

add_subheading("A", "Data Collection Layer")
add_para(
    "The sensing layer collects, transforms, and stores feature data in 15-minute windows aligned with the EventBridge trigger schedule. "
    "The feature vector F_t = [HoD, DoW, traffic_intensity, ep_auth, ep_profile, ep_search, user_new, device_mobile, is_business_hours] "
    "contains 9 features per endpoint:",
    space_after=3
)
add_bullet("Lambda Invocation History (F_HIST): Synthetic traffic at ~3 requests/second targeting /auth, /profile, /search. Each record contains timestamp, endpoint, hour, day, traffic intensity, user type, and device type, stored in S3 under date-partitioned keys.")
add_bullet("Temporal Features (F_TEMP): Hour of Day (0\u201323), Day of Week (0\u20136), and is_business_hours binary flag (1 if 09:00\u201317:00 weekdays).")
add_bullet("User Behavior (F_USER): user_type_new ratio and device_mobile ratio computed over the 15-minute aggregation window.")
add_bullet("System Metrics (F_SYS): traffic_intensity = max(0.01, min(1.0, (n_requests \u2212 5) \u00d7 0.002)), a normalized proxy for server load.")

add_subheading("B", "ETL Pipeline")
add_para(
    "An ETL Lambda function triggered by S3 object creation events reads raw JSON logs, extracts the 9-element feature vector, "
    "and writes structured records to the ETLFeatureData DynamoDB table with a Unix timestamp (timestamp_s) for efficient time-range queries. "
    "The ETL process completes within 200 ms per record, ensuring feature freshness within the 15-minute aggregation window.",
    space_after=6
)

# ══════════════════════════════════════════════════════════════════════════════
# IV. ML PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
add_heading("IV", "The Machine Learning Pipeline")
add_subheading("A", "Feature Engineering and Aggregation")
add_para(
    "The DataAggregator Lambda, triggered every 15 minutes by Amazon EventBridge, performs: (1) DynamoDB scan for records "
    "with timestamp_s in the last 15 minutes; (2) grouping by endpoint (auth, profile, search), skipping endpoints with fewer than "
    "5 records; (3) feature vector construction using the most recent record's temporal fields and computed ratios from the full window.",
    space_after=4
)

add_subheading("B", "Ensemble Prediction Engine (EPE)")
add_para(
    "The EPE employs a dual-model architecture optimized for AWS Lambda constraints (memory, predictor cold start, execution time).",
    space_after=3
)

add_subsubheading("1", "XGBoost Primary Classifier (M_XGB)")
add_para("Configuration: binary:logistic objective, n_estimators=100, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, eval_metric=AUC.", space_after=3, left_indent=0.2)

add_subsubheading("2", "Random Forest Secondary Model (M_RF)")
add_para("Implemented as an XGBoost classifier with Random Forest-style hyperparameters: n_estimators=200, max_depth=8, learning_rate=0.05, subsample=0.7, colsample_bytree=0.7, min_child_weight=3.", space_after=3, left_indent=0.2)

add_subsubheading("3", "Ensemble Fusion")
add_para("The final ensemble prediction uses a fixed weighted combination determined through 5-fold cross-validation:", space_after=2, left_indent=0.2)
add_equation("P_final = 0.7 \u00d7 P_XGB + 0.3 \u00d7 P_RF", "1")

add_subsubheading("4", "Confidence Scoring")
add_para("The Confidence Score C measures agreement between the two base models:", space_after=2, left_indent=0.2)
add_equation("C = 1 \u2212 |P_XGB \u2212 P_RF| / max(P_XGB, P_RF)", "2")
add_para("A high C indicates model agreement, reducing the risk of resource waste from uncertain predictions. The CBW gate prevents wasteful warming even when P_final is high but C is low.", space_after=4, left_indent=0.2)

add_subheading("C", "Model Training Details")
add_para("Dataset Generation: Training data is generated using a probabilistic model calibrated to replicate real-world FaaS cold start patterns from the Microsoft Azure Functions public traces.", space_after=3)

add_para("The cold start probability for each training sample is:", space_after=2)
p_cs = doc.add_paragraph()
para_fmt(p_cs, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=2, space_after=4, left_indent=0.3)
r_cs = p_cs.add_run(
    "p_cold = 0.05  (base)\n"
    "       + 0.40  (if not business hours)\n"
    "       + 0.50  (if traffic_intensity < 0.15)\n"
    "       + 0.30  (if new user AND low traffic)\n"
    "       + 0.40  (if auth endpoint AND hour < 07:00)\n"
    "       + 0.20  (if mobile device AND not business hours)\n"
    "       + 0.25  (if weekend)\n"
    "p_cold = min(p_cold, 0.95)"
)
set_font(r_cs, name="Courier New", size=9)

add_para("Dataset Statistics:", bold=True, space_after=2)
add_bullet("Training set: 1,000 samples (XGBoost), 2,000 samples (RF); Validation split: 80/20 train/test")
add_bullet("Cold start ratio: ~62% (class imbalance handled via weighted loss, \u03b1 = 0.7)")
add_bullet("Feature dimensions: 9 scalar features; Random seeds: 42 (XGBoost), 123 (RF) for reproducibility")
add_bullet("Training hardware: Intel Core i7, 16 GB RAM; XGBoost training time: ~0.8 s; RF training time: ~1.4 s")
add_bullet("Model sizes: XGBoost 223 KB, RF 465 KB; Lambda cold start overhead for model load: ~962 ms (once at container init)")

add_para("Evaluation Protocol: Models are evaluated on the held-out 20% validation split using weighted F1 score (primary metric due to class imbalance), AUC-ROC, and confusion matrix analysis.", space_after=6)

# ══════════════════════════════════════════════════════════════════════════════
# V. MATHEMATICAL MODELING
# ══════════════════════════════════════════════════════════════════════════════
add_heading("V", "Detailed Mathematical Modeling")
add_subheading("A", "Cost Function for Ensemble Weight Optimization")
add_para(
    "The XGBoost primary model is trained by minimizing the weighted Binary Cross-Entropy loss to penalize false negatives "
    "(missed cold starts) more heavily than false positives (unnecessary warming):",
    space_after=2
)
add_equation("L_BCE = \u2212 (1/N) \u03a3 [ \u03b1\u00b7y\u00b7log(P) + (1\u2212\u03b1)\u00b7(1\u2212y)\u00b7log(1\u2212P) ]", "3")
add_para(
    "where y \u2208 {0,1} is the ground truth label, P is the predicted probability, N is the batch size, and \u03b1 = 0.7 reflects the "
    "higher cost of a false negative (latency penalty vs. warming cost). The negative sign ensures loss minimization. This formulation "
    "differs from standard BCE (\u03b1 = 0.5) by increasing the penalty for missed cold starts.",
    space_after=6
)

add_subheading("B", "Confidence-Based Warming (CBW) Decision Rule")
add_para("The CBW mechanism translates the probabilistic EPE output into a binary warming decision:", space_after=2)
p_cbw = doc.add_paragraph()
para_fmt(p_cbw, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=4)
r_cbw = p_cbw.add_run(
    "A_warm = True,   if P_final \u2265 T_predict AND C \u2265 T_confidence\n"
    "          False,  otherwise                                        (4)"
)
set_font(r_cbw, size=10, italic=True)
add_para(
    "Fig. 2. CBW Gating Policy. A pre-warming action is triggered only when both the ensemble probability P_final \u2265 T_predict (0.7) "
    "AND the confidence score C \u2265 T_confidence (0.6). The dual gate eliminates costly false positives that arise from uncertain predictions.",
    italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=4
)
add_para(
    "The static thresholds T_predict = 0.7 and T_confidence = 0.6 were calibrated to achieve Purity of Warming > 80% while maintaining "
    "cold start reduction > 55%.",
    space_after=6
)

add_subheading("C", "Cost-Benefit Ratio (CBR) Analysis")
add_para("The economic viability of COLDSTART is quantified by the Cost-Benefit Ratio:", space_after=2)
add_equation("CBR = (P_FN \u00b7 C_penalty) / (P_FP \u00b7 C_warm)", "5")
add_para("Where the cost components are defined as:", space_after=3)
add_bullet("P_FN: empirical false negative rate (missed cold starts) from validation data")
add_bullet("P_FP: empirical false positive rate (unnecessary warming) from validation data")
add_bullet("C_penalty: cost of a false negative = latency_penalty_ms \u00d7 cost_per_ms_SLA_violation (\u2248 $0.00023 per 100 ms, based on AWS provisioned concurrency pricing)")
add_bullet("C_warm: cost of unnecessary warming = idle_duration \u00d7 memory_GB \u00d7 AWS_per_GB_second_price = 10 s \u00d7 0.512 GB \u00d7 $0.0000166667 = $0.0000853")
add_para(
    "For COLDSTART (P_FN = 5.8%, P_FP = 14.3%): CBR = (0.058 \u00d7 0.00023) / (0.143 \u00d7 0.0000853) = 1.10. "
    "A CBR > 1.0 confirms the cost of missed cold starts exceeds unnecessary warming costs. This contrasts with the single-source "
    "baseline (CBR = 0.83), which incurs a net financial loss due to excessive false positives.",
    space_after=6
)

add_subheading("D", "Dynamic Threshold Adaptation (Future Extension)")
add_para("A planned extension incorporates a Proportional-Integral (PI) controller to dynamically adjust T_confidence:", space_after=2)
add_equation("E(t) = CBR_target \u2212 CBR_function(t)", "6")
add_equation("u(t) = K_p \u00b7 E(t) + K_i \u00b7 \u222b\u2080\u1d57 E(\u03c4) d\u03c4", "7")
add_para("Where K_p drives immediate correction and K_i eliminates steady-state errors. This extension is detailed in Section IX-A as a future research direction.", space_after=6)

# ══════════════════════════════════════════════════════════════════════════════
# VI. IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════════════
add_heading("VI", "Implementation Details and System Workflow")
add_subheading("A", "AWS Cloud Architecture")
add_para("COLDSTART is deployed on AWS in the ap-south-1 (Mumbai) region. Table II summarizes all deployed components.", space_after=4)

# Table II - AWS Components
t2 = doc.add_table(rows=10, cols=3)
t2.style = 'Table Grid'
t2.alignment = WD_TABLE_ALIGNMENT.CENTER

headers2 = ["Component", "AWS Service", "Configuration"]
for i, h in enumerate(headers2):
    c = t2.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)
    c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

rows_data2 = [
    ["Traffic Generator", "Python Script / EC2", "3 req/s, round-robin /auth /profile /search"],
    ["Raw Log Storage", "Amazon S3", "Date-partitioned: training-data/YYYY/MM/DD/"],
    ["ETL Processing", "AWS Lambda (ETLLambda)", "S3 event trigger, ~200 ms avg execution"],
    ["Feature Storage", "Amazon DynamoDB", "ETLFeatureData table, timestamp_s GSI"],
    ["ML Aggregation", "AWS Lambda (DataAggregator)", "512 MB, 300 s timeout, EventBridge every 15 min"],
    ["Function Warming", "AWS Lambda (IntelligentLambdaWarmer)", "256 MB, 180 s timeout"],
    ["Target Functions", "AWS Lambda", "auth-function, profile-function, search-function"],
    ["Metrics", "Amazon CloudWatch", "Namespace: ColdStart/IntelligentWarming"],
    ["Monitoring", "Streamlit Dashboard", "Real-time DynamoDB + CloudWatch integration"],
]
for ri, row_data in enumerate(rows_data2, 1):
    for ci, val in enumerate(row_data):
        c = t2.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)

add_para("Table II. COLDSTART AWS Deployment Configuration.", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

add_subheading("B", "Traffic Generation and Workload Synthesis")
add_para(
    "The traffic generator produces synthetic workloads replicating real-world cold start risk patterns, calibrated to the "
    "Microsoft Azure Functions public dataset [16]:",
    space_after=3
)
add_bullet("60% Extreme Risk (cold start probability ~0.90): off-hours (00:00\u201304:00), weekend, traffic_intensity \u2208 [0.01, 0.08], new mobile user")
add_bullet("25% High Risk (cold start probability ~0.70): late evening (22:00\u201323:00) or early morning (05:00), traffic_intensity \u2208 [0.09, 0.20]")
add_bullet("15% Low Risk (cold start probability ~0.15): business hours (12:00\u201316:00), weekday, traffic_intensity \u2208 [1.6, 2.5], returning desktop user")
add_para("Each 15-minute window contains ~180 requests (3 req/min \u00d7 60 min), distributed approximately equally across the three endpoints (~60 requests per endpoint). This exceeds the minimum threshold of 5 records per endpoint required for DataAggregator processing.", space_after=6)

add_subheading("C", "DataAggregator Workflow")
add_para("The DataAggregator Lambda executes the following steps every 15 minutes:", space_after=3)
p_wf = doc.add_paragraph()
para_fmt(p_wf, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=2, space_after=4, left_indent=0.3)
r_wf = p_wf.add_run(
    "1. DynamoDB Scan: Retrieve records with timestamp_s in last 15 min (paginated)\n"
    "2. Group by endpoint: auth, profile, search (skip if < 5 records)\n"
    "3. Construct 9-element feature vector per endpoint\n"
    "4. Load XGBoost + RF models from bundled .pkl files\n"
    "5. Compute P_final (Eq. 1) and C (Eq. 2) per endpoint\n"
    "6. Apply CBW gate (Eq. 4): collect endpoints with P_final \u2265 0.7 AND C \u2265 0.6\n"
    "7. Async invoke IntelligentLambdaWarmer (InvocationType='Event', HTTP 202)\n"
    "   Total execution: ~156 ms (excluding model load at cold start)"
)
set_font(r_wf, name="Courier New", size=9)

add_subheading("D", "IntelligentLambdaWarmer Workflow")
add_para(
    "The IntelligentLambdaWarmer receives the predictions payload and: (1) assigns priority (HIGH if P_final \u2265 0.8, MEDIUM if \u2265 0.7) "
    "and warming frequency (2\u20133 for HIGH, 1 for MEDIUM); (2) synchronously invokes each target Lambda with a warming ping; "
    "(3) publishes per-endpoint CloudWatch metrics (ColdStartProbability, WarmingSuccessRate, FunctionsWarmed). "
    "Observed execution: ~11\u201313 seconds for 3 endpoints at HIGH priority (8 total warming invocations, 100% success rate).",
    space_after=6
)

# ══════════════════════════════════════════════════════════════════════════════
# VII. EXPERIMENTAL METHODOLOGY
# ══════════════════════════════════════════════════════════════════════════════
add_heading("VII", "Experimental Methodology")
add_subheading("A", "Testbed Configuration")
add_para("All experiments were conducted on AWS infrastructure in the ap-south-1 region:", space_after=3)
add_bullet("Compute: AWS Lambda (128\u2013512 MB memory, Python 3.9 runtime)")
add_bullet("Storage: Amazon DynamoDB (on-demand capacity) and Amazon S3 (Standard)")
add_bullet("ML Models: XGBoost 1.7.6, scikit-learn 1.3.0, deployed as Lambda Layer (73 MB compressed)")
add_bullet("Monitoring: Amazon CloudWatch, 15-minute metric resolution")
add_bullet("Experiment Duration: 2-hour sessions producing ~700 DynamoDB records; 3 Lambda functions under test")

add_subheading("B", "Workload Characterization")
add_para(
    "The synthetic workload was designed to match the statistical properties of the Microsoft Azure Functions public dataset [16] "
    "along three dimensions: (1) temporal distribution with 70% of requests in high-risk windows; (2) user behavior with 75% returning users, "
    "25% new users, 65% mobile devices; and (3) traffic intensity of mean 0.43 during business hours and 0.08 during off-hours.",
    space_after=6
)

add_subheading("C", "Baseline Comparisons")
add_bullet("Native Platform: No warming; all cold starts occur naturally, measured from DynamoDB cold start labels.")
add_bullet("Single-Source ML (S-S ML): XGBoost trained only on temporal features (HoD, DoW, is_business_hours) without user behavior or traffic intensity.")
add_bullet("Priority-Based Heuristic (P-B Heuristic): Warm all functions if request count exceeds 20 in the last 15 minutes, without ML prediction or confidence gating.")

add_subheading("D", "Evaluation Metrics")
add_bullet("Cold Start Reduction (R_CS): Percentage reduction in cold start events vs. native baseline")
add_bullet("F1 Score: Weighted F1 on held-out 20% validation split")
add_bullet("Purity of Warming (P_W): Fraction of warming invocations that were necessary (TP / total warming invocations)")
add_bullet("P95 / P99 Latency: 95th and 99th percentile response times from DynamoDB duration records")
add_bullet("Cost Efficiency (%R_Cost): Reduction in total operational cost vs. native baseline")

doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════════════
# VIII. RESULTS
# ══════════════════════════════════════════════════════════════════════════════
add_heading("VIII", "Results and Detailed Analysis")
add_subheading("A", "Prediction Accuracy and Cold Start Mitigation")
add_para("Table I presents the comparative performance metrics across all evaluated systems.", space_after=4)

# Table I - Main Results
t1 = doc.add_table(rows=8, cols=5)
t1.style = 'Table Grid'
t1.alignment = WD_TABLE_ALIGNMENT.CENTER

headers1 = ["Metric", "Native", "S-S ML", "P-B Heuristic", "COLDSTART"]
for i, h in enumerate(headers1):
    c = t1.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)
    c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

rows_data1 = [
    ["R_CS (Cold Start Reduction)", "0%", "35.4%", "48.2%", "58.7%"],
    ["F1 Accuracy", "N/A", "71.5%", "76.3%", "94.2%"],
    ["P95 Latency (ms)", "450", "312", "268", "187"],
    ["P99 Latency (ms)", "1,100", "720", "490", "310"],
    ["Purity of Warming (P_W)", "N/A", "58.3%", "64.1%", "85.7%"],
    ["%R_Cost (Cost Efficiency)", "0%", "\u22129.2% (loss)", "19.4%", "34.8%"],
    ["Warming Success Rate", "N/A", "N/A", "N/A", "100%"],
]
for ri, row_data in enumerate(rows_data1, 1):
    for ci, val in enumerate(row_data):
        c = t1.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)
        if ci == 4:
            c.paragraphs[0].runs[0].bold = True

add_para("Table I. Comparative Performance and Cost Metrics (AWS Production Deployment).", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

add_para(
    "The 94.2% F1 accuracy of COLDSTART represents a 22.7 percentage point improvement over S-S ML, validating the hypothesis that "
    "multi-modal feature fusion provides significant predictive advantage. This directly translates into a 58.7% cold start reduction. "
    "The P95 latency of 187 ms falls within the typical 200 ms SLO target, while the S-S ML baseline incurs a 9.2% financial loss due "
    "to its high false positive rate (41.7%).",
    space_after=6
)

add_subheading("B", "Ablation Study: Multi-Modal Fusion Impact")
add_para("Table III quantifies the incremental contribution of each feature modality:", space_after=4)

t3 = doc.add_table(rows=5, cols=3)
t3.style = 'Table Grid'
t3.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(["Feature Set", "F1 Score", "Cold Start Reduction"]):
    c = t3.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)

ablation_rows = [
    ["F_TEMP only (HoD, DoW, is_biz)", "71.5%", "35.4%"],
    ["+ F_USER (new/mobile ratio)", "79.8%", "44.1%"],
    ["+ F_SYS (traffic intensity)", "86.3%", "51.8%"],
    ["Full ensemble (all features)", "94.2%", "58.7%"],
]
for ri, row_data in enumerate(ablation_rows, 1):
    for ci, val in enumerate(row_data):
        c = t3.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)
        if ri == 4:
            c.paragraphs[0].runs[0].bold = True

add_para("Table III. Ablation Study: Incremental Feature Modality Contribution.", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

add_subheading("C", "Feature Importance Analysis")
add_para("Fig. 3 presents the top-9 feature importance scores (Gain metric) from the XGBoost component of the EPE:", space_after=4)

t4 = doc.add_table(rows=10, cols=2)
t4.style = 'Table Grid'
t4.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(["Feature", "Importance Score (Gain)"]):
    c = t4.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)

feat_rows = [
    ["traffic_intensity (F_SYS)", "2244"],
    ["user_type_new (F_USER)", "1188"],
    ["hour_of_day (F_TEMP)", "1111"],
    ["is_business_hours (F_TEMP)", "942"],
    ["device_mobile (F_USER)", "894"],
    ["day_of_week (F_TEMP)", "441"],
    ["endpoint_auth", "294"],
    ["endpoint_profile", "214"],
    ["endpoint_search", "143"],
]
for ri, row_data in enumerate(feat_rows, 1):
    for ci, val in enumerate(row_data):
        c = t4.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)

add_para("Fig. 3. Top-9 Feature Importance from the XGBoost Component (Gain metric). Traffic intensity and user behavior features rank highest, confirming the necessity of multi-modal fusion over temporal features alone.", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

add_subheading("D", "Cold Start Rate Time-Series Analysis")
add_para("Table IV illustrates the system's response to a cold start spike after a 1-hour idle period:", space_after=4)

t5 = doc.add_table(rows=7, cols=5)
t5.style = 'Table Grid'
t5.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(["Window", "Requests", "Cold Starts", "Cold Rate", "CBW Action"]):
    c = t5.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)

ts_rows = [
    ["18:00\u201318:15", "183", "22", "12.0%", "SKIP"],
    ["18:15\u201318:30", "178", "19", "10.7%", "SKIP"],
    ["18:30\u201318:45", "181", "20", "11.0%", "SKIP"],
    ["18:45\u201319:00", "176", "21", "11.9%", "SKIP"],
    ["20:00\u201320:15", "185", "162", "87.6%", "WARM \u26a1"],
    ["20:15\u201320:30", "180", "28", "15.6%", "SKIP (warmed)"],
]
for ri, row_data in enumerate(ts_rows, 1):
    for ci, val in enumerate(row_data):
        c = t5.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)
        if ri == 5:
            c.paragraphs[0].runs[0].bold = True

add_para("Table IV. Cold Start Rate Over a Representative 2-Hour Window. After a 1-hour idle period, cold start rate spikes to 87.6%. COLDSTART pre-warms functions, reducing subsequent cold starts to 15.6%.", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

add_subheading("E", "Cost-Benefit Analysis")
add_para("Table V presents the detailed cost analysis:", space_after=4)

t6 = doc.add_table(rows=8, cols=4)
t6.style = 'Table Grid'
t6.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, h in enumerate(["Metric", "S-S ML", "P-B Heuristic", "COLDSTART"]):
    c = t6.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)

cost_rows = [
    ["Purity of Warming (P_W)", "58.3%", "64.1%", "85.7%"],
    ["False Positive Rate", "41.7%", "35.9%", "14.3%"],
    ["False Negative Rate", "28.5%", "23.4%", "5.8%"],
    ["CBR", "0.83", "1.02", "1.10"],
    ["Monthly Warming Cost", "$18.40", "$14.20", "$8.50"],
    ["Monthly Latency Savings", "$16.70", "$17.10", "$18.00"],
    ["Net Monthly Benefit", "\u2212$1.70", "+$2.90", "+$9.50"],
]
for ri, row_data in enumerate(cost_rows, 1):
    for ci, val in enumerate(row_data):
        c = t6.rows[ri].cells[ci]
        c.text = val
        c.paragraphs[0].runs[0].font.size = Pt(9)
        if ci == 3:
            c.paragraphs[0].runs[0].bold = True

add_para("Table V. Detailed Cost-Benefit Analysis. COLDSTART's confidence gate (C \u2265 0.6) is the primary driver of 85.7% warming purity and positive net monthly benefit.", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=3, space_after=6)

# ══════════════════════════════════════════════════════════════════════════════
# IX. CONCLUSION
# ══════════════════════════════════════════════════════════════════════════════
add_heading("IX", "Conclusion and Future Work")
add_para(
    "We presented COLDSTART, a practical, cloud-native orchestration framework for FaaS cold start mitigation validated on "
    "production AWS infrastructure. By achieving 94.2% prediction accuracy through dual-model ensemble learning with a "
    "Confidence-Based Warming gate, COLDSTART demonstrates a 58.7% reduction in cold starts and a 34.8% reduction in operational "
    "costs compared to single-source ML baselines. The key insight is that cold start prediction is fundamentally a multi-modal problem: "
    "temporal features alone achieve 71.5% F1, but incorporating user behavior and traffic intensity raises this to 94.2%. Furthermore, "
    "prediction accuracy alone is insufficient; the CBW gate ensures that uncertain predictions do not result in wasteful resource allocation.",
    space_after=6
)

add_subheading("A", "Future Research Directions")
add_bullet("Adaptive T_confidence with Deep RL: A Deep RL agent to continuously optimize CBW thresholds using cost/latency metrics as reward signal.")
add_bullet("LSTM Integration: A lightweight LSTM component to capture temporal sequence dependencies (e.g., burst patterns) that tree models cannot model directly.")
add_bullet("Resource Sizing Optimization: Extending the binary warm/skip decision to continuous optimal Memory/CPU allocation prediction.")
add_bullet("Multi-Cloud Telemetry Standardization: A universal interface abstracting CloudWatch, Azure Monitor, and GCP Monitoring for cross-cloud portability.")
add_bullet("Real-Time Streaming Pipeline: Replacing 15-minute batch aggregation with AWS Kinesis streaming to reduce prediction latency from 15 minutes to under 30 seconds.")

doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════════════
# ACKNOWLEDGMENT
# ══════════════════════════════════════════════════════════════════════════════
add_heading("", "Acknowledgment")
add_para(
    "The authors wish to thank the faculty and staff of the Department of Computer Engineering at Dr. D.Y. Patil College of Engineering "
    "and Innovation, Varale, Talegaon, for their invaluable guidance, institutional support, and provision of computational resources "
    "throughout this research. The authors also gratefully acknowledge the contributions of the open-source XGBoost [17], scikit-learn, "
    "and Streamlit communities whose tools formed the foundation of this implementation.",
    space_after=8
)

# ══════════════════════════════════════════════════════════════════════════════
# REFERENCES
# ══════════════════════════════════════════════════════════════════════════════
add_heading("", "References")

refs = [
    "[1]\tS. Eismann et al., \u201cA review of serverless use cases and their characteristics,\u201d IEEE Access, vol. 8, pp. 159981\u2013160000, 2020.",
    "[2]\tX. Cai et al., \u201cIncendio: Priority-based scheduling for alleviating cold start in serverless computing,\u201d IEEE Trans. Comput., vol. 73, no. 7, pp. 1780\u20131793, Jul. 2024.",
    "[3]\tP. Vahidinia, B. Farahani, and F. S. Aliee, \u201cMitigating cold start problem in serverless computing: A reinforcement learning approach,\u201d IEEE Internet of Things J., vol. 10, no. 5, pp. 3917\u20133927, Mar. 2023.",
    "[4]\tS. Pan et al., \u201cSustainable serverless computing with cold-start optimization and automatic workflow resource scheduling,\u201d IEEE Trans. Sustain. Comput., vol. 9, no. 3, pp. 329\u2013342, May/Jun. 2024.",
    "[5]\tK. Suo et al., \u201cTackling cold start of serverless applications by efficient and adaptive container runtime reusing,\u201d in Proc. IEEE Int. Conf. Cluster Comput. (CLUSTER), 2021, pp. 433\u2013443.",
    "[6]\tJ. Chen et al., \u201cFaaSCache: A flexible and adaptive container reuse policy for serverless computing,\u201d IEEE Trans. Parallel Distrib. Syst., vol. 32, no. 6, pp. 1475\u20131489, Jun. 2021.",
    "[7]\tY. Wang et al., \u201cDemystifying and optimizing MicroVM initialization in serverless computing,\u201d IEEE Trans. Parallel Distrib. Syst., vol. 35, no. 1, pp. 174\u2013188, Jan. 2024.",
    "[8]\tZ. Xu et al., \u201cAdaptive function launching acceleration in serverless computing platforms,\u201d in Proc. IEEE 25th Int. Conf. Parallel Distrib. Syst. (ICPADS), 2019, pp. 9\u201316.",
    "[9]\tS. Eismann et al., \u201cSizeless: Predicting the optimal size of serverless functions,\u201d in Proc. 22nd ACM/IFIP/USENIX Int. Middleware Conf., 2021, pp. 248\u2013259.",
    "[10]\tS. R. Chaudhry et al., \u201cImproved QoS at the edge using serverless computing to deploy virtual network functions,\u201d IEEE Internet Things J., vol. 7, no. 10, pp. 10673\u201310683, Oct. 2020.",
    "[11]\tA. Mampage et al., \u201cDeadline-aware dynamic resource management in serverless computing environments,\u201d in Proc. IEEE/ACM 21st Int. Symp. Cluster, Cloud Internet Comput. (CCGrid), 2021, pp. 483\u2013492.",
    "[12]\tA. Singhvi et al., \u201cAtoll: A scalable low-latency serverless platform,\u201d IEEE Trans. Cloud Comput., vol. 11, no. 1, pp. 104\u2013118, Jan./Mar. 2023.",
    "[13]\tAmazon Web Services, \u201cAWS Lambda Announces Provisioned Concurrency,\u201d Dec. 2019. [Online]. Available: https://aws.amazon.com/about-aws/whats-new/2019/12/aws-lambda-announces-provisioned-concurrency/",
    "[14]\tJ. Chen et al., \u201cA dynamic ensemble model for workload prediction in cloud computing,\u201d IEEE Trans. Services Comput., vol. 14, no. 6, pp. 1827\u20131838, Nov./Dec. 2021.",
    "[15]\tJ. Cao et al., \u201cMulti-source data fusion and task scheduling optimization in cloud computing environments,\u201d IEEE Trans. Parallel Distrib. Syst., vol. 32, no. 1, pp. 120\u2013131, Jan. 2021.",
    "[16]\tMicrosoft Azure, \u201cAzure Functions Invocation Traces Dataset,\u201d GitHub, 2020. [Online]. Available: https://github.com/Azure/AzurePublicDataset",
    "[17]\tT. Chen and C. Guestrin, \u201cXGBoost: A scalable tree boosting system,\u201d in Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining, 2016, pp. 785\u2013794.",
    "[18]\tL. Breiman, \u201cRandom forests,\u201d Machine Learning, vol. 45, no. 1, pp. 5\u201332, 2001.",
]

for ref in refs:
    p_ref = doc.add_paragraph()
    para_fmt(p_ref, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=1, space_after=2, left_indent=0.25)
    run = p_ref.add_run(ref)
    set_font(run, size=9)

# ── Save ──────────────────────────────────────────────────────────────────────
out = "COLDSTART_Updated_Paper.docx"
doc.save(out)
print(f"Saved: {out}")
