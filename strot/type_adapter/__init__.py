import typing as t
from copy import deepcopy

from jsonref import replace_refs

from strot.type_adapter.utils import (
    drop_titles as drop_titles_fn,
)
from strot.type_adapter.utils import (
    extract_python_object,
    generate_random_suffix,
    transform_to_anthropic_schema,
    transform_to_gemini_schema,
    transform_to_openai_schema,
    update_schema,
)

T_Retval = t.TypeVar("T_Retval")


class TypeAdapter(t.Generic[T_Retval]):
    """
    Schema generation from and data validation against given type.

    A wrapper around Pydantic's `TypeAdapter` to:
    - populate docstring from object type into schema.
    - support schema transformation for different LLM providers.
    """

    @t.overload
    def __init__(self, __type: type[T_Retval]) -> None: ...
    @t.overload
    def __init__(self, __type: t.Callable[..., T_Retval]) -> None: ...

    def __init__(self, __type: type[T_Retval] | t.Callable[..., T_Retval]) -> None:
        from pydantic.fields import FieldInfo
        from pydantic.type_adapter import TypeAdapter as PydanticTypeAdapter

        self.__id = None
        if t.get_origin(__type) is t.Annotated:
            if len(args := t.get_args(__type)) < 2:
                raise TypeError("Annotated types must have more than 1 argument.")
            if isinstance(field := args[1], FieldInfo) and field.alias:
                self.__id = field.alias

        if self.__id is None:
            self.__id = getattr(__type, "__name__", f"id_{generate_random_suffix()}")

        self.ref = __type
        self.__adapter = PydanticTypeAdapter[T_Retval](type=self.ref)
        self.__schema: dict[str, t.Any] | None = None

    @property
    def id(self) -> str:
        return self.__id  # type: ignore[return-value]

    def generate_schema(
        self,
        resolve_refs: bool = False,
        drop_titles: bool = True,
    ) -> dict[str, t.Any]:
        """
        Get the JSON schema for the type.

        The schema is generated on first access and cached for subsequent calls.
        """
        if self.__schema is None:
            base_schema = self.__adapter.json_schema()
            if resolve_refs and "$defs" in base_schema:
                base_schema = replace_refs(base_schema, lazy_load=False)
                _ = base_schema.pop("$defs", None)
            self.__schema = update_schema(self.ref, base_schema)  # type: ignore[arg-type]

        if drop_titles:
            return drop_titles_fn(deepcopy(self.__schema))
        return self.__schema

    @property
    def openai_schema(self) -> dict[str, t.Any]:
        """Get the JsON schema in openai tool calling format."""
        return transform_to_openai_schema(self.id, self.generate_schema(drop_titles=True))

    @property
    def anthropic_schema(self) -> dict[str, t.Any]:
        """Get the JsON schema in anthropic tool calling format."""
        return transform_to_anthropic_schema(self.id, self.generate_schema(drop_titles=True))

    @property
    def gemini_schema(self) -> dict[str, t.Any]:
        """Get the JsON schema in gemini tool calling format."""
        return transform_to_gemini_schema(self.id, self.generate_schema(drop_titles=True))

    def validate_python(self, obj: t.Any, **kwargs: t.Any) -> T_Retval:
        """
        Validate a Python object against the descripted object.

        :param obj: Python object to validate
        :param kwargs: Extra keyword arguments
        :raises ValidationError: If validation fails
        :return: The validated object
        """
        obj = extract_python_object(obj, schema=self.generate_schema(), value_type="python")
        return self.__adapter.validate_python(obj, **kwargs)

    def validate_json(self, data: str | bytes | bytearray, **kwargs: t.Any) -> T_Retval:
        """
        Validate JSON data against the descripted object.

        :param data: JSON data to validate
        :param kwargs: Extra keyword arguments
        :raises ValidationError: If validation fails
        :return: The validated object
        """
        obj = extract_python_object(data, schema=self.generate_schema(), value_type="json")
        return self.__adapter.validate_python(obj, **kwargs)
