import json
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
    def parameters(self) -> dict[str, Any]:
        def _load_value(value: Any) -> Any:
            if isinstance(value, str):
                try:
                    return _load_value(json.loads(value))
                except (json.JSONDecodeError, ValueError):
                    return value
            elif isinstance(value, dict):
                return {k: _load_value(v) for k, v in value.items()}
            else:
                return value

        if self.method.lower() == "post" and isinstance(self.post_data, dict):
            return _load_value(self.post_data)

        return _load_value(self.queries)

    def apply_state(self, state: dict[str, Any]) -> "Request":
        request = self.model_copy()
        if request.method.lower() == "post" and isinstance(request.post_data, dict):
            for key, value in state.items():
                if value is None:
                    request.post_data.pop(key, None)
                else:
                    request.post_data[key] = value
        else:
            for key, value in state.items():
                if value is None:
                    request.queries.pop(key, None)
                else:
                    request.queries[key] = value

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
