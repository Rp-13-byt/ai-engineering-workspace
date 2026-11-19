import enum
import uuid
from dataclasses import dataclass, field


class FileChangeType(str, enum.Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class DiffHunk:
    old_start: int
    old_length: int
    new_start: int
    new_length: int
    added_lines: list[int] = field(default_factory=list)
    deleted_lines: list[int] = field(default_factory=list)
    modified_line_ranges: list[tuple[int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class ChangedFile:
    path: str
    change_type: FileChangeType
    old_path: str | None = None
    language: str = "text"
    added_line_count: int = 0
    deleted_line_count: int = 0
    modified_line_ranges: list[tuple[int, int]] = field(default_factory=list)
    is_migration: bool = False
    is_config: bool = False
    is_api_route: bool = False
    is_security_sensitive: bool = False


@dataclass(frozen=True)
class ChangedSymbol:
    name: str
    symbol_type: str  # "class", "function", "method", "interface", "type_alias", "import"
    file_path: str
    start_line: int
    end_line: int
    parent_scope: str | None = None
    change_nature: str = "modified"  # "modified", "added", "deleted"


@dataclass(frozen=True)
class DiffAnalysisResult:
    repository_id: uuid.UUID
    base_sha: str
    head_sha: str
    files: list[ChangedFile]
    changed_symbols: list[ChangedSymbol]
    total_added_lines: int
    total_deleted_lines: int
    is_bounded: bool = True
