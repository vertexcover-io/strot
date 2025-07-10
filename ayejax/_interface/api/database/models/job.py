from sqlalchemy import CheckConstraint, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.sql import func

from ayejax._interface.api.database.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    url = Column(Text, nullable=False)
    tag = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    message = Column(Text)
    analysis_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(status.in_(["pending", "ready", "failed"]), name="job_status_check"),)
