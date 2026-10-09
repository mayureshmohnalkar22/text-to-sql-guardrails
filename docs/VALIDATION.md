# Validation report

Version 2.0.0: 142 pytest tests passed on Python 3.12. Sources pass Python 3.11 grammar validation. GitHub Actions is configured for both versions; CI runs after upload.

Template evaluation: 81/81 question cases passed, including 71/71 result matches. 12/12 destructive/external attacks blocked; no unsafe attack queries executed. 3/3 invented-schema cases blocked. 6/6 known semantic mutations flagged by conservative contract checks.

Regression tests inject wrong grouping, gross/net confusion, missing completed-order filters, wrong tables, bad region filters, false model judgments, malicious alternatives, timeouts and malformed JSON. UI tests cover startup and flagged queries without fabricated zero metrics.

Generation does not read golden fixtures. Expectations include committed result snapshots and manually specified zero-count cases. Repair tests use mocked model candidates. Template coverage is bounded and does not measure unrestricted LLM accuracy.

Live Ollama, Docker Compose and macOS execution have not been tested here. One FastAPI/Starlette TestClient deprecation warning is non-failing. The Streamlit width warning is fixed.
