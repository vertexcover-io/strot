from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text

from ayejax._interface.api.database.models.base import Base


class Output(Base):
    __tablename__ = "outputs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    url = Column(Text, nullable=False)
    tag = Column(String(50), nullable=False)
    value = Column(JSONB, nullable=False)
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    jobs = relationship("Job", back_populates="output")

    __table_args__ = (
        UniqueConstraint("url", "tag", name="outputs_url_tag_unique"),
        Index("idx_outputs_tag", "tag"),
        Index("idx_outputs_url_pattern", text("to_tsvector('english', url)"), postgresql_using="gin"),
        Index("idx_outputs_popularity", "usage_count", "last_used_at", postgresql_using="btree"),
    )
