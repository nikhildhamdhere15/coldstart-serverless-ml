"""
COLDSTART — Cold Start Prevention Dashboard
Architecture:
  DataAggregator Lambda (AWS, every 15 min via EventBridge)
      → aggregated features from DynamoDB
  Local ML Models (XGBoost 70% + Random Forest 30%)
      → ensemble P_final + Confidence C
  CBW Gate: P_final >= 0.7 AND C >= 0.6
      → IntelligentLambdaWarmer (AWS Lambda)
      → CloudWatch metrics published
"""

import os
import queue as _queue_module
import threading
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

import aws_client
import ml_engine
import traffic_generator
import realtime_data
from config import aws

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="COLDSTART",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ────────────────────────────────────────────────────
_defaults = {
    "tg_running":  False,
    "tg_progress": 0,
    "tg_log":      [],
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

if "tg_queue" not in st.session_state:
    st.session_state.tg_queue = _queue_module.Queue()

# Drain queue on every page load
_q = st.session_state.tg_queue
while not _q.empty():
    try:
        _item = _q.get_nowait()
        if _item[0] == "progress":
            st.session_state.tg_progress = _item[1]
        elif _item[0] == "status":
            st.session_state.tg_log.append(_item[1])
        elif _item[0] == "done":
            st.session_state.tg_running  = False
            st.session_state.tg_progress = 100
    except Exception:
        break

# ── Enterprise Theme — Fixed Light, Professional ──────────────────────────────
bg     = "#F0F4F8"
bg2    = "#1E2D3D"
text   = "#0F172A"
muted  = "#64748B"
border = "#E2E8F0"
card   = "#FFFFFF"
accent = "#2563EB"
accent2= "#0EA5E9"
success= "#10B981"
danger = "#EF4444"
warning= "#F59E0B"

st.markdown(f"""<style>
/* ─── Base ─────────────────────────────────────────────────────── */
.stApp {{
    background: {bg};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* ─── Sidebar ───────────────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {{
    background: {bg2} !important;
    border-right: none;
}}
[data-testid="stSidebar"] * {{
    color: #CBD5E1 !important;
}}
[data-testid="stSidebar"] .stRadio > label {{
    color: #F1F5F9 !important;
    font-weight: 600;
    letter-spacing: 0.05em;
    font-size: 0.75rem;
    text-transform: uppercase;
}}
[data-testid="stSidebar"] .stRadio div[data-baseweb="radio"] {{
    background: transparent !important;
    border-radius: 8px;
    margin: 2px 0;
    transition: background 0.15s;
}}
[data-testid="stSidebar"] .stRadio div[data-baseweb="radio"]:hover {{
    background: rgba(37,99,235,0.2) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.08) !important;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: rgba(37,99,235,0.15) !important;
    border: 1px solid rgba(37,99,235,0.4) !important;
    color: #93C5FD !important;
    font-size: 0.8rem !important;
    border-radius: 6px;
    padding: 0.4rem 0.8rem;
    transition: all 0.2s;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(37,99,235,0.35) !important;
    color: #fff !important;
}}

/* ─── Top bar (header area) ──────────────────────────────────────── */
.cs-topbar {{
    background: linear-gradient(135deg, #1E2D3D 0%, #2563EB 100%);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.cs-topbar-title {{
    font-size: 1.5rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.02em;
    margin: 0;
}}
.cs-topbar-sub {{
    font-size: 0.82rem;
    color: rgba(255,255,255,0.7);
    margin-top: 0.2rem;
}}
.cs-badge {{
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}

/* ─── KPI Cards ──────────────────────────────────────────────────── */
.cs-card {{
    background: {card};
    border: 1px solid {border};
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s, transform 0.2s;
    position: relative;
    overflow: hidden;
}}
.cs-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, {accent}, {accent2});
    border-radius: 12px 12px 0 0;
}}
.cs-card:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateY(-1px);
}}
.cs-label {{
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {muted};
    margin-bottom: 0.4rem;
}}
.cs-value {{
    font-size: 1.9rem;
    font-weight: 800;
    color: {text};
    line-height: 1.1;
    letter-spacing: -0.02em;
}}
.cs-sub {{
    font-size: 0.72rem;
    color: {muted};
    margin-top: 0.3rem;
    font-weight: 500;
}}

/* ─── Section headers ────────────────────────────────────────────── */
.cs-section {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {text};
    border-left: 3px solid {accent};
    padding: 0.1rem 0 0.1rem 0.6rem;
    margin: 1.4rem 0 0.8rem 0;
    letter-spacing: -0.01em;
}}

/* ─── Pipeline status rows ───────────────────────────────────────── */
.cs-pipeline-row {{
    background: {card};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.8rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}}
.cs-pipeline-dot {{
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.cs-pipeline-name {{
    font-size: 0.82rem;
    font-weight: 600;
    color: {text};
    flex: 1;
}}
.cs-pipeline-status {{
    font-size: 0.76rem;
    color: {muted};
}}

/* ─── Architecture cards ─────────────────────────────────────────── */
.cs-arch-card {{
    background: {card};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 1rem 1.2rem;
    height: 100%;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
.cs-arch-title {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {accent};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid {border};
}}
.cs-arch-item {{
    font-size: 0.8rem;
    color: {text};
    padding: 0.2rem 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}

/* ─── Table styling ──────────────────────────────────────────────── */
.dataframe {{
    border: none !important;
    font-size: 0.82rem !important;
}}
thead tr th {{
    background: #F8FAFC !important;
    font-weight: 700 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: {muted} !important;
    border-bottom: 2px solid {border} !important;
}}

/* ─── Alerts ─────────────────────────────────────────────────────── */
.stAlert {{
    border-radius: 8px !important;
    font-size: 0.85rem !important;
}}

/* ─── Buttons ────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {accent} 0%, {accent2} 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 1.5rem !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
    transition: all 0.2s !important;
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 4px 16px rgba(37,99,235,0.4) !important;
    transform: translateY(-1px) !important;
}}
.stButton > button[kind="secondary"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}}

/* ─── Tabs ────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: {card};
    border-radius: 8px;
    padding: 0.3rem;
    gap: 0.2rem;
    border: 1px solid {border};
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.82rem;
    color: {muted};
    padding: 0.4rem 1rem;
}}
.stTabs [aria-selected="true"] {{
    background: {accent} !important;
    color: #fff !important;
}}

/* ─── Progress bar ───────────────────────────────────────────────── */
.stProgress > div > div {{
    background: linear-gradient(90deg, {accent}, {accent2}) !important;
    border-radius: 4px;
}}

/* ─── Divider ────────────────────────────────────────────────────── */
hr {{
    border-color: {border} !important;
    margin: 1rem 0 !important;
}}

/* ─── Metrics ────────────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {card};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 0.8rem 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
</style>""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def card(label, value, sub="", color=""):
    c = f"color:{color};" if color else f"color:{text};"
    st.markdown(f"""<div class="cs-card">
    <div class="cs-label">{label}</div>
    <div class="cs-value" style="{c}">{value}</div>
    <div class="cs-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="cs-section">{title}</div>', unsafe_allow_html=True)

def risk_color(p):
    if p >= 0.7: return "#EF4444"
    if p >= 0.4: return "#F59E0B"
    return "#10B981"

def plotly_bg():
    return dict(
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(248,250,252,0.6)",
        font=dict(color=text, family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#E2E8F0", linecolor="#E2E8F0", showgrid=True),
        yaxis=dict(gridcolor="#E2E8F0", linecolor="#E2E8F0", showgrid=True),
    )

def aws_ok(fn):
    try: fn(); return True
    except Exception: return False

def pipeline_row(name, status, ok=True):
    dot_color = "#10B981" if ok else "#94A3B8"
    st.markdown(f"""<div class="cs-pipeline-row">
    <div class="cs-pipeline-dot" style="background:{dot_color};"></div>
    <div class="cs-pipeline-name">{name}</div>
    <div class="cs-pipeline-status">{status}</div>
    </div>""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 0.5rem 0;">
        <div style="font-size:1.1rem;font-weight:800;color:#F1F5F9;letter-spacing:-0.01em;">
            ⚡ COLDSTART
        </div>
        <div style="font-size:0.7rem;color:#64748B;font-weight:500;margin-top:0.2rem;
                    text-transform:uppercase;letter-spacing:0.08em;">
            Cold Start Prevention Platform
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    page = st.radio("Navigate",
        ["Overview", "Live Prediction", "Traffic Generator", "System Status"],
        label_visibility="collapsed")

    st.divider()
    st.markdown('<div style="font-size:0.65rem;color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem;">AWS Connection</div>', unsafe_allow_html=True)

    cw_ok = aws_ok(lambda: aws_client.cloudwatch().list_metrics(Namespace=aws.cloudwatch_namespace))
    db_ok = aws_ok(lambda: aws_client.dynamodb().Table(aws.dynamodb_table).load())

    cw_color = "#10B981" if cw_ok else "#EF4444"
    db_color = "#10B981" if db_ok else "#EF4444"

    st.markdown(f"""
    <div style="display:flex;flex-direction:column;gap:0.4rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;">
            <div style="width:7px;height:7px;border-radius:50%;background:{cw_color};flex-shrink:0;"></div>
            <span style="font-size:0.78rem;color:#CBD5E1;">CloudWatch</span>
            <span style="margin-left:auto;font-size:0.7rem;color:{cw_color};font-weight:600;">
                {'OK' if cw_ok else 'ERR'}
            </span>
        </div>
        <div style="display:flex;align-items:center;gap:0.5rem;">
            <div style="width:7px;height:7px;border-radius:50%;background:{db_color};flex-shrink:0;"></div>
            <span style="font-size:0.78rem;color:#CBD5E1;">DynamoDB</span>
            <span style="margin-left:auto;font-size:0.7rem;color:{db_color};font-weight:600;">
                {'OK' if db_ok else 'ERR'}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown(f"""
    <div style="font-size:0.65rem;color:#475569;line-height:1.8;">
        <div style="color:#64748B;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.4rem;">System Info</div>
        <div>Region: <span style="color:#94A3B8;">{aws.region}</span></div>
        <div>Table: <span style="color:#94A3B8;">{aws.dynamodb_table}</span></div>
        <div>Namespace: <span style="color:#94A3B8;">ColdStart/...</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown(f'<div style="font-size:0.65rem;color:#475569;text-align:center;">v1.0  ·  {datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown("""
    <div class="cs-topbar">
        <div>
            <div class="cs-topbar-title">⚡ COLDSTART — Live Dashboard</div>
            <div class="cs-topbar-sub">Real-time monitoring of the cold start prevention pipeline</div>
        </div>
        <div class="cs-badge">Live</div>
    </div>
    """, unsafe_allow_html=True)

    # Auto-refresh every 30 seconds
    if "last_overview_refresh" not in st.session_state:
        st.session_state.last_overview_refresh = datetime.now()

    elapsed = (datetime.now() - st.session_state.last_overview_refresh).seconds
    if elapsed >= 30:
        st.cache_data.clear()
        st.session_state.last_overview_refresh = datetime.now()
        st.rerun()

    col_refresh, col_time = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh", key="ov_top_refresh", type="primary"):
            st.cache_data.clear()
            st.session_state.last_overview_refresh = datetime.now()
            st.rerun()
    with col_time:
        st.markdown(f'<div style="font-size:0.78rem;color:{muted};padding-top:0.6rem;">Auto-refreshes every 30s &nbsp;·&nbsp; Last: <b>{datetime.now().strftime("%H:%M:%S")}</b> &nbsp;·&nbsp; Next in ~{30 - elapsed}s</div>', unsafe_allow_html=True)

    st.divider()

    # ── Row 1: Live KPI Cards ─────────────────────────────────────────────────
    section("Live System Metrics")

    stats = realtime_data.get_live_stats()
    cw_vals = realtime_data.get_cw_latest_values()
    s3_files = realtime_data.get_s3_recent_files(hours=1)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        total = stats.get("total_requests_1h", 0)
        card("Requests (1h)", str(total), "From DynamoDB", "#2563EB")
    with c2:
        cold_rate = stats.get("cold_start_rate", 0)
        cold_count = stats.get("cold_starts_1h", 0)
        # High cold start rate is expected — traffic generator sends 85% high-risk traffic
        card("Cold Start Rate", f"{cold_rate:.1%}",
             f"{cold_count} cold / {total} total", risk_color(cold_rate))
    with c3:
        rpm = stats.get("requests_per_min", 0)
        card("Req/min", f"{rpm:.1f}", "Avg over last 1h", "#7C3AED")
    with c4:
        # FunctionsWarmed: capped at 3 (auth, profile, search are the only 3 functions)
        fw_cw = cw_vals.get("FunctionsWarmed")
        if fw_cw is not None:
            fw_display = str(int(fw_cw))
            fw_sub = "CloudWatch (last cycle)"
        else:
            # Fallback: count how many endpoints had warm starts
            warm_eps = sum(
                1 for ep in ["auth", "profile", "search"]
                if stats.get(f"{ep}_cold_rate", 1.0) < 1.0
            )
            fw_display = str(warm_eps)
            fw_sub = "Endpoints with warm starts"
        card("Functions Warmed", fw_display, fw_sub, "#10B981")
    with c5:
        ws = cw_vals.get("WarmingSuccessRate")
        if ws is not None:
            ws_display = f"{ws:.1f}%"
            ws_sub = "CloudWatch"
        else:
            # Compute from DynamoDB: warm starts / total
            warm_count = stats.get("warm_starts_1h", 0)
            ws_val = (warm_count / total * 100) if total > 0 else 0
            ws_display = f"{ws_val:.1f}%"
            ws_sub = "Warm starts / total (DynamoDB)"
        card("Warming Success", ws_display, ws_sub, "#10B981")
    with c6:
        card("S3 Files (1h)", str(s3_files),
             "JSON logs uploaded today" if s3_files > 0 else "No uploads yet (1h)", "#F59E0B")

    st.divider()

    # ── Row 2: Risk Status + Pipeline Status ──────────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        section("System Risk Status")
        cold_rate = stats.get("cold_start_rate", 0)
        if cold_rate >= 0.7:
            st.error(f"HIGH RISK — {cold_rate:.1%} cold start rate. Warming recommended.")
        elif cold_rate >= 0.4:
            st.warning(f"MODERATE RISK — {cold_rate:.1%} cold start rate.")
        elif cold_rate > 0:
            st.success(f"LOW RISK — {cold_rate:.1%} cold start rate. System normal.")
        else:
            st.info("No recent traffic data. Run Traffic Generator.")

        # Per-endpoint breakdown
        if stats:
            ep_data = []
            for ep in ["auth", "profile", "search"]:
                count = stats.get(f"{ep}_count", 0)
                cr    = stats.get(f"{ep}_cold_rate", 0)
                ep_data.append({"Endpoint": ep.upper(), "Requests": count,
                                 "Cold Rate": f"{cr:.1%}",
                                 "Status": "HIGH" if cr >= 0.7 else "MED" if cr >= 0.4 else "LOW"})
            if ep_data:
                st.dataframe(pd.DataFrame(ep_data), use_container_width=True, hide_index=True)

    with right_col:
        section("Pipeline Activity")
        tg_running = st.session_state.get("tg_running", False)
        tg_pct     = st.session_state.get("tg_progress", 0)

        pipeline_items = [
            ("EC2 / Traffic Generator",    f"Running ({tg_pct}%)" if tg_running else "Idle",       tg_running),
            ("S3 (Raw JSON Logs)",          f"{s3_files} files uploaded (1h)",                       s3_files > 0),
            ("DynamoDB (ETLFeatureData)",   f"{stats.get('total_requests_1h', 0)} records (1h)",    stats.get("total_requests_1h", 0) > 0),
            ("ML Models (Local)",           "Loaded" if ml_engine.models_available() else "Missing", ml_engine.models_available()),
            ("IntelligentLambdaWarmer",     f"Warmed {int(cw_vals.get('FunctionsWarmed', 0) or 0)} functions", bool(cw_vals.get("FunctionsWarmed"))),
        ]
        for name, status, ok in pipeline_items:
            pipeline_row(name, status, ok)

    st.divider()

    # ── Row 3: Live Charts ────────────────────────────────────────────────────
    section("Live Traffic Charts")

    df = realtime_data.get_recent_traffic(minutes=60)

    if not df.empty and "minute" in df.columns:
        chart_c1, chart_c2 = st.columns(2)

        with chart_c1:
            # Requests per minute over time
            rpm_df = df.groupby("minute").size().reset_index(name="count")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=rpm_df["minute"], y=rpm_df["count"],
                mode="lines+markers", name="Requests",
                line=dict(color="#2563EB", width=2),
                fill="tozeroy", fillcolor="rgba(37,99,235,0.1)"
            ))
            fig.update_layout(
                title="Requests per Minute (Last 1h)",
                height=280, margin=dict(t=40,b=20,l=20,r=20),
                **plotly_bg()
            )
            st.plotly_chart(fig, use_container_width=True)

        with chart_c2:
            # Cold start rate over time
            if "is_cold" in df.columns:
                cold_df = df.groupby("minute").agg(
                    total=("is_cold", "count"),
                    cold=("is_cold", "sum")
                ).reset_index()
                cold_df["cold_rate"] = cold_df["cold"] / cold_df["total"]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=cold_df["minute"], y=cold_df["cold_rate"],
                    mode="lines+markers", name="Cold Start Rate",
                    line=dict(color="#EF4444", width=2),
                    fill="tozeroy", fillcolor="rgba(239,68,68,0.1)"
                ))
                fig2.add_hline(y=0.7, line_dash="dash", line_color="#F59E0B",
                               annotation_text="CBW Threshold (0.7)")
                fig2.update_layout(
                    title="Cold Start Rate Over Time",
                    height=280, margin=dict(t=40,b=20,l=20,r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color=text,
                    xaxis=dict(gridcolor=border),
                    yaxis=dict(gridcolor=border, tickformat=".0%", range=[0, 1]),
                )
                st.plotly_chart(fig2, use_container_width=True)

        # Row 2 charts
        chart_c3, chart_c4 = st.columns(2)

        with chart_c3:
            # Endpoint distribution pie
            if "endpoint" in df.columns:
                ep_counts = df["endpoint"].value_counts().reset_index()
                ep_counts.columns = ["endpoint", "count"]
                fig3 = px.pie(ep_counts, values="count", names="endpoint",
                              title="Traffic by Endpoint",
                              color_discrete_sequence=["#2563EB","#10B981","#F59E0B"])
                fig3.update_layout(height=280, margin=dict(t=40,b=20,l=20,r=20),
                                   **plotly_bg())
                st.plotly_chart(fig3, use_container_width=True)

        with chart_c4:
            # Cold vs Warm bar chart per endpoint
            if "endpoint" in df.columns and "is_cold" in df.columns:
                ep_cold = df.groupby(["endpoint","is_cold"]).size().reset_index(name="count")
                ep_cold["type"] = ep_cold["is_cold"].map({1: "Cold Start", 0: "Warm Start"})
                fig4 = px.bar(ep_cold, x="endpoint", y="count", color="type",
                              title="Cold vs Warm Starts by Endpoint",
                              color_discrete_map={"Cold Start":"#EF4444","Warm Start":"#10B981"},
                              barmode="stack")
                fig4.update_layout(height=280, margin=dict(t=40,b=20,l=20,r=20),
                                   **plotly_bg())
                st.plotly_chart(fig4, use_container_width=True)

    else:
        st.info("No traffic data yet. Start the Traffic Generator to see live charts.")

    st.divider()

    # ── Row 4: ML Predictions — locked to 15-min DataAggregator window ────────
    section("ML Ensemble Prediction (Auto-updates every 15 min)")

    # Compute the current 15-min window boundaries (same as DataAggregator)
    _now_utc = datetime.now(timezone.utc)
    _min_past = _now_utc.minute % 15
    _window_end   = _now_utc - timedelta(minutes=_min_past,
                                         seconds=_now_utc.second,
                                         microseconds=_now_utc.microsecond)
    _window_start = _window_end - timedelta(minutes=15)
    _window_key   = _window_start.strftime("%Y%m%d_%H%M")  # e.g. "20260506_1800"
    _next_min     = 15 - _min_past

    st.caption(
        f"Local XGBoost + Random Forest. Data window: "
        f"{_window_start.astimezone().strftime('%H:%M')} → "
        f"{_window_end.astimezone().strftime('%H:%M')}  |  "
        f"Next update in ~{_next_min} min"
    )

    # Cache is keyed by the 15-min window — predictions are STABLE within a window
    # and only change when a new DataAggregator cycle completes.
    # Refresh Now does NOT change predictions — it only refreshes traffic/KPI data.
    @st.cache_data(ttl=900, show_spinner=False)
    def _pipeline_for_window(window_key: str):
        """Cached per 15-min window. window_key changes every 15 min."""
        return ml_engine.run_full_pipeline()

    # Check if DataAggregator ran a new cycle since last prediction
    last_agg  = ml_engine.get_last_data_aggregator_run_time()
    last_pred = st.session_state.get("last_prediction_ts")
    new_cycle = last_agg is not None and (last_pred is None or last_agg > last_pred)
    if new_cycle:
        st.session_state["last_prediction_ts"] = datetime.now(timezone.utc)

    with st.spinner("Loading predictions for current 15-min window..."):
        pr = _pipeline_for_window(_window_key)

    preds  = pr.get("predictions", [])
    source = pr.get("source", "unknown")

    # Show source badge
    source_labels = {
        "data_aggregator_lambda": "🟢 DataAggregator Lambda",
        "cloudwatch_logs":        "🟡 CloudWatch Logs",
        "dynamodb_last_window":   "🔵 DynamoDB (last window)",
        "dynamodb_direct":        "🔵 DynamoDB (direct)",
    }
    st.caption(f"Source: {source_labels.get(source, source)}")

    if not preds:
        st.warning("No data in last 15-min window. Run Traffic Generator to populate data.")
    else:
        # Gauge charts — one per endpoint
        gauge_cols = st.columns(len(preds))
        for i, r in enumerate(preds):
            with gauge_cols[i]:
                p = r["p_final"]
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=round(p * 100, 1),
                    number={"suffix": "%", "font": {"size": 28}},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar":  {"color": risk_color(p)},
                        "steps": [
                            {"range": [0,  40], "color": "#DCFCE7"},
                            {"range": [40, 70], "color": "#FEF9C3"},
                            {"range": [70,100], "color": "#FEE2E2"},
                        ],
                        "threshold": {"line": {"color": "#EF4444", "width": 3},
                                      "thickness": 0.75, "value": 70}
                    },
                    title={"text": f"{r['endpoint'].upper()}<br><sub>{'WARM' if r['should_warm'] else 'SKIP'}</sub>"},
                ))
                fig_g.update_layout(height=220, margin=dict(t=50,b=0,l=10,r=10), **plotly_bg())
                st.plotly_chart(fig_g, use_container_width=True)

        # Summary table
        rows = [{"Endpoint":   r["endpoint"].upper(),
                 "XGBoost":    f"{r['xgboost']:.1%}",
                 "RF":         f"{r['random_forest']:.1%}",
                 "P_final":    f"{r['p_final']:.1%}",
                 "C":          f"{r['confidence']:.1%}",
                 "Priority":   r["priority"],
                 "CBW":        "WARM" if r["should_warm"] else "SKIP",
                 "Requests":   str(r.get("request_count", 0))} for r in preds]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        warm_eps = [r["endpoint"].upper() for r in preds if r["should_warm"]]
        if warm_eps:
            st.error(f"CBW Gate: WARM — {', '.join(warm_eps)}")
            # Only invoke warmer when a NEW DataAggregator cycle just completed
            if new_cycle:
                warmer_payload = [{"endpoint": r["endpoint"],
                                   "function_name": r["function_name"],
                                   "ensemble_probability": r["p_final"],
                                   "request_count": r.get("request_count", 0)}
                                  for r in preds if r["should_warm"]]
                with st.spinner("Invoking IntelligentLambdaWarmer (new 15-min cycle)..."):
                    wr, err = ml_engine.invoke_intelligent_warmer(warmer_payload)
                if err:
                    st.error(f"❌ IntelligentLambdaWarmer failed: {err}")
                elif wr:
                    s = wr.get("summary", {})
                    st.success(
                        f"✅ IntelligentLambdaWarmer invoked — "
                        f"Warmed: {s.get('functions_warmed','?')} | "
                        f"Success: {s.get('overall_success_rate','?')} | "
                        f"Metrics → CloudWatch"
                    )
                    st.session_state["last_warmer_response"] = wr
        else:
            st.success("CBW Gate: SKIP — All endpoints within safe thresholds.")

    st.divider()
    section("System Architecture")
    a1, a2, a3, a4 = st.columns(4)
    arch_items = [
        ("Data Collection",   accent,   ["EC2 → API Gateway", "Lambda (auth/profile/search)", "S3 JSON Logs", "ETL Processing"]),
        ("ETL Pipeline",      "#7C3AED",["S3 trigger → ETL Lambda", "Feature extraction", "DynamoDB write", "ETLFeatureData table"]),
        ("ML Pipeline",       "#0EA5E9",["EventBridge → DataAggregator", "XGBoost 70% + RF 30%", "P_final + Confidence C", "Every 15 minutes"]),
        ("CBW + Warming",     "#10B981",["P_final ≥ 0.7 AND C ≥ 0.6", "IntelligentLambdaWarmer", "Warms 3 Lambda functions", "CloudWatch metrics"]),
    ]
    for col, (title, color, items) in zip([a1, a2, a3, a4], arch_items):
        with col:
            items_html = "".join(f'<div class="cs-arch-item">→ {i}</div>' for i in items)
            st.markdown(f"""<div class="cs-arch-card">
            <div class="cs-arch-title" style="color:{color};">{title}</div>
            {items_html}
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LIVE PREDICTION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Live Prediction":
    st.markdown("# Live Prediction")
    st.markdown("Run ensemble ML prediction manually or via DataAggregator Lambda.")
    st.divider()

    tab1, tab2 = st.tabs(["Manual Prediction", "Live from DataAggregator"])

    with tab1:
        left, right = st.columns(2, gap="large")
        with left:
            section("Input Parameters")
            hour     = st.slider("Hour of Day", 0, 23, datetime.now().hour)
            day      = st.selectbox("Day of Week", range(7),
                format_func=lambda x: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][x],
                index=datetime.now().weekday())
            traffic  = st.slider("Traffic Intensity", 0.01, 2.0, 1.0, step=0.01)
            endpoint = st.selectbox("Target Endpoint", ["auth", "profile", "search"])
            user_new = st.checkbox("New User")
            mobile   = st.checkbox("Mobile Device")
            run_btn  = st.button("Run Prediction", type="primary", width='stretch')

        with right:
            section("Prediction Results")
            if run_btn:
                feat   = ml_engine.build_feature_vector(hour, day, traffic, endpoint, user_new, mobile)
                result = ml_engine.ensemble_predict(feat)
                if result is None:
                    st.error("Model files not found. Run save_models.py first.")
                else:
                    p, c = result["p_final"], result["confidence"]
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number", value=round(p*100,1),
                        number={"suffix":"%","font":{"size":36}},
                        gauge={"axis":{"range":[0,100]},"bar":{"color":risk_color(p)},
                               "steps":[{"range":[0,40],"color":"#DCFCE7"},
                                        {"range":[40,70],"color":"#FEF9C3"},
                                        {"range":[70,100],"color":"#FEE2E2"}]},
                        title={"text":"Cold Start Probability"}))
                    fig.update_layout(height=260, margin=dict(t=40,b=0,l=20,r=20), **plotly_bg())
                    st.plotly_chart(fig, width='stretch')
                    mc1, mc2, mc3 = st.columns(3)
                    with mc1: card("XGBoost", f"{result['xgboost']:.1%}", "Weight: 70%")
                    with mc2: card("Random Forest", f"{result['random_forest']:.1%}", "Weight: 30%")
                    with mc3: card("Confidence C", f"{c:.1%}", "Model agreement")
                    st.divider()
                    if result["should_warm"]:
                        st.error(f"CBW GATE: WARM — P_final={p:.1%} ≥ 0.7 and C={c:.1%} ≥ 0.6")
                    else:
                        reason = "P_final below threshold" if p < 0.7 else "Confidence below threshold"
                        st.success(f"CBW GATE: SKIP — {reason}.")
            else:
                st.info("Set parameters and click Run Prediction.")

    with tab2:
        section("DataAggregator → Local ML → IntelligentLambdaWarmer")
        st.caption("Auto-updates every 15 min. DataAggregator reads DynamoDB → local models predict → send to warmer.")

        @st.cache_data(ttl=900, show_spinner=False)
        def _live_pipeline():
            return ml_engine.run_full_pipeline()

        last_agg2 = ml_engine.get_last_data_aggregator_run_time()
        last_live = st.session_state.get("last_live_pred_ts")
        if last_agg2 and (last_live is None or last_agg2 > last_live):
            st.cache_data.clear()
            st.session_state["last_live_pred_ts"] = datetime.now(timezone.utc)

        with st.spinner("Running pipeline..."):
            pr2 = _live_pipeline()

        preds2 = pr2.get("predictions", [])
        now2   = datetime.now()
        st.caption(f"Updated: {now2.strftime('%H:%M:%S')}  |  Next: ~{15-now2.minute%15} min  |  Source: {pr2.get('source','unknown')}")

        if st.button("Refresh Now", key="live_refresh"):
            st.cache_data.clear()
            st.rerun()

        if not preds2:
            st.warning("No DynamoDB data in last 15 min. Run Traffic Generator to populate data.")
        else:
            rows2 = [{"Endpoint": r["endpoint"].upper(),
                      "XGBoost (70%)": f"{r['xgboost']:.1%}",
                      "Random Forest (30%)": f"{r['random_forest']:.1%}",
                      "P_final": f"{r['p_final']:.1%}",
                      "Confidence C": f"{r['confidence']:.1%}",
                      "Priority": r["priority"],
                      "Warming Freq": str(r["warming_frequency"]),
                      "CBW": "WARM" if r["should_warm"] else "SKIP",
                      "Requests": str(r.get("request_count", 0))} for r in preds2]
            st.dataframe(pd.DataFrame(rows2), width='stretch', hide_index=True)

            s1, s2, s3 = st.columns(3)
            warm_count = sum(1 for r in preds2 if r["should_warm"])
            with s1: card("Endpoints to Warm", str(warm_count), f"of {len(preds2)}")
            with s2: card("High Priority", str(sum(1 for r in preds2 if r["priority"]=="HIGH")), "P_final ≥ 0.8")
            with s3: card("Total Invocations", str(sum(r["warming_frequency"] for r in preds2)), "Planned")

            st.divider()
            section("Send to IntelligentLambdaWarmer")
            st.caption("Sends predictions to IntelligentLambdaWarmer Lambda. Warmer invokes auth/profile/search based on priority.")

            if st.button("Send to IntelligentLambdaWarmer", type="primary", width='stretch'):
                with st.spinner("Invoking IntelligentLambdaWarmer..."):
                    wr2, err2 = ml_engine.invoke_intelligent_warmer(pr2["warmer_payload"])
                if err2:
                    st.error(f"❌ IntelligentLambdaWarmer failed: {err2}")
                    st.info(
                        "**Troubleshooting:**\n"
                        f"- Check WARMER_FUNCTION in .env = exact Lambda name in AWS\n"
                        f"- Current value: `{aws.warmer_function}`\n"
                        "- Verify IAM role has `lambda:InvokeFunction` permission\n"
                        "- Check Lambda is deployed in same region as dashboard"
                    )
                else:
                    s = wr2.get("summary", {})
                    w1, w2, w3, w4 = st.columns(4)
                    with w1: card("Evaluated", str(s.get("functions_evaluated","—")))
                    with w2: card("Warmed", str(s.get("functions_warmed","—")))
                    with w3: card("Attempts", str(s.get("total_warming_attempts","—")))
                    with w4: card("Success", str(s.get("overall_success_rate","—")))
                    wr_list = wr2.get("warming_results", [])
                    if wr_list:
                        st.dataframe(pd.DataFrame([{
                            "Function": r.get("function_name",""), "Endpoint": r.get("endpoint","").upper(),
                            "Priority": r.get("priority",""), "P_final": f"{r.get('probability',0):.1%}",
                            "Attempts": r.get("attempts",0), "Successful": r.get("successful",0),
                            "Success %": f"{r.get('success_rate',0):.1%}", "Action": r.get("action",""),
                        } for r in wr_list]), width='stretch', hide_index=True)
                    st.success("✅ Warming complete. Metrics published to CloudWatch: ColdStart/IntelligentWarming")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TRAFFIC GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Traffic Generator":
    st.markdown("# Traffic Generator")
    st.markdown("Generates synthetic API traffic and uploads to S3. Same logic as the 2-hour EC2 script.")
    st.divider()

    section("Configuration")
    hours = st.slider("Duration (hours)", 0.25, 4.0, 2.0, 0.25,
                      help="How long to run.", format="%.2f h",
                      disabled=st.session_state.tg_running)
    st.caption(f"~{int(hours*180)} requests  |  ~{int(hours*4)} DataAggregator cycles  |  1 req/sec, 85% high-risk")

    section("Controls")
    b1, b2 = st.columns(2)
    with b1:
        start = st.button("Start", type="primary", disabled=st.session_state.tg_running, width='stretch')
    with b2:
        stop = st.button("Stop", disabled=not st.session_state.tg_running, width='stretch')

    if stop and hasattr(st.session_state, "_stop_list"):
        st.session_state._stop_list[0] = True
        st.session_state.tg_running = False
        st.info("Stop signal sent.")

    pct = st.session_state.tg_progress
    st.progress(pct)
    status_box = st.empty()
    log_box    = st.empty()

    if st.session_state.tg_running:
        status_box.caption(f"Running... {pct}% complete")
    elif pct == 100:
        status_box.caption("Generation complete.")
    elif pct > 0:
        status_box.caption(f"Stopped at {pct}%.")

    if st.session_state.tg_log:
        log_box.text_area("Log", "\n".join(st.session_state.tg_log[-15:]), height=220)

    if start and not st.session_state.tg_running:
        st.session_state.tg_running  = True
        st.session_state.tg_progress = 0
        st.session_state.tg_log      = []
        while not st.session_state.tg_queue.empty():
            try: st.session_state.tg_queue.get_nowait()
            except Exception: break

        _hours     = float(hours)
        _queue_ref = st.session_state.tg_queue
        _stop_list = [False]
        st.session_state._stop_list = _stop_list

        def _run():
            def _on_progress(pct_val, _): _queue_ref.put(("progress", pct_val))
            def _on_status(msg):          _queue_ref.put(("status", msg))
            traffic_generator.run(hours=_hours, on_progress=_on_progress,
                                  on_status=_on_status, stop_flag=lambda: _stop_list[0])
            _queue_ref.put(("done", None))

        threading.Thread(target=_run, daemon=True).start()
        st.success(f"Started {hours}h traffic generation → S3: {aws.s3_bucket}")
        st.rerun()

    if st.session_state.tg_running:
        time.sleep(2.0)   # reduced from 1s to 2s to reduce WebSocket noise
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SYSTEM STATUS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "System Status":
    st.markdown("# System Status")
    st.markdown("AWS service health and configuration overview.")
    st.divider()

    section("AWS Services")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        ok = aws_ok(lambda: aws_client.cloudwatch().list_metrics(Namespace=aws.cloudwatch_namespace))
        card("CloudWatch", "Connected" if ok else "Unavailable", aws.cloudwatch_namespace, "#10B981" if ok else "#EF4444")
    with s2:
        ok = aws_ok(lambda: aws_client.dynamodb().Table(aws.dynamodb_table).load())
        card("DynamoDB", "Connected" if ok else "Unavailable", aws.dynamodb_table, "#10B981" if ok else "#EF4444")
    with s3:
        ok = aws_ok(lambda: aws_client.s3().head_bucket(Bucket=aws.s3_bucket))
        card("S3 Bucket", "Accessible" if ok else "Unavailable", aws.s3_bucket, "#10B981" if ok else "#EF4444")
    with s4:
        ok = aws_ok(lambda: aws_client.lambda_client().get_function(FunctionName=aws.data_aggregator_function))
        card("DataAggregator", "Active" if ok else "Not Found", aws.data_aggregator_function, "#10B981" if ok else "#F59E0B")
    with s5:
        ok = aws_ok(lambda: aws_client.lambda_client().get_function(FunctionName=aws.warmer_function))
        card("IntelligentWarmer", "Active" if ok else "Not Found", aws.warmer_function, "#10B981" if ok else "#F59E0B")

    st.divider()
    section("Configuration")
    st.dataframe(pd.DataFrame({
        "Setting": ["AWS Region","DynamoDB Table","S3 Bucket","DataAggregator Lambda",
                    "Warmer Lambda","CloudWatch Namespace","ML Models"],
        "Value":   [aws.region, aws.dynamodb_table, aws.s3_bucket,
                    aws.data_aggregator_function, aws.warmer_function,
                    aws.cloudwatch_namespace, "models/xgboost_model.pkl + random_forest_model.pkl"],
    }), width='stretch', hide_index=True)

    st.divider()
    section("ML Models")
    xgb_ok = os.path.exists(os.path.join("models", "xgboost_model.pkl"))
    rf_ok  = os.path.exists(os.path.join("models", "random_forest_model.pkl"))
    m1, m2 = st.columns(2)
    with m1:
        card("XGBoost Model", "Loaded" if xgb_ok else "Missing",
             "models/xgboost_model.pkl", "#10B981" if xgb_ok else "#EF4444")
    with m2:
        card("Random Forest Model", "Loaded" if rf_ok else "Missing",
             "models/random_forest_model.pkl", "#10B981" if rf_ok else "#EF4444")
    if not xgb_ok or not rf_ok:
        st.warning("Run `python save_models.py` to train and save the models.")

