import psycopg2
import psycopg2.extras
from app.config import settings

def execute_query(sql: str) -> list[dict]:
    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            return [dict(row) for row in results]
    finally:
        conn.close()
