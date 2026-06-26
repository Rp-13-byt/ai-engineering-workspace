import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProposedFileChange:
    path: str
    status: str = "changed"


_DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<old>.+?) b/(?P<new>.+)$")
_NEW_FILE_RE = re.compile(r"^\+\+\+ b/(?P<path>.+)$")
_DELETED_FILE_RE = re.compile(r"^--- a/(?P<path>.+)$")


def extract_changed_files(diff: str) -> list[ProposedFileChange]:
    changes: dict[str, ProposedFileChange] = {}
    current_path: str | None = None
    current_status = "changed"

    for raw_line in diff.splitlines():
        line = raw_line.strip()
        header_match = _DIFF_HEADER_RE.match(line)
        if header_match:
            current_path = header_match.group("new")
            current_status = "changed"
            changes[current_path] = ProposedFileChange(path=current_path, status=current_status)
            continue

        if line == "new file mode 100644":
            current_status = "added"
            if current_path:
                changes[current_path] = ProposedFileChange(path=current_path, status=current_status)
            continue

        if line == "deleted file mode 100644":
            current_status = "removed"
            if current_path:
                changes[current_path] = ProposedFileChange(path=current_path, status=current_status)
            continue

        new_file_match = _NEW_FILE_RE.match(line)
        if new_file_match:
            path = new_file_match.group("path")
            current_path = path
            changes[path] = ProposedFileChange(path=path, status=current_status)
            continue

        deleted_file_match = _DELETED_FILE_RE.match(line)
        if deleted_file_match and current_status == "removed":
            path = deleted_file_match.group("path")
            current_path = path
            changes[path] = ProposedFileChange(path=path, status=current_status)

    return sorted(changes.values(), key=lambda change: change.path)
