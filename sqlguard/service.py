import json, uuid, threading, os, math
from datetime import datetime, timezone
import sqlglot
from .database import schema
from .provider import generate, judge
from .intents import resolve
from .safety import guard, Blocked
from .execution import execute
from .paths import DATA
LOCK=threading.Lock()
AUDIT=DATA/"history.jsonl"

def records():
    with LOCK:
        return [json.loads(x) for x in AUDIT.read_text().splitlines() if x.strip()] if AUDIT.exists() else []

def save(record):
    with LOCK:
        AUDIT.parent.mkdir(exist_ok=True)
        with AUDIT.open("a") as f: f.write(json.dumps(record,default=str)+"\n")

def feedback(query_id,session,correct):
    found=next((r for r in records() if r.get("id")==query_id and r.get("session_id")==session and r.get("status")=="success"),None)
    if not found: raise ValueError("Successful query not found in this session")
    save({"event":"feedback","query_id":query_id,"session_id":session,"correct":correct,"question":found["question"],"sql":found["sql"],"needs_review":True})
    if not correct:
        with LOCK:
            with (DATA/"feedback_cases.jsonl").open("a") as f: f.write(json.dumps({"question":found["question"],"candidate_sql":found["sql"],"needs_review":True})+"\n")
    # User votes are never automatically promoted into trusted model examples.

def equivalent(a,b,ordered=False):
    def row_equal(x,y):
        if len(x)!=len(y): return False
        for l,r in zip(x,y):
            if isinstance(l,(int,float)) and isinstance(r,(int,float)):
                if not math.isclose(l,r,rel_tol=1e-9,abs_tol=1e-6): return False
            elif l!=r: return False
        return True
    if len(a)!=len(b): return False
    left=[list(x.values()) for x in a]; right=[list(x.values()) for x in b]
    if ordered: return all(row_equal(x,y) for x,y in zip(left,right))
    # Multiset comparison preserves duplicate counts, tolerates numeric roundoff.
    for x in left:
        index=next((i for i,y in enumerate(right) if row_equal(x,y)),None)
        if index is None: return False
        right.pop(index)
    return True

def sanity(result):
    issues=[]
    rows=result["rows"]
    if not rows: issues.append("No rows matched; this may be a valid empty result")
    for col in result["columns"]:
        if rows and sum(x[col] is None for x in rows)/len(rows)>0.5: issues.append(f"Column {col} is more than 50% NULL; inspect join/filter/empty aggregate")
        if any(isinstance(x[col],(int,float)) and x[col]<0 for x in rows) and any(k in col.lower() for k in ["revenue","count","quantity"]): issues.append(f"Unexpected negative values in {col}")
    return issues

def query(request):
    r={"id":str(uuid.uuid4()),"session_id":request.session_id,"question":request.question,"timestamp":datetime.now(timezone.utc).isoformat(),"provider":os.getenv("MODEL_PROVIDER","template"),"warnings":[],"executed":False}
    try:
        q=request.question.lower()
        if "revenue" in q and not any(x in q for x in ["gross","net"]):
            r.update(status="clarification",reason="Choose gross (before discounts) or net (after discounts); completed orders only.",choices=["What is gross revenue?","What is net revenue?"]); return r
        if any(x in q for x in ["profit","salary","weather"]):
            r.update(status="unanswerable",reason="The retail database does not contain this information."); return r
        s=schema(); contract=resolve(request.question)
        examples=[{"question":"How many customers are there?","sql":"SELECT COUNT(*) FROM customers"},{"question":"What is gross revenue?","sql":"SELECT SUM(i.quantity*i.unit_price) FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.status='completed'"},{"question":"Show order counts by region","sql":"SELECT c.region,COUNT(*) FROM customers c JOIN orders o ON c.id=o.customer_id GROUP BY c.region"}]
        if not contract and os.getenv("MODEL_PROVIDER","template") in {"template","demo"}:
            r.update(status="unanswerable",reason="Outside the reviewed retail question contracts. Use one of the examples or enable Ollama."); return r
        override=request.sql_override.strip() if request.sql_override else ""
        g=generate(request.question,s,examples) if not override else None
        candidate,tables=guard(override or g.sql,s)
        r.update(candidate_sql=candidate,sql=candidate,tables=tables,explanation=g.explanation if g else "User SQL override",repaired=False)
        if contract:
            reference,_=guard(contract.sql,s)
            # Execute reviewed SQL for supported intents. No LLM judgment may overrule it.
            # A generated query is replaced when its AST differs; overrides are never silently repaired.
            same=sqlglot.parse_one(candidate,read="duckdb")==sqlglot.parse_one(reference,read="duckdb")
            r["verification"]={"method":"reviewed_intent_contract","intent":contract.intent,"candidate_matches_contract_ast":same,"reference_sql":reference}
            if override and not same:
                r.update(status="flagged",reason="Edited SQL differs from the reviewed contract. Clear the override to use the verified query."); return r
            if not same:
                r.update(sql=reference,repaired=True)
                r["warnings"].append("Model SQL differed from the reviewed contract; the reviewed SQL was executed instead. Original SQL is retained for inspection.")
            r["verification_level"]="Reviewed retail contract"
        else:
            j=judge(request.question,candidate,s)
            r["verification"]={"method":"llm_judge",**(j.model_dump() if j else {})}
            if not j or j.alignment<0.6:
                r.update(status="flagged",reason="Open-ended SQL lacks sufficient semantic alignment evidence."); return r
            r["verification_level"]="Model judgment only; review the result"
        result=execute(r["sql"]); r.update(result,executed=True)
        r["warnings"]+=sanity(result)
        r["checks"]={"syntax_schema":"passed","read_only":"passed","semantic":r["verification_level"],"alternative":"not requested"}
        if request.validate_alternative and not override:
            try:
                alt=generate(request.question,s,examples,True); alt_sql,_=guard(alt.sql,s)
                if sqlglot.parse_one(alt_sql)==sqlglot.parse_one(r["sql"]):
                    r["alternative"]={"sql":alt_sql,"status":"identical","agreement":None}; r["checks"]["alternative"]="identical; no independent evidence"
                else:
                    other=execute(alt_sql)
                    ordered=bool(sqlglot.parse_one(r["sql"]).args.get("order"))
                    agreement=equivalent(result["rows"],other["rows"],ordered=ordered)
                    r["alternative"]={"sql":alt_sql,"rows":other["rows"],"agreement":agreement,"status":"agreement" if agreement else "disagreement"}
                    r["checks"]["alternative"]="agrees" if agreement else "disagrees"
                    if not agreement: r["warnings"].append("Alternative disagrees with the primary result. Inspect both; the reviewed contract remains the authoritative result for supported questions.")
            except Exception as e:
                r["alternative"]={"status":"failed","reason":str(e),"agreement":None}; r["checks"]["alternative"]="failed"
                r["warnings"].append("Alternative validation failed; primary result is retained with this limitation.")
        if not contract and r.get("alternative",{}).get("agreement") is False:
            r.update(status="flagged",reason="Open-ended approaches disagree; manual review required.")
        else: r["status"]="success"
    except Blocked as e: r.update(status="blocked",reason=str(e))
    except Exception as e: r.update(status="error",reason=str(e))
    finally: save(r)
    return r
