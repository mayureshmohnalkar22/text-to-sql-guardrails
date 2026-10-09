import os
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

class Blocked(ValueError): pass

FUNCTIONS={"and","or","case","if","sum","count","avg","min","max","round","coalesce","extract","date_trunc","timestamp_trunc","lower","upper","length","abs","cast","try_cast","nullif","concat"}

def guard(sql, schema):
    try: trees=sqlglot.parse(sql,read="duckdb")
    except Exception as e: raise Blocked(f"Invalid SQL: {e}") from e
    if len(trees)!=1 or trees[0] is None: raise Blocked("Exactly one SQL statement is required")
    tree=trees[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)): raise Blocked("Only SELECT queries are permitted")
    for node in tree.walk():
        if isinstance(node,(exp.DDL,exp.DML,exp.Command,exp.Into)): raise Blocked("Write or command operation blocked")
        if isinstance(node,exp.Func):
            name=node.name.lower() if isinstance(node,exp.Anonymous) else node.sql_name().lower()
            if name not in FUNCTIONS: raise Blocked(f"Function {name} is outside the allowlist")
        if isinstance(node,exp.Table) and (node.db or node.catalog or not isinstance(node.this,exp.Identifier)): raise Blocked("External sources and qualified tables are blocked")
    ctes={x.alias_or_name for x in tree.find_all(exp.CTE)}
    tables={x.name for x in tree.find_all(exp.Table)}-ctes
    if not tables or not tables<=schema.keys(): raise Blocked(f"Unknown or absent tables: {sorted(tables-schema.keys())}")
    for sub in tree.find_all(exp.Subquery):
        depth=sum(isinstance(x,exp.Subquery) for x in sub.walk())
        if depth>int(os.getenv("MAX_SUBQUERY_DEPTH","3")): raise Blocked("Subquery nesting limit exceeded")
    try:
        qualify(tree.copy(),dialect="duckdb",schema={t:v["columns"] for t,v in schema.items()},validate_qualify_columns=True)
    except Exception as e: raise Blocked(f"Schema validation failed: {e}") from e
    cap=int(os.getenv("MAX_ROWS","1000"))
    limit=tree.args.get("limit")
    if limit:
        val=limit.expression
        if not isinstance(val,exp.Literal) or not val.is_int: raise Blocked("LIMIT must be an integer literal")
        if int(val.this)<0: raise Blocked("Negative LIMIT blocked")
        cap=min(cap,int(val.this))
    tree=tree.limit(cap)
    return tree.sql(dialect="duckdb"), sorted(tables)
