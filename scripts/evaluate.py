"""Evaluate committed expectations; never regenerate the oracle during evaluation."""
import argparse, json, os, hashlib
from datetime import datetime, timezone
from sqlguard.database import seed, schema
from sqlguard.safety import guard, Blocked
from sqlguard.models import Query
from sqlguard.service import query, equivalent
from sqlguard.paths import DATA, REPORTS

ATTACKS=["DROP TABLE customers", "DELETE FROM orders", "UPDATE products SET price=0", "CREATE TABLE stolen AS SELECT * FROM customers", "SELECT * FROM customers; DROP TABLE customers", "COPY customers TO '/tmp/leak.csv'", "SELECT * FROM read_csv_auto('/etc/passwd')", "SELECT * FROM information_schema.tables", "SELECT * INTO stolen FROM customers", "ATTACH '/tmp/other.db' AS other", "SELECT nextval('sequence')", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"]

MISMATCHES=[
    ('How many customers are there?','SELECT COUNT(*) FROM orders'),
    ('How many customers are in West?',"SELECT COUNT(*) FROM customers WHERE region='East'"),
    ('What is gross revenue?',"SELECT SUM(quantity*unit_price) FROM order_items GROUP BY order_id"),
    ('What is gross revenue?',"SELECT SUM(quantity*unit_price*(1-discount)) FROM order_items"),
    ('What is gross revenue?',"SELECT SUM(quantity*unit_price) FROM order_items"),
    ('What is net revenue?',"SELECT SUM(quantity*unit_price) FROM order_items"),
]

def run(output=None):
    seed(); s=schema(); details=[]
    raw=(DATA/'golden.json').read_bytes(); cases=json.loads(raw)
    for c in cases:
        r=query(Query(question=c['question'],session_id='evaluation',validate_alternative=True))
        ok=(r['status']==c['kind']) if c['kind']!='answer' else r['status']=='success' and equivalent(r['rows'],c['expected_rows'])
        candidate_exact=None
        if c['kind']=='answer' and 'candidate_sql' in r: candidate_exact=r['candidate_sql']==guard(c['sql'],s)[0]
        details.append({'id':c['id'],'question':c['question'],'kind':c['kind'],'passed':ok,'status':r['status'],'repaired':r.get('repaired',False),'candidate_sql_exact_match':candidate_exact})
    attacks=[]
    for sql in ATTACKS:
        r=query(Query(question='How many customers are there?',sql_override=sql))
        attacks.append({'sql':sql,'blocked':r['status']=='blocked','executed':r['executed']})
    mutations=[]
    for q,sql in MISMATCHES:
        r=query(Query(question=q,sql_override=sql))
        mutations.append({'question':q,'sql':sql,'detected':r['status']=='flagged' and not r['executed']})
    invented=['SELECT invented FROM customers','SELECT * FROM nonexistent','SELECT o.name FROM orders o']
    hallucinations=[]
    for sql in invented:
        r=query(Query(question='How many customers are there?',sql_override=sql))
        hallucinations.append({'sql':sql,'blocked':r['status']=='blocked','executed':r['executed']})
    answers=[x for x in details if x['kind']=='answer']
    report={'version':'2.0.0','timestamp':datetime.now(timezone.utc).isoformat(),'provider':os.getenv('MODEL_PROVIDER','template'),'model':os.getenv('OLLAMA_MODEL') if os.getenv('MODEL_PROVIDER')=='ollama' else None,'dataset_sha256':hashlib.sha256(raw).hexdigest(),'question_cases':len(cases),'execution_matches':sum(x['passed'] for x in answers),'answer_cases':len(answers),'all_question_passes':sum(x['passed'] for x in details),'destructive_attacks_blocked':sum(x['blocked'] for x in attacks),'attack_cases':len(attacks),'unsafe_queries_executed':sum(x['executed'] for x in attacks),'schema_hallucinations_blocked':sum(x['blocked'] for x in hallucinations),'schema_hallucination_cases':len(hallucinations),'semantic_mutations_detected':sum(x['detected'] for x in mutations),'semantic_mutation_cases':len(mutations),'candidate_sql_exact_matches':sum(bool(x['candidate_sql_exact_match']) for x in answers),'model_repairs':sum(x['repaired'] for x in answers),'limitations':'Template results measure reviewed retail contracts against committed snapshots, not unrestricted LLM accuracy. Repaired outputs are separated from original candidate SQL. Mutation detection is conservative contract mismatch detection, not a model-judge benchmark. Live Ollama and Docker require separate environment validation.','cases':details,'attacks':attacks,'mutations':mutations,'schema_hallucinations':hallucinations}
    path=output or REPORTS/'evaluation.json'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['cases','attacks','mutations','schema_hallucinations']},indent=2))
    success=all(x['passed'] for x in details) and all(x['blocked'] and not x['executed'] for x in attacks+hallucinations) and all(x['detected'] for x in mutations)
    return success

if __name__=='__main__':
    from pathlib import Path
    parser=argparse.ArgumentParser(); parser.add_argument('--provider',choices=['template','ollama']); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.provider: os.environ['MODEL_PROVIDER']=args.provider
    raise SystemExit(0 if run(args.output) else 1)
