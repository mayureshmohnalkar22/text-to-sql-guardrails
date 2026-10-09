import sys, json, uuid, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
import httpx
from sqlguard.paths import DATA, ROOT
from dotenv import load_dotenv
load_dotenv(ROOT/".env")
st.set_page_config(page_title="Text-to-SQL Guardrails v2",page_icon="🛡️",layout="wide")
API=os.getenv("API_URL","http://localhost:8000")
st.title("Text-to-SQL Guardrails v2")
st.caption("Ask a retail question. Inspect generated SQL, reviewed contracts, safety checks, and results.")
if "session" not in st.session_state: st.session_state.session=uuid.uuid4().hex

def request(method,path,**kw):
    try:
        r=httpx.request(method,API+path,timeout=300,**kw); r.raise_for_status(); return r.json()
    except Exception as e: st.error(f"API unavailable: {e}. Start python -m uvicorn app.main:app first."); return None
with st.sidebar:
    st.header("Explore")
    st.caption("Configured provider: "+os.getenv("MODEL_PROVIDER","template"))
    examples=json.loads((DATA/"golden.json").read_text())
    selected=st.selectbox("Example question",[x["question"] for x in examples[:12]])
    if st.button("Inspect schema"):
        s=request("GET","/v1/schema")
        if s: st.json(s)
    st.caption("Local portfolio app. Session IDs partition history; they are not authentication.")
with st.form("query_form"):
    question=st.text_input("Your question",value=selected)
    validate=st.checkbox("Compare a second SQL approach",False)
    with st.expander("Edit SQL or test a guardrail"):
        st.caption("Leave empty for automatic generation. Example text below is a placeholder.")
        override=st.text_area("Optional SQL override",placeholder="Example only: SELECT * FROM customers")
    submitted=st.form_submit_button("Run question",type="primary")
if submitted:
    st.session_state.pop("result",None)
    with st.spinner("Generating and validating SQL…"):
        result=request("POST","/v1/query",json={"question":question,"session_id":st.session_state.session,"sql_override":override.strip() or None,"validate_alternative":validate})
    if result: st.session_state.result=result
if "result" in st.session_state:
    r=st.session_state.result
    st.caption("Result for submitted question: "+r["question"]+" · "+r["timestamp"])
    st.subheader(r["status"].title())
    if r["status"]=="clarification": st.warning(r["reason"]); st.write(r["choices"])
    elif r["status"] in ["blocked","error","unanswerable"]: st.error(r["reason"])
    else:
        if r.get("reason"): st.warning(r["reason"])
        st.write("**Verification:** "+r.get("verification_level","Not verified"))
        if r.get("executed"):
            a,b=st.columns(2); a.metric("Rows returned",r["row_count"]); b.metric("Execution time",f'{r["execution_ms"]} ms')
        else: st.info("Query was not executed. No row count or execution time is available.")
        st.code(r.get("sql",""),language="sql")
        for msg in r.get("warnings",[]): st.warning(msg)
        if "rows" in r:
            st.dataframe(r["rows"],width="stretch")
            st.download_button("Download results",json.dumps(r["rows"],indent=2),"results.json")
        if r.get("repaired"):
            with st.expander("Original model SQL (replaced)"): st.code(r["candidate_sql"],language="sql")
        if r.get("alternative",{}).get("status")=="disagreement":
            with st.expander("Alternative result disagreement"):
                st.code(r["alternative"]["sql"],language="sql"); st.dataframe(r["alternative"]["rows"],width="stretch")
        with st.expander("Validation evidence and query plan"): st.json(r)
        if r["status"]=="success":
            x,y=st.columns(2)
            for col,label,correct in [(x,"Correct",True),(y,"Incorrect",False)]:
                if col.button(label):
                    response=request("POST","/v1/feedback",json={"query_id":r["id"],"session_id":st.session_state.session,"correct":correct})
                    if response: st.success("Feedback saved for review")
with st.expander("Session history"):
    if st.button("Refresh history"): st.json(request("GET","/v1/history",params={"session_id":st.session_state.session}))
