import re

from ai_workspace_api.core.logging import get_logger
from ai_workspace_api.modules.indexing.parsers.base import BaseCodeParser
from ai_workspace_api.modules.indexing.parsers.fallback_parser import FallbackParser
from ai_workspace_api.modules.indexing.parsers.models import ParsedChunk

logger = get_logger(__name__)

# Regex patterns for TypeScript / JavaScript declarations
CLASS_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+([A-Za-z0-9_$]+)",
    re.MULTILINE,
)
INTERFACE_RE = re.compile(
    r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)",
    re.MULTILINE,
)
TYPE_RE = re.compile(
    r"^(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=",
    re.MULTILINE,
)
FUNCTION_RE = re.compile(
    r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*([A-Za-z0-9_$]+)\s*\(",
    re.MULTILINE,
)
ARROW_FN_RE = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>",
    re.MULTILINE,
)
METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected|static|async|readonly|override)\s+)*([A-Za-z0-9_$]+)\s*\([^)]*\)\s*(?::\s*[^;{]+)?\s*\{",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^(?:import|export\s+(?:\*|\{[^}]+\})\s+from)",
    re.MULTILINE,
)


class TypeScriptCodeParser(BaseCodeParser):
    """Syntax-aware TypeScript and JavaScript parser and chunker."""

    def parse_and_chunk(self, content: str, file_path: str = "") -> list[ParsedChunk]:
        lines = content.splitlines()
        if not lines:
            return []

        try:
            return self._parse_source(lines, file_path)
        except Exception as exc:
            logger.warning(
                "typescript_parser.fallback",
                file_path=file_path,
                error=str(exc),
            )
            return FallbackParser(self.max_chunk_lines).parse_and_chunk(content, file_path)

    def _find_matching_brace(self, lines: list[str], start_idx: int) -> int:
        """Find ending line index for a brace-delimited block starting at or after start_idx."""
        depth = 0
        found_open = False
        in_multiline_comment = False

        for idx in range(start_idx, len(lines)):
            line = lines[idx]
            stripped = line.strip()

            if in_multiline_comment:
                if "*/" in stripped:
                    in_multiline_comment = False
                continue
            if stripped.startswith("/*"):
                if "*/" not in stripped:
                    in_multiline_comment = True
                continue
            if stripped.startswith("//"):
                continue

            # Strip string literals to avoid counting braces inside strings
            sanitized = re.sub(r"'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"|`(?:\\.|[^`])*`", "''", line)

            for char in sanitized:
                if char == "{":
                    depth += 1
                    found_open = True
                elif char == "}":
                    depth -= 1
                    if found_open and depth == 0:
                        return idx

        return len(lines) - 1

    def _parse_source(self, lines: list[str], file_path: str) -> list[ParsedChunk]:
        covered_ranges: list[tuple[int, int]] = []
        raw_chunks: list[ParsedChunk] = []
        total_lines = len(lines)

        # 1. Capture imports at top of file
        import_start = None
        import_end = None
        for idx, line in enumerate(lines):
            if IMPORT_RE.search(line):
                if import_start is None:
                    import_start = idx + 1
                import_end = idx + 1
            elif import_start is not None and line.strip() and not line.strip().startswith("//"):
                # Hit non-import statement
                break

        if import_start is not None and import_end is not None:
            covered_ranges.append((import_start, import_end))
            raw_chunks.extend(
                self.sub_chunk_oversized(
                    lines,
                    import_start,
                    import_end,
                    symbol="imports",
                    symbol_type="import",
                    parent_scope=None,
                )
            )

        # 2. Iterate through lines to discover symbols
        idx = 0
        while idx < total_lines:
            line = lines[idx]
            line_num = idx + 1

            # Skip lines already in import range
            if import_start and import_end and import_start <= line_num <= import_end:
                idx += 1
                continue

            # Class declaration
            cls_match = CLASS_RE.search(line)
            if cls_match:
                cls_name = cls_match.group(1)
                cls_end_idx = self._find_matching_brace(lines, idx)
                cls_start = line_num
                cls_end = cls_end_idx + 1
                covered_ranges.append((cls_start, cls_end))

                # Extract methods inside class
                methods_found = False
                inner_idx = idx + 1
                while inner_idx < cls_end_idx:
                    inner_line = lines[inner_idx]
                    m_match = METHOD_RE.search(inner_line)
                    keywords = ("if", "for", "while", "switch", "catch")
                    if m_match and not any(kw in inner_line for kw in keywords):
                        m_name = m_match.group(1)
                        if m_name not in ("constructor", "if", "for", "while", "switch", "catch"):
                            m_end_idx = self._find_matching_brace(lines, inner_idx)
                            m_start = inner_idx + 1
                            m_end = min(m_end_idx + 1, cls_end)
                            raw_chunks.extend(
                                self.sub_chunk_oversized(
                                    lines,
                                    m_start,
                                    m_end,
                                    symbol=m_name,
                                    symbol_type="method",
                                    parent_scope=cls_name,
                                )
                            )
                            methods_found = True
                            inner_idx = max(inner_idx + 1, m_end)
                            continue
                    inner_idx += 1

                if not methods_found:
                    raw_chunks.extend(
                        self.sub_chunk_oversized(
                            lines,
                            cls_start,
                            cls_end,
                            symbol=cls_name,
                            symbol_type="class",
                            parent_scope=None,
                        )
                    )
                idx = cls_end
                continue

            # Interface declaration
            iface_match = INTERFACE_RE.search(line)
            if iface_match:
                iface_name = iface_match.group(1)
                iface_end_idx = self._find_matching_brace(lines, idx)
                iface_start = line_num
                iface_end = iface_end_idx + 1
                covered_ranges.append((iface_start, iface_end))
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        iface_start,
                        iface_end,
                        symbol=iface_name,
                        symbol_type="interface",
                        parent_scope=None,
                    )
                )
                idx = iface_end
                continue

            # Type alias
            type_match = TYPE_RE.search(line)
            if type_match:
                type_name = type_match.group(1)
                # Find semicolon or next non-empty line
                type_end_idx = idx
                for search_idx in range(idx, min(idx + 10, total_lines)):
                    if ";" in lines[search_idx]:
                        type_end_idx = search_idx
                        break
                type_start = line_num
                type_end = type_end_idx + 1
                covered_ranges.append((type_start, type_end))
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        type_start,
                        type_end,
                        symbol=type_name,
                        symbol_type="type_alias",
                        parent_scope=None,
                    )
                )
                idx = type_end
                continue

            # Function declaration
            fn_match = FUNCTION_RE.search(line)
            if fn_match:
                fn_name = fn_match.group(1)
                fn_end_idx = self._find_matching_brace(lines, idx)
                fn_start = line_num
                fn_end = fn_end_idx + 1
                covered_ranges.append((fn_start, fn_end))
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        fn_start,
                        fn_end,
                        symbol=fn_name,
                        symbol_type="function",
                        parent_scope=None,
                    )
                )
                idx = fn_end
                continue

            # Arrow function
            arrow_match = ARROW_FN_RE.search(line)
            if arrow_match and "{" in line:
                arrow_name = arrow_match.group(1)
                arrow_end_idx = self._find_matching_brace(lines, idx)
                arrow_start = line_num
                arrow_end = arrow_end_idx + 1
                covered_ranges.append((arrow_start, arrow_end))
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        arrow_start,
                        arrow_end,
                        symbol=arrow_name,
                        symbol_type="function",
                        parent_scope=None,
                    )
                )
                idx = arrow_end
                continue

            idx += 1

        # 3. Fill any uncovered line gaps
        sorted_ranges = sorted(covered_ranges, key=lambda r: r[0])
        current_line = 1
        for start, end in sorted_ranges:
            if start > current_line:
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        current_line,
                        start - 1,
                        symbol=None,
                        symbol_type=None,
                        parent_scope=None,
                    )
                )
            current_line = max(current_line, end + 1)

        if current_line <= total_lines:
            raw_chunks.extend(
                self.sub_chunk_oversized(
                    lines,
                    current_line,
                    total_lines,
                    symbol=None,
                    symbol_type=None,
                    parent_scope=None,
                )
            )

        raw_chunks.sort(key=lambda chunk: chunk.start_line)
        return [chunk for chunk in raw_chunks if chunk.content.strip()]
