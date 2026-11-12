from ai_workspace_api.modules.indexing.parsers import (
    FallbackParser,
    PythonCodeParser,
    TypeScriptCodeParser,
    get_parser_for_language,
)


def test_python_ast_parser_extracts_classes_and_methods() -> None:
    code = (
        "import os\n"
        "import sys\n"
        "\n"
        "class AuthService:\n"
        "    def __init__(self, key: str) -> None:\n"
        "        self.key = key\n"
        "\n"
        "    async def authenticate(self, token: str) -> bool:\n"
        "        return token == self.key\n"
        "\n"
        "def helper_func() -> str:\n"
        "    return 'ok'\n"
    )
    parser = PythonCodeParser(max_chunk_lines=100)
    chunks = parser.parse_and_chunk(code, file_path="auth.py")

    assert len(chunks) >= 4

    # 1. Imports chunk
    import_chunk = next(c for c in chunks if c.symbol == "imports")
    assert import_chunk.symbol_type == "import"
    assert import_chunk.start_line == 1
    assert import_chunk.end_line == 2

    # 2. Methods
    init_chunk = next(c for c in chunks if c.symbol == "__init__")
    assert init_chunk.symbol_type == "method"
    assert init_chunk.parent_scope == "AuthService"
    assert init_chunk.start_line == 5
    assert init_chunk.end_line == 6

    auth_chunk = next(c for c in chunks if c.symbol == "authenticate")
    assert auth_chunk.symbol_type == "method"
    assert auth_chunk.parent_scope == "AuthService"
    assert auth_chunk.start_line == 8
    assert auth_chunk.end_line == 9

    # 3. Top-level function
    helper_chunk = next(c for c in chunks if c.symbol == "helper_func")
    assert helper_chunk.symbol_type == "function"
    assert helper_chunk.parent_scope is None
    assert helper_chunk.start_line == 11
    assert helper_chunk.end_line == 12


def test_python_parser_sub_chunks_oversized_function() -> None:
    func_lines = ["def huge_workload():"] + [f"    step_{i} = {i}" for i in range(120)]
    code = "\n".join(func_lines)

    parser = PythonCodeParser(max_chunk_lines=50)
    chunks = parser.parse_and_chunk(code, file_path="workload.py")

    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk.symbol == "huge_workload"
        assert chunk.symbol_type == "function"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 50
    assert chunks[1].start_line == 51
    assert chunks[1].end_line == 100
    assert chunks[2].start_line == 101
    assert chunks[2].end_line == 121


def test_python_parser_gracefully_handles_malformed_syntax() -> None:
    malformed_code = "def broken_func(\n  print('missing closing paren and colon'"
    parser = PythonCodeParser(max_chunk_lines=50)
    chunks = parser.parse_and_chunk(malformed_code, file_path="broken.py")

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert chunks[0].symbol is None


def test_typescript_parser_extracts_classes_interfaces_and_functions() -> None:
    code = (
        "import React from 'react';\n"
        "import { useState } from 'react';\n"
        "\n"
        "export interface UserProfile {\n"
        "  id: string;\n"
        "  name: string;\n"
        "}\n"
        "\n"
        "export type Status = 'active' | 'disabled';\n"
        "\n"
        "export class UserManager {\n"
        "  fetchUser(id: string): UserProfile {\n"
        "    return { id, name: 'Alice' };\n"
        "  }\n"
        "}\n"
        "\n"
        "export async function processUsers(): Promise<void> {\n"
        "  console.log('done');\n"
        "}\n"
    )
    parser = TypeScriptCodeParser(max_chunk_lines=100)
    chunks = parser.parse_and_chunk(code, file_path="user.ts")

    # Verify imports
    import_chunk = next(c for c in chunks if c.symbol == "imports")
    assert import_chunk.symbol_type == "import"

    # Verify interface
    iface_chunk = next(c for c in chunks if c.symbol == "UserProfile")
    assert iface_chunk.symbol_type == "interface"
    assert iface_chunk.start_line == 4
    assert iface_chunk.end_line == 7

    # Verify type alias
    type_chunk = next(c for c in chunks if c.symbol == "Status")
    assert type_chunk.symbol_type == "type_alias"

    # Verify method inside class
    method_chunk = next(c for c in chunks if c.symbol == "fetchUser")
    assert method_chunk.symbol_type == "method"
    assert method_chunk.parent_scope == "UserManager"

    # Verify function
    fn_chunk = next(c for c in chunks if c.symbol == "processUsers")
    assert fn_chunk.symbol_type == "function"
    assert fn_chunk.start_line == 17


def test_parser_factory_routes_languages() -> None:
    py_parser = get_parser_for_language("python")
    ts_parser = get_parser_for_language("typescript")
    js_parser = get_parser_for_language("javascript")
    md_parser = get_parser_for_language("markdown")

    assert isinstance(py_parser, PythonCodeParser)
    assert isinstance(ts_parser, TypeScriptCodeParser)
    assert isinstance(js_parser, TypeScriptCodeParser)
    assert isinstance(md_parser, FallbackParser)
