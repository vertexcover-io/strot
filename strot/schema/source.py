from strot.pagination_translators import LimitOffsetTranslator
from strot.schema.base import BaseSchema
from strot.schema.request import PaginationInfo, Request, RequestDetail
from strot.schema.response import ResponseDetail, ResponsePreprocessorUnion

__all__ = ("Source", "OldSource")


class Source(BaseSchema):
    request_detail: RequestDetail
    response_detail: ResponseDetail

    async def generate_data(self, *, limit: int, offset: int, **dynamic_parameters):
        unknown = set(dynamic_parameters) - set(self.request_detail.dynamic_parameters)
        if unknown:
            raise ValueError(
                f'Unknown dynamic parameter(s): {", ".join(sorted(unknown))}. '
                f'Allowed: {", ".join(sorted(self.request_detail.dynamic_parameters))}'
            )

        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be non-negative")

        translator = LimitOffsetTranslator(limit, offset)
        async for data in translator.generate_data(
            request_detail=self.request_detail,
            response_detail=self.response_detail,
            **dynamic_parameters,
        ):
            yield data


# Legacy source (for backward compatibility)
class OldSource(BaseSchema):
    request: Request
    pagination_strategy: PaginationInfo | None = None
    response_preprocessor: ResponsePreprocessorUnion | None = None
    extraction_code: str | None = None
    default_limit: int = 1

    def as_new_source(self) -> "Source":
        # Create RequestDetail from old source
        request_detail = RequestDetail(
            request=self.request,
            pagination_info=self.pagination_strategy,
            dynamic_parameters={},  # Old source didn't support dynamic parameters
            code_to_apply_parameters=None,  # Use fallback parameter application
        )

        # Create ResponseDetail from old source
        response_detail = ResponseDetail(
            preprocessor=self.response_preprocessor,
            code_to_extract_data=self.extraction_code,
            default_entity_count=self.default_limit,
        )

        return Source(
            request_detail=request_detail,
            response_detail=response_detail,
        )

    async def generate_data(self, *, limit: int, offset: int, **dynamic_parameters):
        source = self.as_new_source()
        async for data in source.generate_data(limit=limit, offset=offset):
            yield data
