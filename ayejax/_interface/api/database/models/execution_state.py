from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ayejax._interface.api.database.models.base import Base


class ExecutionState(Base):
    __tablename__ = "execution_states"

    id = Column(UUID(as_uuid=True), primary_key=True)
    request_number = Column(Integer, nullable=False, default=1)
    last_response = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_executed_at = Column(DateTime(timezone=True))

    output_id = Column(UUID(as_uuid=True), ForeignKey("outputs.id"), nullable=False)
    output = relationship("Output", back_populates="execution_states")

    __table_args__ = (
        Index("idx_execution_states_output_id", "output_id"),
        Index("idx_execution_states_last_executed", "last_executed_at"),
    )
