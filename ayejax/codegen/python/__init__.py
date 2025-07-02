from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from jinja2 import Environment, FileSystemLoader

from ayejax import pagination
from ayejax.codegen.base import BaseCode
from ayejax.types import CapturedRequest

__all__ = ("PythonCode",)

HEADERS_TO_IGNORE = {
    "accept-encoding",
    "host",
    "method",
    "path",
    "scheme",
    "version",
    "authority",
    "protocol",
}


class PythonCode(BaseCode):
    jinja_env: ClassVar[Environment] = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=True,
    )
    jinja_env.filters["repr"] = lambda v: repr(v)

    @classmethod
    def from_request(cls, request: CapturedRequest, template: Literal["requests", "httpx"]) -> PythonCode:
        """
        Builds python code from a request object.

        Args:
            request: The request object to build code from.
            template: The template to use for building the code.
        """

        jinja_template = cls.jinja_env.get_template(f"{template}.jinja")
        for key in list(request.headers):
            if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                request.headers.pop(key)

        map_key = None
        strategy = pagination.determine_strategy(request.queries)
        if strategy is not None:
            map_key = "params"
        elif isinstance(request.post_data, dict):
            map_key = "data"
            strategy = pagination.determine_strategy(request.post_data)

        code_block = jinja_template.render(
            method=request.method,
            url=request.url,
            headers=request.headers,
            params=request.queries,
            data=request.post_data,
            pagination_strategy=strategy,
            map_key=map_key,
        )

        loop_lines = [
            "request_number = 1",
            "while True:",
            "    try:",
            "        print(f'Fetching request {request_number}...')",
            "        response = make_request(request_number)",
            "        request_number += 1",
            "    except Exception as e:",
            "        print(f'Finished pagination or encountered an error: {e}')",
            "        break",
        ]

        return cls(
            code_block=code_block,
            caller_block="make_request(1)",
            loop_caller_block="\n".join(loop_lines),
        )
