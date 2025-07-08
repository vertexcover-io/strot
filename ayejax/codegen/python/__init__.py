from __future__ import annotations

from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader

from ayejax.types import Output

__all__ = ("generate",)

jinja_env = Environment(  # noqa: S701
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
)
jinja_env.filters["repr"] = lambda v: repr(v)


def generate(*, output: Output, template: Literal["requests", "httpx"]) -> str:
    jinja_template = jinja_env.get_template(f"{template}.jinja")
    return jinja_template.render(output=output)
