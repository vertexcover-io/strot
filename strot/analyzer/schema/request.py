import random
from typing import Any, Literal

import rnet
from pydantic import BaseModel, PrivateAttr


class RequestException(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class Request(BaseModel):
    method: str
    url: str
    type: Literal["ajax", "ssr"] = "ajax"
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None

    _client: rnet.Client | None = PrivateAttr(default=None)

    def _apply_state(self, state: dict[str, Any]) -> "Request":
        is_post_data_dict = isinstance(self.post_data, dict)
        request = Request(
            method=self.method,
            type=self.type,
            url=self.url,
            queries=self.queries.copy(),
            headers=self.headers.copy(),
            post_data=self.post_data.copy() if is_post_data_dict else self.post_data,
        )

        for key, value in state.items():
            # Check if key exists in queries
            if self.queries and key in self.queries:
                if value is None:
                    request.queries.pop(key, None)
                else:
                    request.queries[key] = value

            # Check if key exists in post_data (when it's a dict)
            if is_post_data_dict and key in self.post_data:
                if value is None:
                    request.post_data.pop(key, None)
                else:
                    request.post_data[key] = value

        return request

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

    async def make(
        self,
        *,
        state: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> rnet.Response:
        request = self
        if state is not None:
            request = self._apply_state(state)

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
