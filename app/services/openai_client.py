from google import genai
from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

def generate_sql(question: str, anonymized_schema: dict, schema_hints: dict = None) -> str:
    schema_str = ""
    if schema_hints:
        for table, info in schema_hints.items():
            schema_str += f"- Table {table} ({info['hint']}): columns {', '.join(info['columns'])}\n"
    else:
        for table, columns in anonymized_schema.items():
            schema_str += f"- Table {table}: columns {', '.join(columns)}\n"

    prompt = f"""You are an expert SQL generator for PostgreSQL.

The database schema uses anonymized table and column names for privacy.
Each table has a hint describing its purpose to help you write correct queries.

Rules:
- Generate ONLY a single SQL SELECT statement
- Use ONLY the table and column names provided
- ALWAYS include a LIMIT clause (maximum 1000 rows)
- Never use DROP, DELETE, UPDATE, INSERT, TRUNCATE
- Return ONLY the raw SQL, no explanation, no markdown, no backticks
- Use the table hints to pick the right table for the question

Database Schema:
{schema_str}

Question: {question}

SQL Query:"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        sql = response.text.strip()
        if "```" in sql:
            lines = sql.split("\n")
            sql = "\n".join(line for line in lines if not line.strip().startswith("```"))
        return sql.strip()
    except Exception as e:
        raise Exception(f"Gemini API error: {str(e)}")
