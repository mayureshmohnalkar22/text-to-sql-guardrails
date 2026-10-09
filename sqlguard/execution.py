import json, os, time, threading
import duckdb
from .database import DB
from .safety import Blocked

EXECUTION_LOCK=threading.Lock()

def execute(sql):
    with EXECUTION_LOCK:
        return _execute(sql)

def _execute(sql):
    c=duckdb.connect(str(DB),read_only=True)
    c.execute("SET enable_external_access=false")
    c.execute("SET threads=2")
    c.execute("SET memory_limit='256MB'")
    timer=threading.Timer(float(os.getenv("QUERY_TIMEOUT","5")),c.interrupt)
    started=time.perf_counter()
    timer.start()
    try:
        c.execute("BEGIN TRANSACTION READ ONLY")
        plan=json.loads(c.execute("EXPLAIN (FORMAT JSON) "+sql).fetchone()[1])
        estimates=[]
        def visit(nodes):
            for n in nodes:
                info=n.get("extra_info",{})
                if "SCAN" in n.get("name",""):
                    estimates.append(int(info.get("Estimated Cardinality","0")))
                visit(n.get("children",[]))
        visit(plan)
        if sum(estimates)>int(os.getenv("MAX_SCAN_ROWS","100000")): raise Blocked("Estimated scan exceeds configured budget")
        df=c.execute(sql).fetchdf()
        rows=json.loads(df.to_json(orient="records",date_format="iso"))
        return {"rows":rows,"columns":list(df.columns),"row_count":len(rows),"execution_ms":round((time.perf_counter()-started)*1000,2),"explain":plan,"estimated_scan_rows":sum(estimates)}
    finally:
        timer.cancel()
        try: c.execute("ROLLBACK")
        finally: c.close()
