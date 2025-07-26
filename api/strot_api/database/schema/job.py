from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from strot_api.database.schema.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    url = Column(Text, nullable=False)
    label_id = Column(UUID(as_uuid=True), ForeignKey("labels.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(20), nullable=False)

    source = Column(JSONB)  # Contains source object if job completed successfully
    usage_count = Column(Integer, default=0)  # Number of times the source has been used
    last_used_at = Column(DateTime(timezone=True))  # Last time the source was used

    error = Column(Text)  # Contains error message if job failed

    initiated_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at = Column(DateTime(timezone=True))

    label = relationship("Label", back_populates="jobs")

    __table_args__ = (CheckConstraint(status.in_(["pending", "ready", "failed"]), name="job_status_check"),)
