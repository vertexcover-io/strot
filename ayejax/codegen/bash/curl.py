from __future__ import annotations

from urllib.parse import quote_plus, urlsplit, urlunsplit

from ayejax.helpers import bash_escape, determine_page_and_offset_keys
from ayejax.request import Request

from ..base import BaseCode


class BashCurlCode(BaseCode):
    @classmethod
    def from_request(cls, request: Request) -> BashCurlCode:  # noqa: C901
        """Builds a `curl` bash script from a `Request` object."""

        code_lines = ["make_request() {"]
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
            code_lines.append("  page_number=${" + f"{page_number}" + ":-1}")

        if pagination:
            query_parts = []
            for query in request.queries:
                if page_key and query.name == page_key:
                    query_parts.append(f"{page_key}=$page_number")
                elif offset_key and query.name == offset_key:
                    query_parts.append(f"{offset_key}=$(({offset // page_number} * page_number))")
                else:
                    query_parts.append(f"{query.name}={quote_plus(query.value)}")

            split = urlsplit(str(request.url))
            url = urlunsplit((split.scheme, split.netloc, split.path, "&".join(query_parts), split.fragment))
            url = f'"{url}"'
        else:
            url = bash_escape(str(request.url))

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
        parts = [url]
        if request.method.upper() != "GET":
            parts.append(f"  -X {bash_escape(request.method)}")

        if (data := request._repr_post_data()) is not None:
            parts.append(f"  --data-raw {bash_escape(data)}")
            ignored_headers.add("content-length")

        cookie_val = None
        for h in request.headers:
            name = h.name.lstrip(":")
            if (lc := name.lower()) in ignored_headers:
                continue
            if lc == "cookie":
                cookie_val = h.value
                continue
            if h.value.strip():
                header_str = f"{name}: {h.value}"
                parts.append(f"  -H {bash_escape(header_str)}")
            else:
                parts.append(f"  -H {bash_escape(name + ';')}")
        if cookie_val:
            parts.append(f"  -b {bash_escape(cookie_val)}")

        joiner = " " if len(parts) < 3 else " \\\n  "

        code_lines.append("  curl " + joiner.join(parts) + " --compressed")
        code_lines.append("}")

        # ---- Caller Blocks ----
        caller_lines = ["# Example usage:"]
        if page_key or offset_key:
            caller_lines.extend([
                "# To paginate, provide a page number:",
                "# make_request 2",
            ])
        caller_lines.extend([
            "# To make a non-paginated call (or use default page 1 if paginated):",
            "make_request",
        ])

        loop_caller_lines = []
        if page_key or offset_key:
            loop_caller_lines.extend([
                "page=1",
                "while true; do",
                '  echo "Fetching page $page..."',
                "  make_request $page",
                "  page=$((page + 1))",
                "  sleep 1",
                "done",
            ])

        return cls(
            import_block="",
            code_block="\n".join(code_lines),
            caller_block="\n".join(caller_lines),
            loop_caller_block="\n".join(loop_caller_lines),
        )
