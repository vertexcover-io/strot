import ast
import os
import sys
from contextlib import suppress
from typing import Any, Literal, Self

from e2b_code_interpreter import Sandbox
from pydantic import PrivateAttr, model_validator

from strot.code_executor.base import BaseCodeExecutor, CodeExecutionError

__all__ = ("E2BCodeExecutor",)


class E2BCodeExecutor(BaseCodeExecutor):
    """Code executor that uses E2B Code Interpreter for safe sandboxed execution."""

    type: Literal["e2b"] = "e2b"
    _sandbox: Sandbox | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_api_key(self) -> Self:
        """Validate that E2B_API_KEY is available in environment."""
        if not os.getenv("E2B_API_KEY"):
            raise ValueError("E2B API key is required. Set E2B_API_KEY environment variable.")
        return self

    async def _get_sandbox(self) -> Sandbox:
        """Get or create E2B sandbox instance."""
        if self._sandbox is None:
            self._sandbox = Sandbox.create()
        return self._sandbox

    async def execute(self, code: str) -> Any:
        """Execute Python code in E2B sandbox and return the result.

        Args:
            code: Python code to execute

        Returns:
            The result of code execution

        Raises:
            CodeExecutionError: If code execution fails
        """
        try:
            sandbox = await self._get_sandbox()

            # Execute the code in E2B sandbox
            execution = sandbox.run_code(code)

            if execution.error:
                raise CodeExecutionError(  # noqa: TRY301
                    f"Error executing code: {execution.error.name}: {execution.error.value}\n"
                    f"{execution.error.traceback}"
                )

            if logs := execution.logs:
                for out in logs.stdout:
                    sys.stdout.write(out)
                for err in logs.stderr:
                    sys.stderr.write(err)

            if not execution.results:
                return None

            result_text = execution.results[0].text
            try:
                return ast.literal_eval(result_text)
            except (ValueError, SyntaxError):
                return result_text

        except Exception as e:
            if isinstance(e, CodeExecutionError):
                raise
            raise CodeExecutionError(f"Error executing code: {e}") from e

    async def is_definition_available(self, name: str) -> bool:
        """Check if a definition is available in the E2B sandbox.

        Args:
            name: The name of the definition to check

        Returns:
            True if the definition exists in sandbox, False otherwise
        """
        try:
            output = await self.execute(f"'exists' if {name!r} in locals() or {name!r} in globals() else 'not_exists'")

            return output.strip() == "exists"

        except CodeExecutionError:
            return False

    async def close(self):
        """Clean up E2B sandbox resources."""
        if self._sandbox:
            self._sandbox.kill()
            self._sandbox = None

    def __del__(self):
        """Cleanup when executor is destroyed."""
        if self._sandbox:
            with suppress(Exception):
                self._sandbox.kill()
