def generate_sql(question: str, anonymized_schema: dict) -> str:
    # MOCK MODE - Claude fallback mock
    first_table = list(anonymized_schema.keys())[0]
    columns = anonymized_schema[first_table]
    col_list = ", ".join(columns[:3])
    return f"SELECT {col_list} FROM {first_table} LIMIT 10"
