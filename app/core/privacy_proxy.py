import uuid
from sqlalchemy.orm import Session
from app.models.schema_mapping import SchemaMapping

class PrivacyProxy:
    
    def __init__(self, db: Session, database_id: str):
        self.db = db
        self.database_id = database_id

    def _get_or_create_mapping(self, real_name: str, is_column: bool, parent_table: str = None) -> str:
        # Check if mapping already exists
        existing = self.db.query(SchemaMapping).filter(
            SchemaMapping.database_id == self.database_id,
            SchemaMapping.real_table_name == real_name,
            SchemaMapping.is_column == is_column
        ).first()

        if existing:
            return existing.anonymous_name

        # Create new mapping
        prefix = "C" if is_column else "T"
        count = self.db.query(SchemaMapping).filter(
            SchemaMapping.database_id == self.database_id,
            SchemaMapping.is_column == is_column
        ).count()

        anonymous_name = f"{prefix}{count + 1}"

        mapping = SchemaMapping(
            database_id=self.database_id,
            real_table_name=real_name,
            anonymous_name=anonymous_name,
            is_column=is_column,
            parent_table=parent_table
        )
        self.db.add(mapping)
        self.db.commit()

        return anonymous_name

    def anonymize_schema(self, schema: dict) -> dict:
        anonymized = {}

        for table_name, columns in schema.items():
            # Anonymize table name
            anon_table = self._get_or_create_mapping(
                real_name=table_name,
                is_column=False
            )

            # Anonymize each column
            anon_columns = []
            for col in columns:
                anon_col = self._get_or_create_mapping(
                    real_name=col,
                    is_column=True,
                    parent_table=table_name
                )
                anon_columns.append(anon_col)

            anonymized[anon_table] = anon_columns

        return anonymized

    def deanonymize_sql(self, sql: str) -> str:
        # Get all mappings for this database
        mappings = self.db.query(SchemaMapping).filter(
            SchemaMapping.database_id == self.database_id
        ).all()

        # Replace anonymous names with real names
        # Sort by length descending to avoid partial replacements
        mappings_sorted = sorted(
            mappings,
            key=lambda m: len(m.anonymous_name),
            reverse=True
        )

        result = sql
        for mapping in mappings_sorted:
            result = result.replace(
                mapping.anonymous_name,
                mapping.real_table_name
            )

        return result

    def get_forward_mapping(self) -> dict:
        mappings = self.db.query(SchemaMapping).filter(
            SchemaMapping.database_id == self.database_id
        ).all()
        return {m.real_table_name: m.anonymous_name for m in mappings}

    def get_reverse_mapping(self) -> dict:
        mappings = self.db.query(SchemaMapping).filter(
            SchemaMapping.database_id == self.database_id
        ).all()
        return {m.anonymous_name: m.real_table_name for m in mappings}
