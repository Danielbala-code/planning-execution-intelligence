# How the Two Layers Connect

## Layer 1: evidence

The public GitHub backtest estimates an item-level probability of remaining unresolved after 30 days. Its only purpose is to rank workflow risk using historic, time-safe data.

## Layer 2: scenario

The synthetic scenario accepts a **workflow-risk band** as an external signal. It then combines that signal with fictional service tier, capacity headroom, scope change, and dependency state to choose an action.

| Workflow signal | Synthetic operating context | Action |
|---|---|---|
| High | Critical work and low headroom | Protect capacity and investigate immediately. |
| High | Standard work | Re-scope or defer. |
| Medium | Weak quality gates | Add verification capacity. |
| Low | Adequate headroom | Monitor. |

The synthetic data does not train, tune, or validate the Layer 1 model. It only illustrates the decision policy a leader could use after receiving a validated risk signal.
