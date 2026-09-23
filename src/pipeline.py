"""Spotify-Luigi pipeline for a reproducible planning-and-execution prototype."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import luigi
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "artifacts"
RNG = np.random.default_rng(20260923)


def make_data() -> None:
    """Create fictional operational data; all values are deliberately synthetic."""
    raw = DATA / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    teams = pd.DataFrame(
        [("Atlas", "Core platform"), ("Beacon", "Creator experience"),
         ("Compass", "Consumer product"), ("Delta", "Data platform"),
         ("Ember", "Reliability engineering"), ("Forge", "Monetisation")],
        columns=["team", "domain"],
    )
    quarters = ["2026-Q1", "2026-Q2", "2026-Q3"]
    initiatives = []
    for n in range(1, 31):
        priority = "P0" if n <= 6 else ("P1" if n <= 17 else "P2")
        tier = "critical" if n in {1, 4, 7, 12, 18} else ("strategic" if priority != "P2" else "standard")
        initiatives.append({
            "initiative_id": f"INIT-{n:02d}", "initiative": f"Initiative {n:02d}",
            "owner_team": teams.team.iloc[(n - 1) % len(teams)], "quarter": quarters[(n - 1) % 3],
            "priority": priority, "service_tier": tier,
            "work_class": ["feature", "quality_reliability", "maintenance"][n % 3],
            "outcome_target": int(RNG.integers(8, 25)),
            "outcome_progress": int(RNG.integers(2, 23)),
            "scope_change_pct": round(float(RNG.uniform(0, 0.38)), 2),
        })
    initiatives = pd.DataFrame(initiatives)
    # Deliberate decision case: critical work faces high scope change and weak outcome progress.
    initiatives.loc[initiatives.initiative_id == "INIT-04", ["scope_change_pct", "outcome_progress"]] = [0.42, 5]
    initiatives.loc[initiatives.initiative_id == "INIT-07", ["scope_change_pct", "outcome_progress"]] = [0.35, 4]

    capacity = []
    for quarter in quarters:
        for team in teams.team:
            planned = int(RNG.integers(130, 190))
            unplanned = int(RNG.integers(8, 42))
            verification = int(RNG.integers(18, 46))
            change = int(RNG.integers(24, 72))
            capacity.append({"team": team, "quarter": quarter, "planned_capacity": planned,
                             "allocated_capacity": planned - int(RNG.integers(-8, 18)),
                             "unplanned_capacity": unplanned, "verification_capacity": verification,
                             "change_volume": change, "capacity_headroom_pct": round(float(RNG.uniform(0.08, 0.35)), 2)})
    capacity = pd.DataFrame(capacity)
    capacity.loc[(capacity.team == "Atlas") & (capacity.quarter == "2026-Q2"),
                 ["unplanned_capacity", "verification_capacity", "change_volume", "capacity_headroom_pct"]] = [52, 16, 88, 0.06]

    work = []
    for _, initiative in initiatives.iterrows():
        for item in range(6):
            planned = int(RNG.integers(5, 17))
            actual = planned + int(RNG.integers(-3, 8))
            status = "done" if RNG.random() > 0.26 else "in_progress"
            work.append({"work_item_id": f"{initiative.initiative_id}-W{item+1}", "initiative_id": initiative.initiative_id,
                         "team": initiative.owner_team, "quarter": initiative.quarter, "planned_effort": planned,
                         "actual_effort": actual, "status": status, "is_unplanned": bool(RNG.random() < 0.18),
                         "quality_gate_passed": bool(RNG.random() > 0.15)})
    work = pd.DataFrame(work)
    work.loc[work.initiative_id == "INIT-04", "quality_gate_passed"] = False

    dependencies = []
    for n in range(35):
        downstream = initiatives.iloc[n % len(initiatives)]
        upstream = initiatives.iloc[(n * 7 + 4) % len(initiatives)]
        dependencies.append({"dependency_id": f"DEP-{n+1:02d}", "upstream_initiative_id": upstream.initiative_id,
                             "downstream_initiative_id": downstream.initiative_id,
                             "status": "blocked" if n % 6 == 0 else "on_track", "delay_days": 14 if n % 6 == 0 else int(RNG.integers(0, 5))})
    dependencies = pd.DataFrame(dependencies)
    for name, frame in {"teams": teams, "initiatives": initiatives, "capacity_snapshots": capacity,
                        "work_items": work, "dependencies": dependencies}.items():
        frame.to_csv(raw / f"{name}.csv", index=False)


class GenerateSyntheticData(luigi.Task):
    def output(self): return luigi.LocalTarget(str(DATA / "raw" / "initiatives.csv"))
    def run(self): make_data()


class ValidateData(luigi.Task):
    def requires(self): return GenerateSyntheticData()
    def output(self): return luigi.LocalTarget(str(OUT / "validation.json"))
    def run(self):
        initiatives = pd.read_csv(DATA / "raw" / "initiatives.csv")
        work = pd.read_csv(DATA / "raw" / "work_items.csv")
        checks = {"initiative_ids_unique": bool(initiatives.initiative_id.is_unique),
                  "all_work_has_initiative": bool(work.initiative_id.isin(initiatives.initiative_id).all()),
                  "valid_scope_range": bool(initiatives.scope_change_pct.between(0, 1).all())}
        if not all(checks.values()): raise ValueError(f"Data contract failed: {checks}")
        OUT.mkdir(exist_ok=True)
        with self.output().open("w") as f: json.dump(checks, f, indent=2)


class BuildMarts(luigi.Task):
    def requires(self): return ValidateData()
    def output(self): return luigi.LocalTarget(str(OUT / "initiative_health.csv"))
    def run(self):
        OUT.mkdir(exist_ok=True)
        con = duckdb.connect(str(OUT / "planning_execution.duckdb"))
        for table in ["initiatives", "capacity_snapshots", "work_items", "dependencies"]:
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{(DATA / 'raw' / (table + '.csv')).as_posix()}')")
        con.execute("""
          CREATE OR REPLACE TABLE initiative_health AS
          WITH work AS (SELECT initiative_id, AVG(CASE WHEN status='done' THEN 1.0 ELSE 0 END) completion_rate,
                            AVG(CASE WHEN quality_gate_passed THEN 1.0 ELSE 0 END) quality_gate_rate
                         FROM work_items GROUP BY 1),
          deps AS (SELECT downstream_initiative_id initiative_id, COUNT(*) dependency_count,
                          SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) blocked_dependencies,
                          MAX(delay_days) max_delay_days FROM dependencies GROUP BY 1)
          SELECT i.*, w.completion_rate, w.quality_gate_rate, COALESCE(d.dependency_count,0) dependency_count,
                 COALESCE(d.blocked_dependencies,0) blocked_dependencies, COALESCE(d.max_delay_days,0) max_delay_days,
                 c.unplanned_capacity, c.verification_capacity, c.change_volume, c.capacity_headroom_pct,
                 ROUND(100 * (0.25*(1-w.completion_rate) + 0.18*(1-w.quality_gate_rate) +
                   0.18*LEAST(i.scope_change_pct/0.4,1) + 0.14*LEAST(COALESCE(d.blocked_dependencies,0)/2.0,1) +
                   0.15*LEAST(c.change_volume/NULLIF(c.verification_capacity*2,0),1)),1) AS risk_score
          FROM initiatives i JOIN work w USING(initiative_id)
          JOIN capacity_snapshots c ON i.owner_team=c.team AND i.quarter=c.quarter LEFT JOIN deps d USING(initiative_id)
        """)
        con.execute("""
          CREATE OR REPLACE TABLE intervention_queue AS
          SELECT *, CASE WHEN service_tier='critical' AND risk_score >= 40 THEN 'PROTECT: reserve capacity and address quality gates'
                         WHEN risk_score >= 65 THEN 'INTERVENE: add verification capacity'
                         WHEN scope_change_pct >= .30 THEN 'RE-SCOPE: reduce commitment'
                         WHEN priority='P2' AND risk_score >= 45 THEN 'DEFER: release capacity'
                         ELSE 'MONITOR: no immediate intervention' END AS recommendation
          FROM initiative_health ORDER BY risk_score DESC
        """)
        con.execute("COPY initiative_health TO ? (HEADER, DELIMITER ',')", [str(OUT / "initiative_health.csv")])
        con.execute("COPY intervention_queue TO ? (HEADER, DELIMITER ',')", [str(OUT / "intervention_queue.csv")])
        con.close()


class PublishBrief(luigi.Task):
    def requires(self): return BuildMarts()
    def output(self): return luigi.LocalTarget(str(OUT / "planning_execution_brief.md"))
    def run(self):
        queue = pd.read_csv(OUT / "intervention_queue.csv")
        urgent = queue[queue.recommendation != "MONITOR: no immediate intervention"].head(5)
        lines = ["# Planning & Execution Insight Brief", "", "## Decision", "",
                 "Rebalance capacity toward critical initiatives with weak delivery confidence; pause lower-priority work where it protects verification capacity and delivery headroom.",
                 "", "## Recommended interventions", ""]
        for _, row in urgent.iterrows():
            lines.append(f"- **{row.initiative_id} - {row.recommendation}.** Risk {row.risk_score:.1f}/100; "
                         f"scope change {row.scope_change_pct:.0%}; blocked dependencies {row.blocked_dependencies}; "
                         f"quality-gate pass rate {row.quality_gate_rate:.0%}.")
        lines += ["", "## Interpretation", "", "This is a fictional, reproducible scenario. The score is an explainable triage aid, not a causal model or a claim about any real organisation."]
        with self.output().open("w") as f: f.write("\n".join(lines))


if __name__ == "__main__":
    luigi.run()
