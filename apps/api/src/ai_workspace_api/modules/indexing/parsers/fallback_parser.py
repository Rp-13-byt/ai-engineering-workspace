from ai_workspace_api.modules.indexing.parsers.base import BaseCodeParser
from ai_workspace_api.modules.indexing.parsers.models import ParsedChunk


class FallbackParser(BaseCodeParser):
    """Fallback line-aware chunker for unsupported languages and malformed sources."""

    def parse_and_chunk(self, content: str, file_path: str = "") -> list[ParsedChunk]:
        lines = content.splitlines()
        if not lines:
            return []

        chunks: list[ParsedChunk] = []
        total_lines = len(lines)
        start = 0
        while start < total_lines:
            end = min(start + self.max_chunk_lines, total_lines)
            chunks.append(
                ParsedChunk(
                    start_line=start + 1,
                    end_line=end,
                    content="\n".join(lines[start:end]),
                    symbol=None,
                    symbol_type=None,
                    parent_scope=None,
                )
            )
            start = end

        return chunks
