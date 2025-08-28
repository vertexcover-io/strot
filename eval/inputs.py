from pathlib import Path

from pydantic import BaseModel, Field

from strot.analyzer.schema import Response
from strot.analyzer.schema.request import Request


class BaseInput(BaseModel):
    @property
    def identifier(self) -> str:
        raise NotImplementedError

    @property
    def type(self) -> str:
        raise NotImplementedError


class ExpectedSource(BaseModel):
    expected_source: str = Field(..., description="Expected source URL")


class ExpectedPaginationKeys(BaseModel):
    expected_pagination_keys: list[str] = Field(default_factory=list, description="Expected pagination keys")


class ExpectedEntityCount(BaseModel):
    expected_entity_count: int = Field(..., gt=0, description="Expected entity count")


class ExistingJobInput(BaseInput, ExpectedSource, ExpectedPaginationKeys, ExpectedEntityCount):
    job_id: str = Field(..., description="Job ID")

    @property
    def identifier(self) -> str:
        return self.job_id

    @property
    def type(self) -> str:
        return "existing job"


class NewJobInput(BaseInput, ExpectedSource, ExpectedPaginationKeys, ExpectedEntityCount):
    site_url: str = Field(..., description="Site URL")
    label: str = Field(..., description="Label")

    @property
    def identifier(self) -> str:
        return f"{self.site_url} | {self.label}"

    @property
    def type(self) -> str:
        return "new job"


class RequestDetectionInput(BaseInput, ExpectedSource):
    site_url: str = Field(..., description="Site URL")
    query: str = Field(..., description="Query")

    @property
    def identifier(self) -> str:
        return f"{self.site_url} | {self.query}"

    @property
    def type(self) -> str:
        return "request detection"


class PaginationDetectionInput(BaseInput, ExpectedPaginationKeys):
    request: Request

    @property
    def identifier(self) -> str:
        return f"{self.request.method} {self.request.url}"

    @property
    def type(self) -> str:
        return "pagination detection"


class CodeGenerationInput(BaseInput, ExpectedEntityCount):
    response: Response
    output_schema_file: Path

    @property
    def identifier(self) -> str:
        return f"{self.response.request.url} | {self.output_schema_file.name}"

    @property
    def type(self) -> str:
        return "code generation"


JobBasedInput = ExistingJobInput | NewJobInput

TaskBasedInput = RequestDetectionInput | PaginationDetectionInput | CodeGenerationInput

InputUnion = TaskBasedInput | JobBasedInput
