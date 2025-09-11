from __future__ import annotations

import ast
from dataclasses import dataclass
from types import CodeType
from typing import Literal

__all__ = ("CodeMeta",)


def compile_code(__code: ast.Module | str, filename: str, mode: Literal["exec", "eval"]) -> CodeType:
    """
    Compile the given code.

    Args:
        __code: The code to compile
        filename: The filename to use for the code
        mode: The compilation mode

    Returns:
        Compiled code object
    """
    if isinstance(__code, str):
        __code = ast.parse(__code, filename=filename, mode=mode)  # type: ignore[assignment]
    return compile(__code, filename=filename, mode=mode)


@dataclass(frozen=True)
class CodeMeta:
    """Represents the metadata of a code block"""

    to_exec: CodeType | None
    """The compiled code to execute"""

    to_eval: CodeType | None
    """The compiled code to evaluate"""

    @classmethod
    def from_ast_module(cls, __mod: ast.Module, filename: str = "<string>") -> CodeMeta:
        """
        Create a CodeMeta object from an AST module.

        Args:
            __mod: The AST module to extract metadata from
            filename: The filename to use for the AST module

        Returns:
            CodeMeta object
        """
        if not __mod.body:
            return cls(to_exec=None, to_eval=None)

        to_exec, to_eval = None, None
        mod_copy = ast.Module(body=__mod.body.copy(), type_ignores=__mod.type_ignores)

        if not hasattr(stmt := mod_copy.body[-1], "body"):
            try:
                to_eval = compile_code(ast.unparse(stmt), filename, "eval")
                mod_copy.body.pop()
            except SyntaxError:
                # some statements, for example - imports, are not allowed in eval
                pass

        if mod_copy.body:
            to_exec = compile_code(mod_copy, filename, "exec")

        return cls(to_exec=to_exec, to_eval=to_eval)

    @classmethod
    def from_code(cls, __code: str, filename: str = "<string>") -> CodeMeta:
        """
        Create a CodeMeta object from code string.

        Args:
            __code: The code string to extract metadata from
            filename: The filename to use for the code string

        Returns:
            CodeMeta object
        """
        mod = ast.parse(__code, filename=filename)
        return cls.from_ast_module(mod, filename=filename)
