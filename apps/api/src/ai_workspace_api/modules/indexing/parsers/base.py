from abc import ABC, abstractmethod

from ai_workspace_api.modules.indexing.parsers.models import ParsedChunk


class BaseCodeParser(ABC):
    """Abstract base class for syntax-aware code chunking and symbol extraction."""

    def __init__(self, max_chunk_lines: int = 100) -> None:
        self.max_chunk_lines = max_chunk_lines

    @abstractmethod
    def parse_and_chunk(self, content: str, file_path: str = "") -> list[ParsedChunk]:
        """Parse source content into syntax-aware chunks with extracted symbols."""

    def sub_chunk_oversized(
        self,
        lines: list[str],
        start_line: int,
        end_line: int,
        symbol: str | None,
        symbol_type: str | None,
        parent_scope: str | None,
    ) -> list[ParsedChunk]:
        """Sub-chunk oversized code blocks while preserving symbol context and line references."""
        total_lines = end_line - start_line + 1
        if total_lines <= self.max_chunk_lines:
            return [
                ParsedChunk(
                    start_line=start_line,
                    end_line=end_line,
                    content="\n".join(lines[start_line - 1 : end_line]),
                    symbol=symbol,
                    symbol_type=symbol_type,
                    parent_scope=parent_scope,
                )
            ]

        chunks: list[ParsedChunk] = []
        for offset in range(0, total_lines, self.max_chunk_lines):
            sub_start = start_line + offset
            sub_end = min(start_line + offset + self.max_chunk_lines - 1, end_line)
            chunks.append(
                ParsedChunk(
                    start_line=sub_start,
                    end_line=sub_end,
                    content="\n".join(lines[sub_start - 1 : sub_end]),
                    symbol=symbol,
                    symbol_type=symbol_type,
                    parent_scope=parent_scope,
                )
            )
        return chunks
