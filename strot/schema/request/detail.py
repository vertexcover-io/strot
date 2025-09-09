import random
from typing import Any

import rnet
from pydantic import Field, PrivateAttr

from strot.exceptions import RequestException
from strot.schema.base import BaseSchema
from strot.schema.request.pagination_info import PaginationInfo
from strot.schema.request.request import Request

__all__ = ("RequestDetail",)


class RequestDetail(BaseSchema):
    request: Request
    pagination_info: PaginationInfo | None = None
    dynamic_parameters: dict[str, Any] = Field(default_factory=dict)
    code_to_apply_parameters: str | None = None

    _client: rnet.Client | None = PrivateAttr(default=None)
    _namespace: dict[str, Any] = PrivateAttr(default_factory=dict)

    def _get_client(self) -> rnet.Client:
        if self._client is None:
            # Collect available Chrome impersonations dynamically to avoid brittle name assumptions
            choices = [
                getattr(rnet.Impersonate, name)
                for name in dir(rnet.Impersonate)
                if name.startswith("Chrome") and name[6:].isdigit() and name[6:].startswith("13")
            ]
            if choices:
                self._client = rnet.Client(impersonate=random.choice(choices))  # noqa: S311
            else:
                # Fallback: default client without impersonation
                self._client = rnet.Client()
        return self._client

    async def make_request(
        self, *, parameters: dict[str, Any] | None = None, timeout: float | None = None
    ) -> rnet.Response:
        request = self.apply_parameters(**parameters) if parameters else self.request
        request_kwargs = {}
        if request.queries:
            request_kwargs["query"] = list(request.queries.items())
        if request.headers:
            request_kwargs["headers"] = request.headers

        if timeout is not None:
            request_kwargs["timeout"] = int(timeout)

        if request.post_data is not None:
            if isinstance(request.post_data, dict):
                request_kwargs["json"] = request.post_data
            else:
                request_kwargs["body"] = request.post_data

        response = await self._get_client().request(
            method=getattr(rnet.Method, request.method.upper()), url=request.url, **request_kwargs
        )
        if response.status != 200:
            raise RequestException(response.status, f"Request failed with status code: {response.status}")
        return response

    def apply_parameters(self, **parameters: dict[str, Any]) -> Request:
        try:
            if self.code_to_apply_parameters and not self._namespace:
                exec(self.code_to_apply_parameters, self._namespace)  # noqa: S102

            if "apply_parameters" in self._namespace:
                request = Request.model_validate(
                    self._namespace["apply_parameters"](self.request.model_dump(), **parameters)
                )
                request.headers = self.request.headers
                return request
        except Exception:  # noqa: S110
            pass

        # Backward compatible and used as fallback
        is_post_data_dict = isinstance(self.request.post_data, dict)
        request = Request(
            method=self.request.method,
            type=self.request.type,
            url=self.request.url,
            queries=self.request.queries.copy(),
            headers=self.request.headers.copy(),
            post_data=self.request.post_data.copy() if is_post_data_dict else self.request.post_data,
        )

        for key, value in parameters.items():
            # Check if key exists in queries
            if self.request.queries and key in self.request.queries:
                if value is None:
                    request.queries.pop(key, None)
                else:
                    request.queries[key] = value

            # Check if key exists in post_data (when it's a dict)
            if is_post_data_dict and key in self.request.post_data:
                if value is None:
                    request.post_data.pop(key, None)
                else:
                    request.post_data[key] = value

        return request
