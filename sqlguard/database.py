import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
from .paths import ROOT, DATA
from functools import lru_cache
load_dotenv(ROOT/".env")
DB = Path(os.getenv("DB_PATH", str(DATA/"shop.duckdb")))
if not DB.is_absolute(): DB=ROOT/DB
DB=DB.resolve()

def seed():
    import duckdb
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists(): return
    c = duckdb.connect(str(DB))
    c.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, name VARCHAR, region VARCHAR)")
    c.execute("CREATE TABLE products(id INTEGER PRIMARY KEY, name VARCHAR, category VARCHAR, price DOUBLE)")
    c.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), order_date DATE, status VARCHAR)")
    c.execute("CREATE TABLE order_items(order_id INTEGER REFERENCES orders(id), product_id INTEGER REFERENCES products(id), quantity INTEGER, unit_price DOUBLE, discount DOUBLE)")
    c.executemany("INSERT INTO customers VALUES (?,?,?)", [(i, f"Customer {i}", ["West","East","North","South"][(i-1)%4]) for i in range(1,21)])
    c.executemany("INSERT INTO products VALUES (?,?,?,?)",[(1,"Laptop","Electronics",900),(2,"Headphones","Electronics",80),(3,"Desk","Furniture",200),(4,"Chair","Furniture",100),(5,"Notebook","Stationery",10)])
    from datetime import date, timedelta
    c.executemany("INSERT INTO orders VALUES (?,?,?,?)",[(i,(i-1)%20+1,date(2025,1,1)+timedelta(days=(i-1)*3),"cancelled" if i%10==0 else "completed") for i in range(1,101)])
    c.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)",[(i,j,(i+j)%3+1,[900,80,200,100,10][j-1],0.1 if i%4==0 else 0.0) for i in range(1,101) for j in [(i-1)%5+1,i%5+1]])
    c.close()

@lru_cache(maxsize=1)
def schema():
    seed()
    engine=create_engine(f"duckdb:///{DB}", connect_args={"read_only":True})
    ins=inspect(engine)
    result={}
    with engine.connect() as c:
        for table in ins.get_table_names():
            cols=ins.get_columns(table)
            result[table]={"columns":{x["name"]:str(x["type"]) for x in cols}, "primary_key":ins.get_pk_constraint(table).get("constrained_columns",[]), "foreign_keys":ins.get_foreign_keys(table),"samples":{}}
            pk=c.execute(text("SELECT constraint_column_names FROM duckdb_constraints() WHERE table_name=:table AND constraint_type='PRIMARY KEY'"), {"table":table}).fetchone()
            if pk: result[table]["primary_key"]=list(pk[0])
            for x in cols:
                if "CHAR" in str(x["type"]): result[table]["samples"][x["name"]]=[r[0] for r in c.execute(text(f'SELECT DISTINCT "{x["name"]}" FROM "{table}" LIMIT 5'))]
    engine.dispose()
    return result
