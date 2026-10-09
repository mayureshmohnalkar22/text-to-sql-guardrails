from fastapi import FastAPI, HTTPException
from sqlguard.models import Query, Feedback
from sqlguard import service
from sqlguard.database import schema
app=FastAPI(title="Text-to-SQL Guardrails",version="2.0.0")
@app.get("/")
def root(): return {"project":"Text-to-SQL Guardrails","docs":"/docs","health":"/health"}
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/v1/query")
def query(request:Query): return service.query(request)
@app.get("/v1/schema")
def get_schema(): return schema()
@app.get("/v1/history")
def history(session_id:str="local"): return [r for r in service.records() if r.get("session_id")==session_id]
@app.post("/v1/feedback")
def feedback(f:Feedback):
    try: service.feedback(f.query_id,f.session_id,f.correct)
    except ValueError as e: raise HTTPException(404,str(e))
    return {"saved":True}
