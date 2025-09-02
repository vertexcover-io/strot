from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import schema

__all__ = (
    "ANALYZE_CURRENT_VIEW_PROMPT_TEMPLATE",
    "GENERATE_EXTRACTION_CODE_PROMPT_TEMPLATE",
    "PARAMETER_DETECTION_PROMPT_TEMPLATE",
    "schema",
)

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))  # noqa: S701

ANALYZE_CURRENT_VIEW_PROMPT_TEMPLATE = _env.get_template("analyze_current_view.jinja")

GENERATE_EXTRACTION_CODE_PROMPT_TEMPLATE = _env.get_template("generate_extraction_code.jinja")

PARAMETER_DETECTION_PROMPT_TEMPLATE = _env.get_template("parameter_detection.jinja")
