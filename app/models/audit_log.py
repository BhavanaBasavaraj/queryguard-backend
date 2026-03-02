from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    database_id = Column(String, nullable=False)
    natural_language = Column(String, nullable=False)
    sql_generated = Column(String, nullable=True)
    execution_time_ms = Column(Float, nullable=True)
    rows_returned = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False)
    llm_provider = Column(String, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog {self.query_id} - {self.success}>"
