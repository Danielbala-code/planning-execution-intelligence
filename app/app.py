import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".." / "work" / "vendor"))
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Planning & Execution Intelligence", layout="wide")
st.title("Planning & Execution Intelligence")
st.caption("Synthetic prototype • explainable intervention triage • not Spotify internal data")
data = pd.read_csv(ROOT / "artifacts" / "intervention_queue.csv")
empirical = pd.read_csv(ROOT / "artifacts" / "empirical" / "backtest_metrics.csv")
st.subheader("Layer 1 - empirical workflow-risk backtest")
st.dataframe(empirical, use_container_width=True, hide_index=True)
st.caption("2022-2024 training; 2025 held-out test. The simpler logistic baseline ranked risk better than CatBoost in this capped public-data sample.")
st.divider()
st.subheader("Layer 2 - synthetic capacity decision scenario")
critical = data[data.service_tier == "critical"]
a, b, c = st.columns(3)
a.metric("Initiatives", len(data))
b.metric("Critical initiatives", len(critical))
c.metric("High-risk initiatives", int((data.risk_score >= 55).sum()))
st.subheader("Intervention queue")
st.dataframe(data[["initiative_id", "owner_team", "priority", "service_tier", "risk_score", "recommendation"]], use_container_width=True, hide_index=True)
left, right = st.columns(2)
with left:
    st.plotly_chart(px.bar(data.sort_values("risk_score"), x="risk_score", y="initiative_id", color="service_tier", orientation="h", title="Explainable delivery risk"), use_container_width=True)
with right:
    team = data.groupby("owner_team", as_index=False).agg(change_volume=("change_volume", "mean"), verification_capacity=("verification_capacity", "mean"), headroom=("capacity_headroom_pct", "mean"))
    st.plotly_chart(px.scatter(team, x="verification_capacity", y="change_volume", size="headroom", color="owner_team", title="Velocity versus verification capacity"), use_container_width=True)
st.info("Use the Context Pack before automating answers: every leadership question has an approved metric definition and SQL pattern.")
