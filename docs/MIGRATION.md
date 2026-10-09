# Upgrade from v1

1. Stop the old Uvicorn and Streamlit processes with Control+C in their separate terminals.
2. Extract v2 into a fresh folder and open that folder in VS Code.
3. Create a new .venv and install requirements.txt. Copy .env.example to .env.
4. Seed and run both services using README commands.
5. Start with MODEL_PROVIDER=template. Enable Ollama only after template examples and tests work.
6. Do not copy old Python files, model edits, logs, or .venv over v2. The sample database can be reseeded locally.

Changed behavior: supported intents have reviewed contracts; mismatching generated SQL is replaced transparently; mismatching overrides are flagged; percentages were removed; non-executed queries no longer display zero rows/time; alternative disagreement is advisory for contract results; feedback requires review.
