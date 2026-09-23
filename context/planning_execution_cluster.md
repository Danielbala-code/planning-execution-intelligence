# Planning & Execution Context Pack

## Purpose

Support quarterly capacity decisions. This cluster owns metrics for initiative delivery, capacity, quality gates, and dependencies.

## Authoritative tables

| Table | Grain | Owner | Caveat |
|---|---|---|---|
| `initiatives` | initiative × quarter | Portfolio Insights | Outcome values are synthetic in this prototype. |
| `work_items` | work item | Delivery Operations | Completion is activity, not value. |
| `capacity_snapshots` | team × quarter | Workforce Planning | Capacity is planned, not time-sheet data. |
| `dependencies` | dependency | Portfolio Insights | A dependency can be on track but still become a future risk. |

## Approved metric definitions

- **Risk score:** transparent weighted triage score using completion, quality gates, scope change, blocked dependencies, and change-to-verification load.
- **Verification pressure:** change volume divided by twice verification capacity. It is an early warning, not a quality verdict.
- **Capacity headroom:** capacity available after planned allocation; it must be interpreted alongside service tier.

## Guardrails

Do not state that a score predicts failure. Do not use these synthetic results as organisation-level evidence. Always show underlying evidence and the refresh date.
