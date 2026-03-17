from app.config import settings

def generate_sql(question: str, anonymized_schema: dict) -> str:
    # MOCK MODE - returns fake SQL for testing without real API key
    # In production, replace this with real OpenAI call
    
    question_lower = question.lower()
    
    # Get first table and its columns from anonymized schema
    first_table = list(anonymized_schema.keys())[0]
    columns = anonymized_schema[first_table]
    col_list = ", ".join(columns[:3])  # first 3 columns
    
    if "top" in question_lower or "revenue" in question_lower:
        last_col = columns[-1]
        return f"SELECT {col_list} FROM {first_table} ORDER BY {last_col} DESC LIMIT 10"
    
    elif "count" in question_lower or "how many" in question_lower:
        return f"SELECT COUNT(*) FROM {first_table} LIMIT 1"
    
    else:
        return f"SELECT {col_list} FROM {first_table} LIMIT 10"
