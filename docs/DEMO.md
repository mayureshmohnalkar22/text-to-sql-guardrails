# Portfolio demo (under four minutes)

1. Start template mode. Ask total customer count (20), then West count (5).
2. Ask gross revenue. Show one aggregate result and reviewed-contract verification.
3. Ask net revenue. Explain the discount difference and exclusion of cancelled orders.
4. Ask "What is revenue?". Show clarification; ask "What is profit?" to show abstention.
5. Enter DROP TABLE customers as the SQL override for the count question. Show a block and no fabricated zero metrics. Clear the override and rerun to prove customers remain.
6. Enter a per-order revenue SUM with GROUP BY as an override for total gross revenue. Show contract mismatch flag and skipped execution.
7. In Ollama mode, if the model generates incorrect SQL, expand Original model SQL (replaced). Clearly distinguish model output from reviewed final SQL. Do not claim a model repair occurred unless the record shows repaired=true.
8. Toggle alternative comparison. Show agreement or disagreement and inspect both outputs. Do not claim agreement proves correctness.
9. Mark one result incorrect. Explain that feedback enters a review queue rather than immediately poisoning future examples.
10. Show tests and provider-labeled evaluation report.

Suggested screenshots: one-row gross revenue, West count, ambiguous question, blocked destructive SQL, model repair (if observed), alternative discrepancy (if observed), evaluation summary.

Do not publish template accuracy as unrestricted LLM accuracy. Use model-specific reports with candidate and repair metrics for live-model claims.
