from openai import OpenAI
from opentelemetry import trace

from app.config import settings
from app.core import genai_span as gs
from app.core import providers
from app.core.llm_errors import classify

tracer = trace.get_tracer(__name__)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=settings.nvidia_api_key
)

def generate_sql(question: str, anonymized_schema: dict, schema_hints: dict = None,
                 attempt_seq: int = 1) -> str:
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

    # CLIENT kind: an outbound call we wait on. Nests automatically under
    # whatever span is current, so it becomes a child of the HTTP request.
    with tracer.start_as_current_span(
        gs.span_name("chat", settings.nvidia_model),
        kind=trace.SpanKind.CLIENT,
    ) as span:
        gs.set_request_attributes(
            span,
            provider=providers.NIM,
            model=settings.nvidia_model,
            prompt=prompt,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_output_tokens,
            attempt_seq=attempt_seq,
            capture_content=settings.otel_capture_content,
        )

        try:
            response = client.chat.completions.create(
                model=settings.nvidia_model,
                messages=[
                    {"role": "system", "content": "You are an expert SQL generator. Use type hints to write accurate SQL. Return only raw SQL."},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_output_tokens
            )
        except Exception as e:
            err = classify(e, providers.NIM, settings.nvidia_model)
            gs.record_error(span, e, err.error_type)
            raise err from e

        sql = response.choices[0].message.content.strip()
        if "```" in sql:
            lines = sql.split("\n")
            sql = "\n".join(line for line in lines if not line.strip().startswith("```"))
        sql = sql.strip()

        # OpenAI-shaped usage. Reasoning and cached counts live one level
        # deeper than the headline numbers.
        u = response.usage
        ctd = getattr(u, "completion_tokens_details", None)
        ptd = getattr(u, "prompt_tokens_details", None)
        gs.set_response_attributes(
            span,
            response_model=getattr(response, "model", None),
            input_tokens=getattr(u, "prompt_tokens", None),
            output_tokens=getattr(u, "completion_tokens", None),
            reasoning_tokens=getattr(ctd, "reasoning_tokens", None),
            cached_input_tokens=getattr(ptd, "cached_tokens", None),
            finish_reason=response.choices[0].finish_reason,
            sql=sql,
            capture_content=settings.otel_capture_content,
        )
        return sql
