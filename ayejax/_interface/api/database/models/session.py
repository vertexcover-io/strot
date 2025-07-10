from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ayejax._interface.api.database.models.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True)
    output_id = Column(UUID(as_uuid=True), ForeignKey("outputs.id"), nullable=False)
    request_number = Column(Integer, nullable=False, default=0)
    cursor = Column(String(256))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_executed_at = Column(DateTime(timezone=True))

    output = relationship("Output", back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_output_id", "output_id"),
        Index("idx_sessions_last_executed", "last_executed_at"),
    )
