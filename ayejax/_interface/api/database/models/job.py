from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ayejax._interface.api.database.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    url = Column(Text, nullable=False)
    tag = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False)
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True))

    output_id = Column(UUID(as_uuid=True), ForeignKey("outputs.id"), nullable=True)
    output = relationship("Output", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_output_id", "output_id"),
        CheckConstraint(status.in_(["pending", "ready", "failed"]), name="job_status_check"),
    )
