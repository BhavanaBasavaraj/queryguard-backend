from google import genai
from google.genai import types
from app.config import settings
from app.core import providers
from app.core.llm_errors import classify
from app.core import genai_span as gs
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

client = genai.Client(api_key=settings.gemini_api_key)

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
        gs.span_name("chat", settings.gemini_model),
        kind=trace.SpanKind.CLIENT,
    ) as span:
        gs.set_request_attributes(
            span,
            provider=providers.GEMINI,
            model=settings.gemini_model,
            prompt=prompt,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_output_tokens,
            attempt_seq=attempt_seq,
            capture_content=settings.otel_capture_content,
        )
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=settings.llm_temperature,
                    # Gemini 3.x Flash is a thinking model and thinking tokens
                    # count as output, so this budget covers both. Disabling
                    # thinking keeps SQL generation cheap and deterministic.
                    max_output_tokens=settings.llm_max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            sql = response.text.strip()
            if "```" in sql:
                lines = sql.split("\n")
                sql = "\n".join(line for line in lines if not line.strip().startswith("```"))
            sql = sql.strip()

            # Field names are Gemini's; the helper maps them onto the one
            # vocabulary so nothing downstream knows which SDK ran.
            u = response.usage_metadata
            finish = response.candidates[0].finish_reason if response.candidates else None
            gs.set_response_attributes(
                span,
                response_model=getattr(response, "model_version", None),
                input_tokens=getattr(u, "prompt_token_count", None),
                output_tokens=getattr(u, "candidates_token_count", None),
                reasoning_tokens=getattr(u, "thoughts_token_count", None),
                cached_input_tokens=getattr(u, "cached_content_token_count", None),
                finish_reason=getattr(finish, "name", finish),
                sql=sql,
                capture_content=settings.otel_capture_content,
            )
            return sql
        except Exception as e:
            err = classify(e, providers.GEMINI, settings.gemini_model)
            gs.record_error(span, e, err.error_type)
            raise err from e
