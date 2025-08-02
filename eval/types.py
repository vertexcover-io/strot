from typing import Any, TypedDict

from pydantic import BaseModel, Field


class AirtableField(TypedDict):
    name: str
    description: str
    type: str
    options: dict[str, Any] | None = None


class _CommonInput(BaseModel):
    expected_source: str = Field(..., description="Expected source URL")
    expected_pagination_keys: list[str] = Field(default_factory=list, description="Expected pagination keys")
    expected_entity_count: int = Field(0, description="Expected entity count")


class ExistingJobInput(_CommonInput):
    job_id: str = Field(..., description="Job ID")


class NewJobInput(_CommonInput):
    site_url: str = Field(..., description="Site URL")
    label: str = Field(..., description="Label")
