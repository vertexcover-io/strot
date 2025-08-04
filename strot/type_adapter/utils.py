from __future__ import annotations

import random
import string
import typing as t

from docstring_parser import Docstring, parse
from pydantic_core import from_json

__all__ = (
    "build_description",
    "drop_titles",
    "update_schema",
    "transform_to_openai_schema",
    "transform_to_anthropic_schema",
    "transform_to_gemini_schema",
)


def build_description(docstring: Docstring) -> str | None:
    """
    Build description from docstring.

    :param docstring: A Docstring object.
    """

    result = []
    if s_desc := (docstring.short_description or "").strip():
        result.append(s_desc)
    if l_desc := (docstring.long_description or "").strip():
        result.append(l_desc.replace("\n", " "))

    return " ".join(result).strip("\n") if result else None


def update_object_schema(__type: type, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """
    Update object type schema with its type's docstring
    """
    typehints = t.get_type_hints(__type)
    docstring = parse(__type.__doc__ or "")
    if desc := build_description(docstring) or schema.get("description"):
        schema["description"] = desc
    for p_name, p_schema in schema["properties"].items():
        if p_name in typehints:
            schema["properties"][p_name] = update_schema(typehints[p_name], p_schema)
        param = next((p for p in docstring.params if p.arg_name == p_name), None)
        if param and (p_desc := param.description or p_schema.get("description")):
            schema["properties"][p_name]["description"] = p_desc
    return schema


def update_array_schema(__type: type, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """
    Update array type schema items/prefixItems with its type's docstring
    """
    if "items" in schema:
        schema["items"] = update_schema(__type, schema["items"])
    elif "prefixItems" in schema and all("title" in item for item in schema["prefixItems"]):
        # we assume it's named tuple
        prefix_items = []
        docstring = parse(__type.__doc__ or "")
        p_name_to_desc = {p.arg_name: p.description for p in docstring.params}
        for p_schema in schema["prefixItems"]:
            if (p_name := p_schema["title"].lower()) in p_name_to_desc:
                p_schema["description"] = p_name_to_desc[p_name]
            prefix_items.append(p_schema)
        schema["prefixItems"] = prefix_items
    return schema


def update_schema(__type: type, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Update type schema"""
    if "anyOf" in schema:
        of_key = "anyOf"
    elif "oneOf" in schema:
        of_key = "oneOf"
    else:
        of_key = None

    origin, arg_types = t.get_origin(__type) or __type, t.get_args(__type)
    if of_key is not None:
        schema[of_key] = [update_schema(tp, sc) for tp, sc in zip(arg_types, schema[of_key])]
    elif schema.get("type") == "object" and "properties" in schema:
        if not schema.get("additionalProperties", True):
            _ = schema.pop("additionalProperties")
        schema = update_object_schema(origin, schema=schema)
    elif schema.get("type") == "array":
        schema = update_array_schema(arg_types[0] if arg_types else origin, schema=schema)

    return schema


def drop_titles(__schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Remove title key-value pair from the entire schema"""
    __schema.pop("title", None)

    if "anyOf" in __schema:
        for sub_schema in __schema["anyOf"]:
            drop_titles(sub_schema)
    elif "oneOf" in __schema:
        for sub_schema in __schema["oneOf"]:
            drop_titles(sub_schema)
    elif __schema.get("type") == "object" and "properties" in __schema:
        for prop in __schema["properties"].values():
            drop_titles(prop)
    elif __schema.get("type") == "array" and "items" in __schema:
        drop_titles(__schema["items"])

    return __schema


def transform_to_fc_schema(id: str, schema: dict[str, t.Any], params_key: str) -> dict[str, t.Any]:
    """Transform to LLM function calling format"""
    description_dict: dict[str, str] = {}
    if desc := schema.pop("description", None):
        description_dict["description"] = desc
    if schema.get("type") != "object":
        schema = {"type": "object", "properties": {"input": schema}, "required": ["input"]}
    return {"name": id, **description_dict, params_key: schema}


def extract_python_object(__value: t.Any, schema: dict[str, t.Any], value_type: t.Literal["json", "python"]) -> t.Any:
    """
    Extract python value descriptor's validator is expecting.
    """
    if value_type == "json":
        __value = from_json(__value)

    if schema.get("type") == "object":
        return __value

    if isinstance(__value, dict) and "input" in __value:
        return __value["input"]

    return __value


def transform_to_openai_schema(id: str, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Transform the schema to openai format"""
    return transform_to_fc_schema(id=id, schema=schema, params_key="parameters")


def transform_to_anthropic_schema(id: str, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """Transform the schema to anthropic format"""
    return transform_to_fc_schema(id=id, schema=schema, params_key="input_schema")


def transform_to_gemini_schema(id: str, schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """
    Transform the schema to gemini format

    Yoinked from: https://github.com/instructor-ai/instructor/blob/main/instructor/utils.py#L287
    """
    from pydantic import BaseModel

    class FCSchemaModel(BaseModel):
        description: t.Optional[str] = None  # noqa: UP007
        enum: t.Optional[list[str]] = None  # noqa: UP007
        example: t.Optional[t.Any] = None  # noqa: UP007
        format: t.Optional[str] = None  # noqa: UP007
        nullable: t.Optional[bool] = None  # noqa: UP007
        items: t.Optional[FCSchemaModel] = None  # noqa: UP007
        required: t.Optional[list[str]] = None  # noqa: UP007
        type: str
        properties: t.Optional[dict[str, FCSchemaModel]] = None  # noqa: UP007

    def add_enum_format(obj: dict[str, t.Any]) -> dict[str, t.Any]:
        if isinstance(obj, dict):
            new_dict: dict[str, t.Any] = {}
            for key, value in obj.items():
                new_dict[key] = add_enum_format(value)
                if key == "enum":
                    new_dict["format"] = "enum"
            return new_dict
        else:
            return obj

    schema_model = FCSchemaModel(**add_enum_format(schema))
    return transform_to_fc_schema(
        id=id,
        schema=schema_model.model_dump(exclude_none=True, exclude_unset=True),
        params_key="parameters",
    )


def generate_random_suffix(length: int = 4) -> str:
    choices = string.ascii_lowercase + string.digits
    return "".join(random.choice(choices) for _ in range(length))  # noqa: S311
