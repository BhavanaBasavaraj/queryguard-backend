from openai import OpenAI
from app.config import settings

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.nvidia_api_key
)

def generate_sql(question: str, anonymized_schema: dict, schema_hints: dict = None) -> str:
    schema_str = ""
    if schema_hints:
        for table, info in schema_hints.items():
            cols = ", ".join(info.get("col_descriptions", info["columns"]))
            schema_str += f"- Table {table} ({info['hint']}): {cols}\n"
    else:
        for table, columns in anonymized_schema.items():
            schema_str += f"- Table {table}: columns {', '.join(columns)}\n"

    prompt = f"""You are an expert SQL generator for PostgreSQL.

The schema uses anonymized names for privacy but includes type hints to help you write correct SQL.

Rules:
- Generate ONLY a single SQL SELECT statement
- Use ONLY the anonymized table and column names provided
- ALWAYS include a LIMIT clause (maximum 1000 rows)
- Never use DROP, DELETE, UPDATE, INSERT, TRUNCATE
- Return ONLY the raw SQL, no explanation, no markdown, no backticks
- Use the type hints to pick correct columns for filtering and ordering

Database Schema:
{schema_str}

Question: {question}

SQL Query:"""

    response = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=[
            {"role": "system", "content": "You are an expert SQL generator. Use type hints to write accurate SQL. Return only raw SQL."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=500
    )

    sql = response.choices[0].message.content.strip()
    if "```" in sql:
        lines = sql.split("\n")
        sql = "\n".join(line for line in lines if not line.strip().startswith("```"))
    return sql.strip()
