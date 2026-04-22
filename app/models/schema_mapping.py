from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class SchemaMapping(Base):
    __tablename__ = "schema_mappings"

    id = Column(Integer, primary_key=True, index=True)
    database_id = Column(String, nullable=False, index=True)
    real_table_name = Column(String, nullable=False)
    anonymous_name = Column(String, nullable=False)
    is_column = Column(Boolean, default=False)
    parent_table = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SchemaMapping {self.real_table_name} → {self.anonymous_name}>"
