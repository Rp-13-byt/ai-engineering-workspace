from pathlib import Path

from ai_workspace_api.modules.indexing.parsers.base import BaseCodeParser
from ai_workspace_api.modules.indexing.parsers.fallback_parser import FallbackParser
from ai_workspace_api.modules.indexing.parsers.python_parser import PythonCodeParser
from ai_workspace_api.modules.indexing.parsers.typescript_parser import TypeScriptCodeParser


def get_parser_for_language(language: str | None, max_chunk_lines: int = 100) -> BaseCodeParser:
    if not language:
        return FallbackParser(max_chunk_lines=max_chunk_lines)

    lang = language.lower().strip()
    if lang == "python":
        return PythonCodeParser(max_chunk_lines=max_chunk_lines)
    if lang in ("typescript", "javascript"):
        return TypeScriptCodeParser(max_chunk_lines=max_chunk_lines)

    return FallbackParser(max_chunk_lines=max_chunk_lines)


def get_parser_for_path(path_str: str, max_chunk_lines: int = 100) -> BaseCodeParser:
    ext = Path(path_str).suffix.lower()
    if ext == ".py":
        return PythonCodeParser(max_chunk_lines=max_chunk_lines)
    if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        return TypeScriptCodeParser(max_chunk_lines=max_chunk_lines)
    return FallbackParser(max_chunk_lines=max_chunk_lines)
