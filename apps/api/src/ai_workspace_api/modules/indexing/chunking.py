"""Language-aware semantic chunking for code indexing."""
import re
from dataclasses import dataclass

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    # Systems
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hxx": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".zig": "zig",
    # JVM
    ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
    ".groovy": "groovy",
    ".clj": "clojure",
    # .NET
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vb",
    # Web
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript",
    ".vue": "vue",
    ".svelte": "svelte",
    # Scripting
    ".py": "python", ".pyi": "python",
    ".rb": "ruby",
    ".php": "php",
    ".pl": "perl", ".pm": "perl",
    ".lua": "lua",
    ".r": "r", ".R": "r",
    ".jl": "julia",
    ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    # Shell
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".fish": "shell",
    ".ps1": "powershell", ".psm1": "powershell",
    ".bat": "batch", ".cmd": "batch",
    # Data / Config
    ".sql": "sql",
    ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf",
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".ini": "ini", ".cfg": "ini",
    ".env": "dotenv",
    ".csv": "csv",
    # Markup / Docs
    ".md": "markdown", ".mdx": "markdown",
    ".rst": "rst",
    ".tex": "latex",
    ".html": "html", ".htm": "html",
    ".css": "css",
    ".scss": "scss", ".sass": "sass", ".less": "less",
    # Infra
    ".tf": "terraform", ".hcl": "hcl",
    ".nix": "nix",
    # Mobile
    ".swift": "swift",
    ".m": "objective-c", ".mm": "objective-c",
    ".dart": "dart",
}

FILENAME_LANGUAGES: dict[str, str] = {
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "CMakeLists.txt": "cmake",
    "Jenkinsfile": "groovy",
    "Vagrantfile": "ruby",
    "Rakefile": "ruby",
    "Gemfile": "ruby",
    "BUILD": "starlark",
    "BUILD.bazel": "starlark",
    "WORKSPACE": "starlark",
}

# Regex patterns for semantic boundary detection per language family.
# Each pattern matches the START of a top-level definition.
_BOUNDARY_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^(?:class |def |async def |@)",
        re.MULTILINE,
    ),
    "javascript": re.compile(
        r"^(?:function |class |export |const |let |var |async function |module\.exports)",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r"^(?:function |class |export |const |let |var "
        r"|async function |interface |type |enum |namespace |abstract )",
        re.MULTILINE,
    ),
    "go": re.compile(
        r"^(?:func |type |var |const |package )",
        re.MULTILINE,
    ),
    "rust": re.compile(
        r"^(?:pub |fn |impl |struct |enum |trait |mod |use |type |const |static )",
        re.MULTILINE,
    ),
    "java": re.compile(
        r"^(?:public |private |protected |class |interface |enum |abstract |static |@)",
        re.MULTILINE,
    ),
    "kotlin": re.compile(
        r"^(?:fun |class |object |interface |enum "
        r"|data |sealed |abstract |annotation |val |var )",
        re.MULTILINE,
    ),
    "csharp": re.compile(
        r"^(?:public |private |protected |internal "
        r"|class |interface |enum |struct |namespace |static |abstract |async )",
        re.MULTILINE,
    ),
    "ruby": re.compile(
        r"^(?:class |module |def |end$)",
        re.MULTILINE,
    ),
    "php": re.compile(
        r"^(?:class |function |interface |trait "
        r"|namespace |abstract |public |private |protected )",
        re.MULTILINE,
    ),
    "swift": re.compile(
        r"^(?:func |class |struct |enum |protocol "
        r"|extension |import |public |private |internal |open )",
        re.MULTILINE,
    ),
    "c": re.compile(
        r"^(?:[a-zA-Z_][a-zA-Z0-9_ *]*\([^)]*\)\s*\{|#include |#define "
        r"|typedef |struct |enum )",
        re.MULTILINE,
    ),
    "cpp": re.compile(
        r"^(?:class |namespace |template |struct |enum "
        r"|void |int |auto |[a-zA-Z_][a-zA-Z0-9_:]*\s+[a-zA-Z_])",
        re.MULTILINE,
    ),
    "sql": re.compile(
        r"^(?:CREATE |ALTER |DROP |INSERT |SELECT |UPDATE |DELETE |WITH |-- )",
        re.MULTILINE | re.IGNORECASE,
    ),
    "shell": re.compile(
        r"^(?:[a-zA-Z_][a-zA-Z0-9_]*\(\)|function )",
        re.MULTILINE,
    ),
}

_SYMBOL_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(
        r"^(?:class|def|async def)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "javascript": re.compile(
        r"^(?:function|class|const|let|var|async function)"
        r"\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
    ),
    "typescript": re.compile(
        r"^(?:function|class|const|let|var|async function|interface|type|enum)"
        r"\s+([a-zA-Z_$][a-zA-Z0-9_$]*)"
    ),
    "go": re.compile(
        r"^(?:func|type)\s+(?:\([^)]*\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "rust": re.compile(
        r"^(?:pub\s+)?(?:fn|struct|enum|trait|impl|mod|type)"
        r"\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "java": re.compile(
        r"(?:public|private|protected)?\s*(?:static\s+)?"
        r"(?:class|interface|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "kotlin": re.compile(
        r"^(?:fun|class|object|interface|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "csharp": re.compile(
        r"(?:public|private|protected|internal)?\s*(?:static\s+)?"
        r"(?:class|interface|enum|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "ruby": re.compile(
        r"^(?:class|module|def)\s+([a-zA-Z_][a-zA-Z0-9_!?]*)"
    ),
    "php": re.compile(
        r"^(?:class|function|interface|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
    "swift": re.compile(
        r"^(?:func|class|struct|enum|protocol)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    ),
}


@dataclass(frozen=True)
class Chunk:
    """A chunk of source code with line range and optional symbol name."""

    start_line: int
    end_line: int
    content: str
    symbol: str | None = None


def detect_language(path: str) -> str | None:
    """Detect programming language from file path."""
    import pathlib as _pathlib

    name = _pathlib.PurePosixPath(path).name
    if name in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[name]

    suffix = _pathlib.PurePosixPath(path).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(suffix)


def _extract_symbol(line: str, language: str | None) -> str | None:
    """Try to extract a symbol name from a code line."""
    if language is None or language not in _SYMBOL_PATTERNS:
        return None
    match = _SYMBOL_PATTERNS[language].search(line)
    return match.group(1) if match else None


class SemanticChunker:
    """Splits source code into semantically meaningful chunks."""

    def __init__(
        self,
        max_chunk_lines: int = 120,
        min_chunk_lines: int = 10,
        overlap_lines: int = 5,
    ) -> None:
        self.max_chunk_lines = max_chunk_lines
        self.min_chunk_lines = min_chunk_lines
        self.overlap_lines = overlap_lines

    def chunk(
        self,
        content: str,
        language: str | None = None,
    ) -> list[Chunk]:
        """Split content into semantically aware chunks."""
        lines = content.splitlines()
        if not lines:
            return []

        boundaries = self._find_boundaries(lines, language)

        if not boundaries:
            return self._fixed_chunk(lines)

        # Ensure 0 is a boundary
        if boundaries[0] != 0:
            boundaries.insert(0, 0)

        chunks: list[Chunk] = []
        for i, start in enumerate(boundaries):
            if i + 1 < len(boundaries):
                end = boundaries[i + 1]
            else:
                end = len(lines)

            # If the segment is too large, sub-chunk it
            if end - start > self.max_chunk_lines:
                sub_chunks = self._fixed_chunk(
                    lines[start:end],
                    offset=start,
                    language=language,
                )
                chunks.extend(sub_chunks)
            else:
                chunk_lines = lines[start:end]
                symbol = (
                    _extract_symbol(chunk_lines[0], language)
                    if chunk_lines
                    else None
                )
                chunks.append(
                    Chunk(
                        start_line=start + 1,
                        end_line=end,
                        content="\n".join(chunk_lines),
                        symbol=symbol,
                    )
                )

        # Merge small trailing chunks
        if (
            len(chunks) >= 2
            and (chunks[-1].end_line - chunks[-1].start_line + 1)
            < self.min_chunk_lines
        ):
            last = chunks.pop()
            prev = chunks.pop()
            merged_content = prev.content + "\n" + last.content
            chunks.append(
                Chunk(
                    start_line=prev.start_line,
                    end_line=last.end_line,
                    content=merged_content,
                    symbol=prev.symbol,
                )
            )

        return chunks

    def _find_boundaries(
        self, lines: list[str], language: str | None
    ) -> list[int]:
        """Find line indices where semantic boundaries occur."""
        if language is None:
            return self._find_blank_line_boundaries(lines)

        pattern = _BOUNDARY_PATTERNS.get(language)
        if pattern is None:
            return self._find_blank_line_boundaries(lines)

        boundaries: list[int] = []
        for i, line in enumerate(lines):
            if pattern.match(line):
                boundaries.append(i)

        if not boundaries:
            return self._find_blank_line_boundaries(lines)

        return boundaries

    def _find_blank_line_boundaries(self, lines: list[str]) -> list[int]:
        """Fallback: find boundaries at blank lines preceded by non-blank."""
        boundaries: list[int] = [0]
        for i, line in enumerate(lines):
            if (
                i > 0
                and line.strip() == ""
                and i + 1 < len(lines)
                and lines[i + 1].strip() != ""
            ):
                boundaries.append(i + 1)
        return boundaries

    def _fixed_chunk(
        self,
        lines: list[str],
        offset: int = 0,
        language: str | None = None,
    ) -> list[Chunk]:
        """Fixed-size chunking as a fallback."""
        chunks: list[Chunk] = []
        for start in range(0, len(lines), self.max_chunk_lines):
            end = min(start + self.max_chunk_lines, len(lines))
            chunk_lines = lines[start:end]
            symbol = (
                _extract_symbol(chunk_lines[0], language)
                if chunk_lines
                else None
            )
            chunks.append(
                Chunk(
                    start_line=offset + start + 1,
                    end_line=offset + end,
                    content="\n".join(chunk_lines),
                    symbol=symbol,
                )
            )
        return chunks
