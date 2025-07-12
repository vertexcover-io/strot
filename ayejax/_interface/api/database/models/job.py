from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ayejax._interface.api.database.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    url = Column(Text, nullable=False)
    tag = Column(String(50), nullable=False)

    # process info
    status = Column(String(20), nullable=False)
    message = Column(Text)
    analysis_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True))

    # one-to-one relationship with execution_states
    execution_state_id = Column(UUID(as_uuid=True), ForeignKey("execution_states.id"), nullable=True)
    execution_state = relationship("ExecutionState", uselist=False)

    __table_args__ = (CheckConstraint(status.in_(["pending", "ready", "failed"]), name="job_status_check"),)
