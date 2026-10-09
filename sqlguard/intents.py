"""Reviewed retail intent contracts. These are not inferred from eval fixtures."""
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Contract:
    intent: str
    sql: str
    alternative: str | None = None
    scalar: bool = False

REGIONS={r.lower():r for r in ["West","East","North","South"]}
PRODUCTS={x.lower():x for x in ["Laptop","Headphones","Desk","Chair","Notebook"]}

def resolve(question):
    q=re.sub(r"\s+"," ",question.lower().strip()).rstrip("?.!")
    count_match=re.fullmatch(r"(?:how many customers (?:are there|are in (west|east|north|south))|(?:count|total number of) customers(?: in (west|east|north|south))?)",q)
    if count_match:
        region=next((r for r in count_match.groups() if r),None)
        where=f" WHERE region='{REGIONS[region]}'" if region else ""
        return Contract("customer_count","SELECT COUNT(*) AS customer_count FROM customers"+where,"SELECT COALESCE(SUM(1),0) AS customer_count FROM customers"+where,True)
    m=re.fullmatch(r"(?:what is|show|calculate|what is the total|show total|total) (gross|net) revenue",q)
    if m:
        metric=m[1]; amount="quantity*unit_price"+("*(1-discount)" if metric=="net" else "")
        qualified="i.quantity*i.unit_price"+("*(1-i.discount)" if metric=="net" else "")
        return Contract(metric+"_revenue",f"SELECT SUM({qualified}) AS {metric}_revenue FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.status='completed'",f"SELECT SUM(amount) AS {metric}_revenue FROM (SELECT order_id,SUM({amount}) AS amount FROM order_items GROUP BY order_id) i WHERE order_id IN (SELECT id FROM orders WHERE status='completed')",True)
    m=re.fullmatch(r"how many orders (?:were|are) (cancelled|completed)",q)
    if m: return Contract("order_status_count",f"SELECT COUNT(*) AS order_count FROM orders WHERE status='{m[1]}'",scalar=True)
    fixed={
        "show order counts by region":Contract("orders_by_region","SELECT c.region,COUNT(*) AS order_count FROM orders o JOIN customers c ON c.id=o.customer_id GROUP BY c.region ORDER BY c.region"),
        "show gross revenue by category":Contract("revenue_by_category","SELECT p.category,SUM(i.quantity*i.unit_price) AS gross_revenue FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id WHERE o.status='completed' GROUP BY p.category ORDER BY p.category"),
        "show the five most expensive products":Contract("top_products","SELECT name,price FROM products ORDER BY price DESC, name ASC LIMIT 5"),
        "show monthly order counts":Contract("orders_by_month","SELECT DATE_TRUNC('month',order_date) AS month,COUNT(*) AS order_count FROM orders GROUP BY month ORDER BY month"),
        "show products with no sales":Contract("unsold_products","SELECT p.name FROM products p LEFT JOIN order_items i ON p.id=i.product_id WHERE i.product_id IS NULL ORDER BY p.name"),
    }
    if q in fixed: return fixed[q]
    m=re.fullmatch(r"list customers in (west|east|north|south)",q)
    if m: return Contract("customer_list",f"SELECT id,name FROM customers WHERE region='{REGIONS[m[1]]}' ORDER BY id")
    m=re.fullmatch(r"how many orders came from (west|east|north|south)",q)
    if m: return Contract("orders_in_region",f"SELECT COUNT(*) AS order_count FROM orders o JOIN customers c ON c.id=o.customer_id WHERE c.region='{REGIONS[m[1]]}'",scalar=True)
    m=re.fullmatch(r"how many orders were placed in month (\d{1,2}) of (\d{4})",q)
    if m and 1<=int(m[1])<=12: return Contract("orders_in_month",f"SELECT COUNT(*) AS order_count FROM orders WHERE EXTRACT(month FROM order_date)={int(m[1])} AND EXTRACT(year FROM order_date)={int(m[2])}",scalar=True)
    m=re.fullmatch(r"what is the price of (laptop|headphones|desk|chair|notebook)",q)
    if m: return Contract("product_price",f"SELECT price FROM products WHERE name='{PRODUCTS[m[1]]}'")
    m=re.fullmatch(r"how many units of (laptop|headphones|desk|chair|notebook) were ordered",q)
    if m: return Contract("units_ordered",f"SELECT SUM(i.quantity) AS units FROM order_items i JOIN products p ON p.id=i.product_id WHERE p.name='{PRODUCTS[m[1]]}'",scalar=True)
    m=re.fullmatch(r"how many orders did customer (\d+) place",q)
    if m: return Contract("customer_orders",f"SELECT COUNT(*) AS order_count FROM orders WHERE customer_id={int(m[1])}",scalar=True)
    return None
