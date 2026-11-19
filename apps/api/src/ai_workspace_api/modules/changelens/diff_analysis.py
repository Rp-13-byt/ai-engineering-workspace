import re
import uuid
from pathlib import Path
from typing import Any

from ai_workspace_api.modules.changelens.models import (
    ChangedFile,
    ChangedSymbol,
    DiffAnalysisResult,
    DiffHunk,
    FileChangeType,
)
from ai_workspace_api.modules.indexing.parsers.factory import get_parser_for_path

# Matches unified diff hunk headers: @@ -old_start,old_len +new_start,new_len @@
HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

SECURITY_KEYWORDS = ("security", "permission", "auth", "crypto", "password", "token", "secret", "rbac")


def _detect_language(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".json": "json",
        ".sql": "sql",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sh": "bash",
    }
    return mapping.get(ext, "text")


def _is_security_path(path_str: str) -> bool:
    lower = path_str.lower()
    return any(keyword in lower for keyword in SECURITY_KEYWORDS)


def _is_migration_path(path_str: str) -> bool:
    lower = path_str.lower()
    return "alembic/versions" in lower or "migrations" in lower or lower.endswith(".sql")


def _is_config_path(path_str: str) -> bool:
    name = Path(path_str).name.lower()
    config_names = {
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "docker-compose.yml",
        "docker-compose.yaml",
        "dockerfile",
        "tsconfig.json",
        ".env.example",
        ".env",
    }
    if name in config_names:
        return True
    return name.endswith((".yml", ".yaml", ".toml", ".ini"))


def _is_api_path(path_str: str) -> bool:
    lower = path_str.lower()
    return "router" in lower or "routes" in lower or "endpoints" in lower or "controller" in lower


def _merge_line_ranges(lines: list[int]) -> list[tuple[int, int]]:
    """Converts a sorted list of line numbers into compact inclusive [start, end] ranges."""
    if not lines:
        return []
    sorted_unique = sorted(set(lines))
    ranges: list[tuple[int, int]] = []
    start = sorted_unique[0]
    end = start

    for line in sorted_unique[1:]:
        if line == end + 1:
            end = line
        else:
            ranges.append((start, end))
            start = line
            end = line
    ranges.append((start, end))
    return ranges


class DiffAnalyzer:
    """Parses unified diffs and maps modified line ranges to AST symbols."""

    def __init__(self, max_diff_bytes: int = 10_000_000) -> None:
        self.max_diff_bytes = max_diff_bytes

    def parse_unified_diff(self, diff_text: str) -> list[ChangedFile]:
        """Parses standard unified git diff format into structured ChangedFile instances."""
        if not diff_text or not diff_text.strip():
            return []

        # Bound diff processing to avoid resource exhaustion
        if len(diff_text.encode("utf-8")) > self.max_diff_bytes:
            diff_text = diff_text[: self.max_diff_bytes]

        files: list[ChangedFile] = []
        raw_diff_files = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)

        for block in raw_diff_files:
            block = block.strip()
            if not block or not block.startswith("diff --git"):
                continue

            parsed = self._parse_file_diff_block(block)
            if parsed is not None:
                files.append(parsed)

        return files

    def _parse_file_diff_block(self, block: str) -> ChangedFile | None:
        lines = block.splitlines()
        first_line = lines[0]
        # diff --git a/path/to/file b/path/to/file
        header_parts = first_line.split(" ")
        if len(header_parts) < 4:
            return None

        raw_a = header_parts[2]
        raw_b = header_parts[3]
        old_path = raw_a.removeprefix("a/")
        new_path = raw_b.removeprefix("b/")

        change_type = FileChangeType.MODIFIED
        is_deleted_file = False
        renamed_from: str | None = None

        hunks: list[DiffHunk] = []
        added_lines: list[int] = []
        deleted_lines: list[int] = []

        i = 1
        num_lines = len(lines)
        while i < num_lines:
            line = lines[i]

            if line.startswith("new file mode"):
                change_type = FileChangeType.ADDED
            elif line.startswith("deleted file mode"):
                is_deleted_file = True
                change_type = FileChangeType.DELETED
            elif line.startswith("rename from "):
                renamed_from = line.removeprefix("rename from ").strip()
                change_type = FileChangeType.RENAMED
            elif line.startswith("rename to "):
                new_path = line.removeprefix("rename to ").strip()
                change_type = FileChangeType.RENAMED
            elif line.startswith("--- "):
                if line.startswith("--- /dev/null"):
                    change_type = FileChangeType.ADDED
                else:
                    path_candidate = line.removeprefix("--- ").removeprefix("a/").strip()
                    if path_candidate and path_candidate != "/dev/null":
                        old_path = path_candidate
            elif line.startswith("+++ "):
                if line.startswith("+++ /dev/null"):
                    is_deleted_file = True
                    change_type = FileChangeType.DELETED
                else:
                    path_candidate = line.removeprefix("+++ ").removeprefix("b/").strip()
                    if path_candidate and path_candidate != "/dev/null":
                        new_path = path_candidate
            elif line.startswith("@@ "):
                # Parse hunk
                hunk, i = self._parse_hunk(lines, i)
                hunks.append(hunk)
                added_lines.extend(hunk.added_lines)
                deleted_lines.extend(hunk.deleted_lines)
                continue

            i += 1

        target_path = old_path if is_deleted_file else new_path
        modified_ranges = _merge_line_ranges(added_lines)

        return ChangedFile(
            path=target_path,
            change_type=change_type,
            old_path=renamed_from or (old_path if old_path != new_path else None),
            language=_detect_language(target_path),
            added_line_count=len(added_lines),
            deleted_line_count=len(deleted_lines),
            modified_line_ranges=modified_ranges,
            is_migration=_is_migration_path(target_path),
            is_config=_is_config_path(target_path),
            is_api_route=_is_api_path(target_path),
            is_security_sensitive=_is_security_path(target_path),
        )

    def _parse_hunk(self, lines: list[str], start_index: int) -> tuple[DiffHunk, int]:
        header_line = lines[start_index]
        match = HUNK_HEADER_RE.match(header_line)
        if not match:
            return DiffHunk(old_start=1, old_length=0, new_start=1, new_length=0), start_index + 1

        old_start = int(match.group(1))
        old_length = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_length = int(match.group(4)) if match.group(4) else 1

        added: list[int] = []
        deleted: list[int] = []

        current_new_line = new_start
        current_old_line = old_start

        i = start_index + 1
        while i < len(lines):
            line = lines[i]
            if line.startswith("@@ ") or line.startswith("diff --git"):
                break

            if line.startswith("+") and not line.startswith("+++"):
                added.append(current_new_line)
                current_new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                deleted.append(current_old_line)
                current_old_line += 1
            elif line.startswith(" ") or line == "":
                current_new_line += 1
                current_old_line += 1
            elif line.startswith("\\ No newline at end of file"):
                pass
            i += 1

        return DiffHunk(
            old_start=old_start,
            old_length=old_length,
            new_start=new_start,
            new_length=new_length,
            added_lines=added,
            deleted_lines=deleted,
            modified_line_ranges=_merge_line_ranges(added),
        ), i

    def map_symbols_to_changes(
        self,
        changed_files: list[ChangedFile],
        file_contents: dict[str, str] | None = None,
        indexed_chunks: list[dict[str, Any]] | None = None,
    ) -> list[ChangedSymbol]:
        """Intersects modified line ranges with AST symbols extracted from file contents or indexed chunks."""
        file_contents = file_contents or {}
        indexed_chunks = indexed_chunks or []
        changed_symbols: list[ChangedSymbol] = []
        seen_keys: set[tuple[str, str, str, str | None]] = set()

        for f in changed_files:
            # 1. If file was deleted, any symbols in indexed chunks are marked deleted
            if f.change_type == FileChangeType.DELETED:
                for chunk in indexed_chunks:
                    if chunk.get("path") == f.path and chunk.get("symbol"):
                        key = (f.path, str(chunk["symbol"]), str(chunk.get("symbol_type", "symbol")), chunk.get("parent_scope"))
                        if key not in seen_keys:
                            seen_keys.add(key)
                            changed_symbols.append(
                                ChangedSymbol(
                                    name=str(chunk["symbol"]),
                                    symbol_type=str(chunk.get("symbol_type", "symbol")),
                                    file_path=f.path,
                                    start_line=int(chunk.get("start_line", 1)),
                                    end_line=int(chunk.get("end_line", 1)),
                                    parent_scope=chunk.get("parent_scope"),
                                    change_nature="deleted",
                                )
                            )
                continue

            # 2. Extract symbols from current head content using Milestone A parsers
            symbols_in_file: list[dict[str, Any]] = []
            if f.path in file_contents:
                content = file_contents[f.path]
                parser = get_parser_for_path(f.path)
                parsed_chunks = parser.parse_and_chunk(content, f.path)
                for p_chunk in parsed_chunks:
                    if p_chunk.symbol:
                        symbols_in_file.append(
                            {
                                "name": p_chunk.symbol,
                                "symbol_type": p_chunk.symbol_type or "symbol",
                                "start_line": p_chunk.start_line,
                                "end_line": p_chunk.end_line,
                                "parent_scope": p_chunk.parent_scope,
                            }
                        )
            else:
                # Fallback to indexed chunks
                for chunk in indexed_chunks:
                    if chunk.get("path") == f.path and chunk.get("symbol"):
                        symbols_in_file.append(
                            {
                                "name": str(chunk["symbol"]),
                                "symbol_type": str(chunk.get("symbol_type", "symbol")),
                                "start_line": int(chunk.get("start_line", 1)),
                                "end_line": int(chunk.get("end_line", 1)),
                                "parent_scope": chunk.get("parent_scope"),
                            }
                        )

            # 3. Intersect modified line ranges with symbol boundaries
            change_nature = "added" if f.change_type == FileChangeType.ADDED else "modified"
            for sym in symbols_in_file:
                sym_start = int(sym["start_line"])
                sym_end = int(sym["end_line"])

                is_intersecting = False
                for mod_start, mod_end in f.modified_line_ranges:
                    if mod_start <= sym_end and mod_end >= sym_start:
                        is_intersecting = True
                        break

                if is_intersecting:
                    key = (f.path, str(sym["name"]), str(sym["symbol_type"]), sym["parent_scope"])
                    if key not in seen_keys:
                        seen_keys.add(key)
                        changed_symbols.append(
                            ChangedSymbol(
                                name=str(sym["name"]),
                                symbol_type=str(sym["symbol_type"]),
                                file_path=f.path,
                                start_line=sym_start,
                                end_line=sym_end,
                                parent_scope=sym["parent_scope"],
                                change_nature=change_nature,
                            )
                        )

        return changed_symbols

    def analyze(
        self,
        repository_id: uuid.UUID,
        base_sha: str,
        head_sha: str,
        diff_text: str,
        file_contents: dict[str, str] | None = None,
        indexed_chunks: list[dict[str, Any]] | None = None,
    ) -> DiffAnalysisResult:
        """Full pipeline: diff parsing + symbol mapping into DiffAnalysisResult."""
        files = self.parse_unified_diff(diff_text)
        changed_symbols = self.map_symbols_to_changes(
            changed_files=files,
            file_contents=file_contents,
            indexed_chunks=indexed_chunks,
        )

        total_added = sum(f.added_line_count for f in files)
        total_deleted = sum(f.deleted_line_count for f in files)

        return DiffAnalysisResult(
            repository_id=repository_id,
            base_sha=base_sha,
            head_sha=head_sha,
            files=files,
            changed_symbols=changed_symbols,
            total_added_lines=total_added,
            total_deleted_lines=total_deleted,
            is_bounded=len(diff_text.encode("utf-8")) <= self.max_diff_bytes,
        )
