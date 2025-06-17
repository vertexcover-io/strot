from __future__ import annotations

import json
from urllib.parse import quote_plus, urlsplit, urlunsplit

from ayejax.helpers import determine_page_and_offset_keys
from ayejax.request import Request

from ..base import BaseCode


class PythonRequestsCode(BaseCode):
    @classmethod
    def from_request(cls, request: Request) -> PythonRequestsCode:  # noqa: C901
        """Builds a `requests` code from a `Request` object."""

        import_lines = ["import requests"]
        code_lines = ["def make_request(page_number: int | None = None):"]
        page_key, offset_key = determine_page_and_offset_keys(query.name for query in request.queries)

        page_number, offset, pagination = 1, 0, False
        for query in request.queries:
            if page_key and query.name == page_key:
                page_number = int(query.value)
                pagination = True
            elif offset_key and query.name == offset_key:
                offset = int(query.value)
                pagination = True

        if page_key or offset_key:
            code_lines.append(f"    page_number = {page_number} if page_number is None else page_number")

        if pagination:
            query_parts = []
            for query in request.queries:
                if page_key and query.name == page_key:
                    query_parts.append(f"{page_key}={{page_number}}")
                elif offset_key and query.name == offset_key:
                    query_parts.append(f"{offset_key}=" + "{" + f"{offset // page_number} * page_number" + "}")
                else:
                    query_parts.append(f"{query.name}={quote_plus(query.value)}")

            split = urlsplit(str(request.url))
            url = urlunsplit((split.scheme, split.netloc, split.path, "&".join(query_parts), split.fragment))
            url = f'f"{url}"'
            code_lines.append(f"    url = {url}")
        else:
            code_lines.append(f'    url = "{request.url!s}"')

        # Headers
        ignored_headers = {
            "accept-encoding",
            "host",
            "method",
            "path",
            "scheme",
            "version",
            "authority",
            "protocol",
        }
        headers_dict: dict[str, str] = {}
        for header in request.headers:
            name = header.name.lstrip(":")
            if name.lower() in ignored_headers:
                continue
            if header.value.strip():
                headers_dict[name] = header.value
        if headers_dict:
            code_lines.append(f"    headers = {json.dumps(headers_dict, indent=4)}")

        # Payload
        payload_arg = ""
        if (data := request._repr_post_data()) and data != "{}":
            try:
                parsed = json.loads(data)
                pretty = json.dumps(parsed, indent=4)
                code_lines.append(f"    payload = {pretty}")
                payload_arg = ", json=payload"
            except json.JSONDecodeError:
                escaped = data.replace("\\", "\\\\").replace('"', '\\"')
                code_lines.append(f'    payload = """{escaped}"""')
                payload_arg = ", data=payload"

        # API call
        headers_arg = ", headers=headers" if headers_dict else ""
        code_lines.append(f'    response = requests.request("{request.method.upper()}", url{headers_arg}{payload_arg})')
        code_lines.append("    response.raise_for_status()")
        code_lines.append("    print(response.text)")
        code_lines.append("    return response")

        # Caller blocks
        caller_lines = ["# Example usage:"]
        if page_key or offset_key:
            caller_lines.append("# To paginate, provide a page number:")
            caller_lines.append("# make_request(1)")
        caller_lines.append("# To make a non-paginated call:")
        caller_lines.append("make_request()")

        loop_lines = []
        if page_key or offset_key:
            loop_lines.extend([
                "page = 1",
                "while True:",
                "    try:",
                "        print(f'Fetching page {page}...')",
                "        response = make_request(page)",
                "        page += 1",
                "    except requests.exceptions.HTTPError as e:",
                "        print(f'Finished pagination or encountered an error: {e}')",
                "        break",
            ])

        return cls(
            import_block="\n".join(import_lines),
            code_block="\n".join(code_lines),
            caller_block="\n".join(caller_lines),
            loop_caller_block="\n".join(loop_lines),
        )
