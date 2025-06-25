from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel, Field


class Data(BaseModel):
    """Model representing the data of a HAR file."""

    class Config:
        frozen = True

    log: Log
    """The root log entry containing all HTTP entries"""


class Log(BaseModel):
    """Model representing the log section of a HAR file."""

    entries: list[Entry]
    """List of HTTP request/response entries in the HAR file"""


class Entry(BaseModel):
    """Model representing a single entry in the HAR log."""

    request: Request
    """The HTTP request details for this entry"""


class Pair(BaseModel):
    """Model representing a name-value pair used in headers, cookies, etc."""

    name: str
    """The name/key of the pair"""
    value: Any
    """The value associated with the name/key"""


class PostData(BaseModel):
    """Model representing POST data in a request."""

    class Config:
        populate_by_name = True

    mime_type: str = Field(alias="mimeType")
    """The MIME type of the request body"""
    text: str
    """The raw text content of the request body"""
    params: list[Pair]
    """List of parameters when the content type is application/x-www-form-urlencoded"""


class Request(BaseModel):
    """Model representing an HTTP request in a HAR file.

    Contains details about the HTTP method, URL, headers, cookies,
    query parameters and post data.
    """

    class Config:
        populate_by_name = True

    method: str
    """The HTTP method used for the request"""
    url: str
    """The full URL of the request"""
    cookies: list[Pair] = Field(default_factory=list)
    """List of cookies sent with the request"""
    headers: list[Pair] = Field(default_factory=list)
    """List of HTTP headers sent with the request"""
    queries: list[Pair] = Field(default_factory=list, alias="queryString")
    """List of query parameters in the URL"""
    post_data: PostData | None = Field(default=None, alias="postData")
    """POST data included in the request body"""

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

    def repr_post_data(self) -> str | None:
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
