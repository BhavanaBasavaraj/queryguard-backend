import psycopg2
import psycopg2.extras
from decimal import Decimal
from datetime import datetime, date
from app.config import settings

def serialize_row(row: dict) -> dict:
    result = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result

def execute_query(sql: str) -> list[dict]:
    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            return [serialize_row(dict(row)) for row in results]
    finally:
        conn.close()
