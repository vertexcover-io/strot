from pathlib import Path

from pydantic import BaseModel, Field

from strot.schema.request import Request
from strot.schema.response import Response

__all__ = (
    "JobBasedInput",
    "TaskBasedInput",
    "ExistingJobInput",
    "NewJobInput",
    "RequestDetectionInput",
    "ParameterDetectionInput",
    "StructuredExtractionInput",
)


class BaseInput(BaseModel):
    @property
    def identifier(self) -> str:
        raise NotImplementedError

    @property
    def type(self) -> str:
        raise NotImplementedError


class RequestDetectionCommonInput(BaseModel):
    expected_source: str = Field(..., description="Expected source URL")


class ParameterDetectionCommonInput(BaseModel):
    expected_pagination_keys: list[str] = Field(default_factory=list, description="Expected pagination keys")
    expected_dynamic_keys: list[str] = Field(default_factory=list, description="Expected dynamic keys")


class StructuredExtractionCommonInput(BaseModel):
    expected_entity_count: int = Field(..., gt=0, description="Expected entity count")


class ExistingJobInput(
    BaseInput, RequestDetectionCommonInput, ParameterDetectionCommonInput, StructuredExtractionCommonInput
):
    job_id: str = Field(..., description="Job ID")

    @property
    def identifier(self) -> str:
        return self.job_id

    @property
    def type(self) -> str:
        return "existing job"


class NewJobInput(
    BaseInput, RequestDetectionCommonInput, ParameterDetectionCommonInput, StructuredExtractionCommonInput
):
    site_url: str = Field(..., description="Site URL")
    label: str = Field(..., description="Label")

    @property
    def identifier(self) -> str:
        return f"{self.site_url} | {self.label}"

    @property
    def type(self) -> str:
        return "new job"


class RequestDetectionInput(BaseInput, RequestDetectionCommonInput):
    site_url: str = Field(..., description="Site URL")
    query: str = Field(..., description="Query")

    @property
    def identifier(self) -> str:
        return f"{self.site_url} | {self.query}"

    @property
    def type(self) -> str:
        return "request detection"


class ParameterDetectionInput(BaseInput, ParameterDetectionCommonInput):
    request: Request

    @property
    def identifier(self) -> str:
        return f"{self.request.method} {self.request.url}"

    @property
    def type(self) -> str:
        return "parameter detection"


class StructuredExtractionInput(BaseInput, StructuredExtractionCommonInput):
    response: Response
    output_schema_file: Path

    @property
    def identifier(self) -> str:
        return f"{self.response.request.url} | {self.output_schema_file.name}"

    @property
    def type(self) -> str:
        return "structured extraction"


JobBasedInput = ExistingJobInput | NewJobInput

TaskBasedInput = RequestDetectionInput | ParameterDetectionInput | StructuredExtractionInput
