# Planning & Execution Intelligence

**Question:** At a quarterly planning checkpoint, how should leaders allocate constrained capacity across strategic delivery, quality/reliability, and maintenance work so critical outcomes remain protected as change velocity rises?

This is a fictional, reproducible decision-support prototype. It uses no Spotify data, branding, customer data, or claims about Spotify operations.

## What it delivers

- Spotify **Luigi** pipeline: synthetic data → validation → DuckDB marts → decision brief.
- Public GitHub workflow backtest: logistic-regression baseline versus CatBoost challenger, evaluated on an untouched future year.
- Explainable intervention queue: **protect, intervene, re-scope, defer, or monitor**.
- Streamlit control tower.
- Backstage-compatible `catalog-info.yaml`.
- Context pack with metric definitions, caveats, and approved question/SQL pairs.

## Why this design

The architecture is inspired by Spotify Engineering's public discussion of trusted data context, ownership, quality guardrails, prioritised workloads, observability, and recovery. It is deliberately generalisable to any complex product or platform organisation.

## Evidence and scenario layers

`artifacts/empirical/` contains a time-safe public GitHub workflow-risk backtest. The synthetic capacity scenario is separate: it demonstrates how a leader could act on a risk signal but does not train or validate the empirical model. See `context/layer_linkage.md`.

## Run

```powershell
python -m pip install -r requirements.txt
python src/pipeline.py PublishBrief --local-scheduler
python src/empirical_workflow_model.py
streamlit run app/app.py
```

`src/empirical_workflow_model.py` expects the documented public GitHub API snapshots. They are deliberately ignored by Git because API responses may contain unnecessary public profile fields; only the cleaned work-item table is retained in the empirical artifacts.

## Key limitation

The operational patterns are encoded into synthetic data to demonstrate the product. Risk scores are triage aids, not predictive or causal claims.
