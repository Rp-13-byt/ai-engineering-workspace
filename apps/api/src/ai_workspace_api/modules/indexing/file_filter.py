"""File filtering for repository indexing — .gitignore, binary detection, built-in exclusions."""
import pathlib

try:
    from pathspec import PathSpec
    from pathspec.patterns import GitWildMatchPattern

    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False
    PathSpec = None  # type: ignore[assignment,misc]
    GitWildMatchPattern = None  # type: ignore[assignment,misc]


BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".lib",
    ".pyc", ".pyo", ".class", ".jar", ".war",
    ".wasm", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".sqlite", ".db", ".sqlite3",
    ".DS_Store", ".map",
})

BUILTIN_IGNORE_DIRS: frozenset[str] = frozenset({
    "node_modules", "__pycache__", ".git", ".svn", ".hg",
    "vendor", "dist", "build", "out", "target",
    ".venv", "venv", "env", ".env",
    ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".next", ".nuxt", ".output",
    "coverage", ".coverage", "htmlcov",
    ".idea", ".vscode", ".vs",
    "egg-info",
})

BUILTIN_IGNORE_FILES: frozenset[str] = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "composer.lock",
    "Gemfile.lock", "Cargo.lock", "go.sum",
    ".gitattributes", ".editorconfig",
})


class FileFilter:
    """Decides whether a file should be indexed based on multiple filter layers."""

    def __init__(
        self,
        gitignore_content: str | None = None,
        max_file_size: int = 300_000,
    ) -> None:
        self.max_file_size = max_file_size
        self._gitignore_spec: PathSpec | None = None

        if gitignore_content and HAS_PATHSPEC:
            self._gitignore_spec = PathSpec.from_lines(
                GitWildMatchPattern,
                gitignore_content.splitlines(),
            )

    def should_index(self, path: str, size: int = 0) -> bool:
        """Return True if the file at the given path should be indexed."""
        if size > self.max_file_size:
            return False

        if self._is_binary(path):
            return False

        if self._matches_builtin_ignore(path):
            return False

        if self._gitignore_spec and self._gitignore_spec.match_file(path):
            return False

        return True

    def _is_binary(self, path: str) -> bool:
        suffix = pathlib.PurePosixPath(path).suffix.lower()
        return suffix in BINARY_EXTENSIONS

    def _matches_builtin_ignore(self, path: str) -> bool:
        parts = pathlib.PurePosixPath(path).parts
        filename = parts[-1] if parts else ""

        if filename in BUILTIN_IGNORE_FILES:
            return True

        for part in parts:
            if part in BUILTIN_IGNORE_DIRS:
                return True
            if part.endswith(".egg-info"):
                return True

        return False
