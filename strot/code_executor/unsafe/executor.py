from typing import Any, Literal

from pydantic import PrivateAttr

from strot.code_executor.base import BaseCodeExecutor, CodeExecutionError

from .code_meta import CodeMeta

__all__ = ("UnsafeCodeExecutor",)


class UnsafeCodeExecutor(BaseCodeExecutor):
    """Code executor that uses Python's exec() function directly.

    This maintains compatibility with the current implementation but
    provides no sandboxing or security guarantees.
    """

    type: Literal["unsafe"] = "unsafe"
    _namespace: dict[str, Any] = PrivateAttr(default_factory=dict)

    async def execute(self, code: str) -> Any:
        """Execute Python code and return the result.

        Args:
            code: Python code to execute

        Returns:
            The result of code execution

        Raises:
            CodeExecutionError: If code execution fails
        """
        try:
            code_meta = CodeMeta.from_code(code)

            if code_meta.to_exec:
                exec(code_meta.to_exec, self._namespace, self._namespace)  # noqa: S102

            if code_meta.to_eval:
                return eval(code_meta.to_eval, self._namespace, self._namespace)  # noqa: S307

        except Exception as e:
            raise CodeExecutionError(f"Code execution failed: {e}") from e

    async def is_definition_available(self, name: str) -> bool:
        """Check if a definition is available in the namespace.

        Args:
            name: The name of the definition to check

        Returns:
            True if the definition exists in namespace, False otherwise
        """
        return name in self._namespace
