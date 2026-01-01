---
# EXPERIMENT TEMPLATE
# Copy this file and rename it (e.g., 2026-01-my-experiment.md)
# Then fill in your experiment details below.

title: My Experiment Title
hypothesis: "State your hypothesis here (e.g., Question-based titles get 2x more clicks)"
status: running  # running | completed | cancelled
start_date: 2026-01-01
end_date:   # Fill when experiment ends
posts:
  - path-to-post-1  # Post paths (without /p/ prefix)
  - path-to-post-2
track_metrics:
  - pageviews
  - bounce_rate
  - avg_time_on_page
baseline:
  avg_pageviews: 50  # Your baseline metrics for comparison
  avg_bounce_rate: 80
# These are filled when experiment completes:
# results_summary: "Brief summary of results"
# winner: treatment  # treatment | control | null
---

## Experiment Design

Describe your experiment setup here:
- **Control**: What you're comparing against
- **Treatment**: What you're testing

## Progress Notes

- YYYY-MM-DD: Started experiment
- YYYY-MM-DD: Observation notes...

## Results

<!-- 
When experiment completes, add results here or use the API:
curl -X POST "http://localhost:2323/analytics/api/experiments/YOUR-FILE/complete" \
  -H "Content-Type: application/json" \
  -d '{"results_summary": "Treatment won by 45%", "winner": "treatment"}'
-->

