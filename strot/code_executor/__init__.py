from typing import Literal

from strot.code_executor.base import CodeExecutionError, CodeExecutorT

__all__ = ("CodeExecutorT", "CodeExecutionError", "CodeExecutorType", "create_executor")

CodeExecutorType = Literal["unsafe", "e2b"]


def create_executor(type: CodeExecutorType):
    """Create a code executor instance based on the specified type.

    Args:
        type: The type of executor to create

    Returns:
        CodeExecutor instance

    Raises:
        ValueError: If type is not supported
    """
    if type == "unsafe":
        from strot.code_executor.unsafe import UnsafeCodeExecutor

        return UnsafeCodeExecutor()
    elif type == "e2b":
        from strot.code_executor.e2b import E2BCodeExecutor

        return E2BCodeExecutor()
    else:
        raise ValueError(f"Unsupported code executor type: {type}")
