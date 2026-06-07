from ai_workspace_api.modules.indexing.chunking import (
    SemanticChunker,
    detect_language,
)


def test_detect_language_python() -> None:
    assert detect_language("main.py") == "python"
    assert detect_language("src/app/utils.py") == "python"
    assert detect_language("types.pyi") == "python"


def test_detect_language_typescript() -> None:
    assert detect_language("app.ts") == "typescript"
    assert detect_language("component.tsx") == "typescript"


def test_detect_language_go() -> None:
    assert detect_language("main.go") == "go"


def test_detect_language_special_filenames() -> None:
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("Makefile") == "makefile"
    assert detect_language("CMakeLists.txt") == "cmake"


def test_detect_language_unknown() -> None:
    assert detect_language("file.xyz") is None


def test_detect_language_extended() -> None:
    assert detect_language("main.c") == "c"
    assert detect_language("main.cpp") == "cpp"
    assert detect_language("main.rs") == "rust"
    assert detect_language("main.swift") == "swift"
    assert detect_language("main.php") == "php"
    assert detect_language("main.rb") == "ruby"
    assert detect_language("main.java") == "java"
    assert detect_language("main.kt") == "kotlin"
    assert detect_language("main.scala") == "scala"
    assert detect_language("main.ex") == "elixir"
    assert detect_language("main.hs") == "haskell"
    assert detect_language("script.sh") == "shell"
    assert detect_language("script.ps1") == "powershell"
    assert detect_language("infra.tf") == "terraform"
    assert detect_language("style.css") == "css"
    assert detect_language("style.scss") == "scss"
    assert detect_language("page.html") == "html"
    assert detect_language("query.sql") == "sql"
    assert detect_language("schema.graphql") == "graphql"
    assert detect_language("main.dart") == "dart"


def test_chunker_empty_content() -> None:
    chunker = SemanticChunker()
    assert chunker.chunk("") == []


def test_chunker_small_file() -> None:
    content = "line1\nline2\nline3"
    chunker = SemanticChunker()
    chunks = chunker.chunk(content)
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3


def test_chunker_python_functions() -> None:
    content = """import os

def foo():
    pass

def bar():
    pass

class Baz:
    def method(self):
        pass
"""
    chunker = SemanticChunker(min_chunk_lines=1)
    chunks = chunker.chunk(content, language="python")
    assert len(chunks) >= 3
    symbols = [c.symbol for c in chunks if c.symbol]
    assert "foo" in symbols
    assert "bar" in symbols
    assert "Baz" in symbols


def test_chunker_go_functions() -> None:
    content = """package main

func main() {
    fmt.Println("hello")
}

func helper() int {
    return 42
}

type Config struct {
    Name string
}
"""
    chunker = SemanticChunker(min_chunk_lines=1)
    chunks = chunker.chunk(content, language="go")
    symbols = [c.symbol for c in chunks if c.symbol]
    assert "main" in symbols
    assert "helper" in symbols
    assert "Config" in symbols


def test_chunker_respects_max_lines() -> None:
    lines = [f"line {i}" for i in range(300)]
    content = "\n".join(lines)
    chunker = SemanticChunker(max_chunk_lines=100)
    chunks = chunker.chunk(content)
    for chunk in chunks:
        assert (chunk.end_line - chunk.start_line + 1) <= 110  # allow some flex for merging


def test_chunker_fallback_blank_lines() -> None:
    content = "first block\nline2\n\nsecond block\nline4\n\nthird block"
    chunker = SemanticChunker(min_chunk_lines=1)
    chunks = chunker.chunk(content, language=None)
    assert len(chunks) >= 2


def test_fixed_chunk_line_ranges() -> None:
    """Preserves original test behavior."""
    content = "\n".join(f"line {number}" for number in range(250))
    chunker = SemanticChunker(max_chunk_lines=100)
    chunks = chunker.chunk(content, language=None)
    assert chunks[0].start_line == 1
