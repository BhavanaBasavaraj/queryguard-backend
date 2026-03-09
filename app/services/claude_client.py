import anthropic
from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def generate_sql(question: str, anonymized_schema: dict) -> str:
    schema_str = ""
    for table, columns in anonymized_schema.items():
        schema_str += f"Table {table}: columns are {', '.join(columns)}\n"

    prompt = f"""You are an expert SQL generator for PostgreSQL.

Rules you MUST follow:
- Generate ONLY a single SQL SELECT statement
- Use ONLY the table and column names provided in the schema
- ALWAYS include a LIMIT clause (maximum 1000 rows)
- Never use DROP, DELETE, UPDATE, INSERT, TRUNCATE or any destructive operation
- Return ONLY the raw SQL query, no explanation, no markdown, no backticks

Database Schema:
{schema_str}

Question: {question}

SQL Query:"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    sql = response.content[0].text.strip()
    return sql
