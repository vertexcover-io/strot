from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


def read(path: str | Path) -> Data:
    """
    Read and parse a HAR file into a Data object.

    Args:
        path: Path to the HAR file to read

    Returns:
        Data: Parsed HAR data model

    Raises:
        FileNotFoundError: If the specified file does not exist
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path!r}")

    return Data.model_validate_json(path.read_bytes())


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
    url: HttpUrl
    """The full URL of the request"""
    cookies: list[Pair] = Field(default_factory=list)
    """List of cookies sent with the request"""
    headers: list[Pair] = Field(default_factory=list)
    """List of HTTP headers sent with the request"""
    queries: list[Pair] = Field(default_factory=list, alias="queryString")
    """List of query parameters in the URL"""
    post_data: Optional[PostData] = Field(default=None, alias="postData")  # noqa: UP007
    """POST data included in the request body"""
