from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.openai_api_key)

def generate_sql(question: str, anonymized_schema: dict) -> str:
    schema_str = ""
    for table, columns in anonymized_schema.items():
        schema_str += f"Table {table}: columns are {', '.join(columns)}\n"

    prompt = f"""You are an expert SQL generator for PostgreSQL.

You will be given a database schema and a natural language question.

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

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert SQL generator. Return only raw SQL, nothing else."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=500
    )

    sql = response.choices[0].message.content.strip()
    return sql
