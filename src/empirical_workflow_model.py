"""Time-safe CatBoost workflow-risk backtest on public GitHub metadata.

Only creation-time fields and repository history available before each item's
creation timestamp enter the models. Closure timestamps are labels only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "artifacts" / "empirical"
HORIZON_DAYS = 30


def load_public_records() -> pd.DataFrame:
    rows = []
    for path in sorted(RAW.glob("github_*.json")):
        match = re.match(r"github_(.+)_(issues|prs)_(\d{4})\.json", path.name)
        if not match:
            continue
        repo, work_type, source_year = match.groups()
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("items", []):
            created = pd.Timestamp(item["created_at"])
            closed = pd.Timestamp(item["closed_at"]) if item.get("closed_at") else pd.NaT
            rows.append({
                "record_id": f"{repo}:{work_type}:{item['number']}",
                "repository": repo,
                "work_type": "pull_request" if work_type == "prs" else "issue",
                "number": item["number"],
                "created_at": created,
                "closed_at": closed,
                "source_year": int(source_year),
            })
    data = pd.DataFrame(rows).drop_duplicates("record_id").sort_values(["repository", "created_at", "number"])
    data["resolved_within_30d"] = ((data.closed_at - data.created_at).dt.total_seconds() / 86400 <= HORIZON_DAYS).astype(int)
    data["workflow_risk_30d"] = 1 - data.resolved_within_30d
    return data


def build_time_safe_features(data: pd.DataFrame) -> pd.DataFrame:
    """Build features with an explicit as-of timestamp at work-item creation."""
    features = []
    for repo, group in data.groupby("repository", sort=False):
        history = group.sort_values(["created_at", "number"]).reset_index(drop=True)
        for position, row in history.iterrows():
            as_of = row.created_at
            prior = history.iloc[:position]
            prior_30d = prior[prior.created_at >= as_of - pd.Timedelta(days=30)]
            known_closed = prior[prior.closed_at.notna() & (prior.closed_at <= as_of)]
            mature = prior[prior.created_at + pd.Timedelta(days=HORIZON_DAYS) <= as_of]
            record = row.to_dict()
            record.update({
                "prior_items": len(prior),
                "prior_30d_inflow": len(prior_30d),
                "prior_open_backlog": int(((prior.closed_at.isna()) | (prior.closed_at > as_of)).sum()),
                "prior_closed_by_as_of": len(known_closed),
                "prior_30d_resolution_rate": float(mature.resolved_within_30d.mean()) if len(mature) else np.nan,
                "created_month": as_of.month,
                "created_weekday": as_of.dayofweek,
            })
            features.append(record)
    return pd.DataFrame(features).sort_values("created_at")


def precision_at_k(y_true: np.ndarray, probability: np.ndarray, k: int = 20) -> float:
    k = min(k, len(y_true))
    return float(np.mean(y_true[np.argsort(probability)[-k:]]))


def evaluate(name: str, y_true: pd.Series, probability: np.ndarray) -> dict:
    return {
        "model": name,
        "rows": int(len(y_true)),
        "positive_rate": round(float(y_true.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probability)), 4),
        "brier_score": round(float(brier_score_loss(y_true, probability)), 4),
        "precision_at_20": round(precision_at_k(y_true.to_numpy(), probability, 20), 4),
    }


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = load_public_records()
    features = build_time_safe_features(records)
    # 2025 is untouched during feature-model fitting and hyperparameter selection.
    train = features[features.created_at.dt.year < 2025].copy()
    test = features[features.created_at.dt.year == 2025].copy()
    numeric = ["prior_items", "prior_30d_inflow", "prior_open_backlog", "prior_closed_by_as_of",
               "prior_30d_resolution_rate", "created_month", "created_weekday"]
    categorical = ["repository", "work_type"]
    target = "workflow_risk_30d"
    # Baseline: transparent logistic regression.
    baseline = Pipeline([
        ("prep", ColumnTransformer([
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ])),
        ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=20260923)),
    ])
    baseline.fit(train[numeric + categorical], train[target])
    baseline_probability = baseline.predict_proba(test[numeric + categorical])[:, 1]
    # Primary model: nonlinear CatBoost with shallow, regularised trees to limit overfit.
    cat_train = train[numeric + categorical].copy()
    cat_test = test[numeric + categorical].copy()
    for column in categorical:
        cat_train[column] = cat_train[column].astype(str)
        cat_test[column] = cat_test[column].astype(str)
    cat_train[numeric] = cat_train[numeric].fillna(train[numeric].median())
    cat_test[numeric] = cat_test[numeric].fillna(train[numeric].median())
    cat = CatBoostClassifier(iterations=250, depth=4, learning_rate=0.04, l2_leaf_reg=8,
                             loss_function="Logloss", eval_metric="AUC", verbose=False,
                             random_seed=20260923, auto_class_weights="Balanced")
    cat.fit(cat_train, train[target], cat_features=categorical)
    cat_probability = cat.predict_proba(cat_test)[:, 1]
    test_result = test[["record_id", "repository", "work_type", "created_at", "closed_at", target]].copy()
    test_result["logistic_risk_probability"] = baseline_probability
    test_result["catboost_risk_probability"] = cat_probability
    test_result.to_csv(OUT / "held_out_2025_predictions.csv", index=False)
    metrics = [evaluate("logistic_regression_baseline", test[target], baseline_probability),
               evaluate("catboost_primary", test[target], cat_probability)]
    pd.DataFrame(metrics).to_csv(OUT / "backtest_metrics.csv", index=False)
    importance = pd.DataFrame({"feature": numeric + categorical,
                               "importance": cat.get_feature_importance()}).sort_values("importance", ascending=False)
    importance.to_csv(OUT / "catboost_feature_importance.csv", index=False)
    # Calibration data makes probability quality inspectable rather than assumed.
    calibration = pd.DataFrame({"risk_probability": cat_probability, "outcome": test[target]}).assign(
        risk_bin=lambda x: pd.cut(x.risk_probability, bins=np.linspace(0, 1, 6), include_lowest=True)
    ).groupby("risk_bin", observed=True).agg(predicted_risk=("risk_probability", "mean"), observed_risk=("outcome", "mean"), rows=("outcome", "size")).reset_index()
    calibration.to_csv(OUT / "catboost_calibration.csv", index=False)
    features.to_csv(OUT / "time_safe_feature_table.csv", index=False)
    records[["record_id", "repository", "work_type", "number", "created_at", "closed_at", "workflow_risk_30d"]].to_csv(
        OUT / "public_work_items_clean.csv", index=False
    )
    manifest = {
        "source": "Public GitHub Search API snapshots from spotify/luigi and backstage/backstage",
        "sample_note": "Capped at the first 100 issues and first 100 pull requests per repository-year where available.",
        "as_of_rule": "Only creation-time fields and prior repository history available before created_at are features.",
        "label": "workflow_risk_30d = work item was not closed within 30 days of creation.",
        "train_period": "2022-01-01 to 2024-12-31",
        "held_out_test_period": "2025-01-01 to 2025-12-31",
        "train_rows": int(len(train)), "test_rows": int(len(test)),
    }
    (OUT / "data_and_method_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
