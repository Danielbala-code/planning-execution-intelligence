# Empirical Model Selection

## Held-out test

- Training period: 2022–2024
- Untouched test period: 2025
- Outcome: not closed within 30 days of creation
- Source: capped public GitHub issue and pull-request metadata from `spotify/luigi` and `backstage/backstage`

## Result

The logistic regression baseline ranked held-out risk better than CatBoost (AUC 0.774 versus 0.750; precision among the 20 highest-risk items 0.85 versus 0.80). CatBoost had a slightly lower Brier score (0.197 versus 0.202).

## Decision

Use logistic regression as the Layer 1 champion for this V1. Retain CatBoost as a tested challenger, not as a forced production choice.

## Limits

This is a capped, repository-specific public-data sample. It supports a reproducible method demonstration, not general claims about all software organisations. Work type was the strongest CatBoost feature, so cross-project generalisation requires more diverse data before use in a real deployment.
