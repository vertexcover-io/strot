from typing import Any, TypeVar

from pydantic import BaseModel


class BaseCodeExecutor(BaseModel):
    """Code executor sub class."""

    type: str

    async def execute(self, code: str) -> Any:
        """Execute Python code and return the result.

        Args:
            code: Python code to execute

        Returns:
            The result of code execution

        Raises:
            CodeExecutionError: If code execution fails
        """
        raise NotImplementedError("Subclasses must implement this method.")

    async def is_definition_available(self, name: str) -> bool:
        """Check if a definition (function, variable or any kind of definition) is available in the execution context.

        Args:
            name: The name of the definition to check

        Returns:
            True if the definition exists, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method.")


CodeExecutorT = TypeVar("CodeExecutorT", bound=BaseCodeExecutor)


class CodeExecutionError(Exception):
    """Exception raised when code execution fails."""

    pass
