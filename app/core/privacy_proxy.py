class PrivacyProxy:

    def __init__(self, database_id: str):
        self.database_id = database_id
        self._forward_map = {}  # real_name → anonymous_name
        self._reverse_map = {}  # anonymous_name → real_name
        self._table_counter = 0
        self._column_counter = 0

    def _get_or_create_mapping(self, real_name: str, is_column: bool) -> str:
        if real_name in self._forward_map:
            return self._forward_map[real_name]

        prefix = "C" if is_column else "T"
        if is_column:
            self._column_counter += 1
            anonymous_name = f"{prefix}{self._column_counter}"
        else:
            self._table_counter += 1
            anonymous_name = f"{prefix}{self._table_counter}"

        self._forward_map[real_name] = anonymous_name
        self._reverse_map[anonymous_name] = real_name

        return anonymous_name

    def anonymize_schema(self, schema: dict) -> dict:
        anonymized = {}
        for table_name, columns in schema.items():
            anon_table = self._get_or_create_mapping(table_name, is_column=False)
            anon_columns = [
                self._get_or_create_mapping(col, is_column=True)
                for col in columns
            ]
            anonymized[anon_table] = anon_columns
        return anonymized

    def deanonymize_sql(self, sql: str) -> str:
        result = sql
        for anon, real in sorted(
            self._reverse_map.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            result = result.replace(anon, real)
        return result
