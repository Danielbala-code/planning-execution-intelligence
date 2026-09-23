-- Q1: Which critical initiatives need intervention now?
SELECT initiative_id, owner_team, risk_score, recommendation
FROM intervention_queue
WHERE service_tier = 'critical' AND recommendation <> 'MONITOR: no immediate intervention'
ORDER BY risk_score DESC;

-- Q2: Where is velocity outpacing verification capacity?
SELECT owner_team, quarter, AVG(change_volume) AS change_volume,
       AVG(verification_capacity) AS verification_capacity,
       AVG(capacity_headroom_pct) AS headroom
FROM initiative_health
GROUP BY 1, 2
ORDER BY change_volume / NULLIF(verification_capacity, 0) DESC;

-- Q3: Which lower-priority work could release capacity?
SELECT initiative_id, owner_team, risk_score, scope_change_pct
FROM intervention_queue
WHERE priority = 'P2' AND recommendation LIKE 'DEFER%'
ORDER BY risk_score DESC;
