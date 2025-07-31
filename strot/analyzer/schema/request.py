from typing import Any

import httpx
from pydantic import BaseModel


class Request(BaseModel):
    method: str
    url: str
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None

    @property
    def simple_parameters(self) -> dict[str, Any]:
        result = {}

        from strot.analyzer.utils import is_flat_or_flat_dict, json_load_value

        # From queries if it exists
        if self.queries:
            loaded_queries = json_load_value(self.queries)
            for k, v in loaded_queries.items():
                if is_flat_or_flat_dict(v):
                    result[k] = v

        # From post_data if it's a dict
        if isinstance(self.post_data, dict):
            loaded_post_data = json_load_value(self.post_data)
            for k, v in loaded_post_data.items():
                if is_flat_or_flat_dict(v):
                    result[k] = v

        return result if result else None

    def apply_state(self, state: dict[str, Any]) -> "Request":
        is_post_data_dict = isinstance(self.post_data, dict)
        request = Request(
            method=self.method,
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

    async def make(self, timeout: float | None = None) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                self.method,
                self.url,
                params=self.queries,
                headers=self.headers,
                data=self.post_data,
            )
            response.raise_for_status()
            return response
