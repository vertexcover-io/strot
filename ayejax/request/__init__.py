from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlencode

from .har import Request as HarRequest

__all__ = ("Request",)


class Request(HarRequest):
    """
    HTTP request model with load/persist to file and command generation functionalities.
    """

    @classmethod
    def load_from_file(cls, path: str | Path) -> Request:
        """Load a Request from a JSON file.

        Args:
            path: Path to the JSON file containing the request data

        Returns:
            Request: The loaded Request instance

        Raises:
            FileNotFoundError: If the specified file does not exist
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path!r}")

        return cls.model_validate_json(path.read_bytes())

    def save_to_file(self, path: str | Path) -> None:
        """Save the request to a JSON file.

        Args:
            path: Path where the JSON file should be saved
        """
        path = Path(path)
        path.write_text(self.model_dump_json(indent=3, exclude_none=True))

    def as_curl_command(self, *, format: Literal["bash", "cmd"] = "bash") -> str:
        """
        Generate a curl command representation of this request.

        Args:
            format: Shell format to generate command for. Defaults to `bash`.

        Returns:
            str: Generated curl command

        Raises:
            ValueError: If format is not `bash` or `cmd`
        """
        from ..helpers import bash_escape, cmd_escape

        fmt = format.lower()
        if fmt == "bash":
            return self._build_curl_command(bash_escape, " \\\n  ")
        elif fmt == "cmd":
            return self._build_curl_command(cmd_escape, " ^\n  ")

        raise ValueError(f"Unsupported format: {format!r}")

    def _build_curl_command(self, escape: Callable[[str], str], sep: str) -> str:
        """
        Build a curl command string with the given escaping function and separator.

        Args:
            escape: Function to escape command arguments
            sep: Separator to use between command parts

        Returns:
            str: Complete curl command string
        """
        ignored = {
            "accept-encoding",
            "host",
            "method",
            "path",
            "scheme",
            "version",
            "authority",
            "protocol",
        }

        parts = [escape(str(self.url))]

        # Method
        if self.method.upper() != "GET":
            parts.append(f"-X {escape(self.method)}")

        # Body
        if data := self._repr_post_data():
            parts.append(f"--data-raw {escape(data)}")
            ignored.add("content-length")

        # Headers & cookies
        cookie_val = None
        for h in self.headers:
            name = h.name.lstrip(":")
            if (lc := name.lower()) in ignored:
                continue
            if lc == "cookie":
                cookie_val = h.value
                continue

            if h.value.strip():
                header_str = f"{name}: {h.value}"
                parts.append(f"-H {escape(header_str)}")
            else:
                # Empty header handling like Chrome DevTools
                parts.append(f"-H {escape(name + ';')}")

        if cookie_val:
            parts.append(f"-b {escape(cookie_val)}")

        # Choose separator (single line if few parts)
        joiner = " " if len(parts) < 3 else sep
        return "curl " + joiner.join(parts) + " --compressed"

    def _repr_post_data(self) -> str | None:
        """Get string representation of POST data.

        Returns:
            str | None: String representation of POST data, or None if no data
        """
        if self.post_data is None:
            return None

        data = "{}"
        if self.post_data.text != "":
            data = self.post_data.text
        elif len(self.post_data.params) > 0:
            data = urlencode({p.name: p.value for p in self.post_data.params})
        return data
