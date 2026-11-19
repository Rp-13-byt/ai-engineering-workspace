import uuid

from ai_workspace_api.modules.changelens.diff_analysis import DiffAnalyzer
from ai_workspace_api.modules.changelens.models import FileChangeType

SAMPLE_UNIFIED_DIFF = """\
diff --git a/src/core/security.py b/src/core/security.py
index 1111111..2222222 100644
--- a/src/core/security.py
+++ b/src/core/security.py
@@ -5,4 +5,6 @@ ALGORITHM = "HS256"
 def verify_password(plain_password: str, hashed_password: str) -> bool:
+    if not plain_password:
+        return False
     return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
 
 def hash_password(password: str) -> str:
diff --git a/src/api/router.py b/src/api/router.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/src/api/router.py
@@ -0,0 +1,6 @@
+from fastapi import APIRouter
+
+router = APIRouter()
+
+def get_routes():
+    return []
diff --git a/legacy_code.py b/legacy_code.py
deleted file mode 100644
index 4444444..0000000
--- a/legacy_code.py
+++ /dev/null
@@ -1,4 +0,0 @@
-def old_function():
-    pass
-
-class ObsoleteClass:
diff --git a/alembic/versions/0004_test.py b/alembic/versions/0004_test.py
index 5555555..6666666 100644
--- a/alembic/versions/0004_test.py
+++ b/alembic/versions/0004_test.py
@@ -1,2 +1,3 @@
 def upgrade():
+    op.add_column("users", sa.Column("is_super", sa.Boolean()))
     pass
diff --git a/old_config.toml b/new_config.toml
similarity index 90%
rename from old_config.toml
rename to new_config.toml
index 7777777..8888888 100644
--- a/old_config.toml
+++ b/new_config.toml
@@ -1,3 +1,3 @@
 [app]
-version = "1.0.0"
+version = "1.1.0"
 name = "workspace"
"""

PYTHON_SECURITY_CONTENT = """\
import bcrypt

ALGORITHM = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
"""

TYPESCRIPT_API_CONTENT = """\
export interface UserPayload {
  id: string;
  role: string;
}

export function parseUserToken(token: string): UserPayload {
  const parts = token.split(".");
  return { id: "1", role: "admin" };
}

export class AuthServiceClient {
  private key: string;

  constructor(key: string) {
    this.key = key;
  }

  public validate(): boolean {
    return this.key.length > 0;
  }
}
"""

TYPESCRIPT_DIFF = """\
diff --git a/src/auth/client.ts b/src/auth/client.ts
index aaaaaaa..bbbbbbb 100644
--- a/src/auth/client.ts
+++ b/src/auth/client.ts
@@ -11,6 +11,8 @@ export class AuthServiceClient {
   private key: string;
+  // Added security comment
+  private cache: Map<string, boolean> = new Map();
 
   constructor(key: string) {
"""


def test_parse_unified_diff_extracts_files_and_change_types() -> None:
    analyzer = DiffAnalyzer()
    files = analyzer.parse_unified_diff(SAMPLE_UNIFIED_DIFF)

    assert len(files) == 5

    # 1. security.py (modified)
    sec_file = next(f for f in files if f.path == "src/core/security.py")
    assert sec_file.change_type == FileChangeType.MODIFIED
    assert sec_file.language == "python"
    assert sec_file.is_security_sensitive is True
    assert sec_file.added_line_count == 2
    assert sec_file.deleted_line_count == 0
    assert sec_file.modified_line_ranges == [(6, 7)]

    # 2. router.py (added)
    router_file = next(f for f in files if f.path == "src/api/router.py")
    assert router_file.change_type == FileChangeType.ADDED
    assert router_file.is_api_route is True
    assert router_file.added_line_count == 6

    # 3. legacy_code.py (deleted)
    del_file = next(f for f in files if f.path == "legacy_code.py")
    assert del_file.change_type == FileChangeType.DELETED
    assert del_file.deleted_line_count == 4

    # 4. alembic migration
    mig_file = next(f for f in files if "alembic" in f.path)
    assert mig_file.is_migration is True

    # 5. renamed config
    cfg_file = next(f for f in files if f.path == "new_config.toml")
    assert cfg_file.change_type == FileChangeType.RENAMED
    assert cfg_file.old_path == "old_config.toml"
    assert cfg_file.is_config is True


def test_map_symbols_to_changes_for_python_ast() -> None:
    analyzer = DiffAnalyzer()
    files = analyzer.parse_unified_diff(SAMPLE_UNIFIED_DIFF)
    file_contents = {"src/core/security.py": PYTHON_SECURITY_CONTENT}

    changed_symbols = analyzer.map_symbols_to_changes(
        changed_files=files,
        file_contents=file_contents,
    )

    sym_names = [s.name for s in changed_symbols]
    assert "verify_password" in sym_names

    verify_sym = next(s for s in changed_symbols if s.name == "verify_password")
    assert verify_sym.symbol_type == "function"
    assert verify_sym.file_path == "src/core/security.py"
    assert verify_sym.change_nature == "modified"

    # hash_password is NOT modified and should not be included
    assert "hash_password" not in sym_names


def test_map_symbols_to_changes_for_typescript() -> None:
    analyzer = DiffAnalyzer()
    files = analyzer.parse_unified_diff(TYPESCRIPT_DIFF)
    file_contents = {"src/auth/client.ts": TYPESCRIPT_API_CONTENT}

    changed_symbols = analyzer.map_symbols_to_changes(
        changed_files=files,
        file_contents=file_contents,
    )

    sym_names = [s.name for s in changed_symbols]
    assert "AuthServiceClient" in sym_names

    # parseUserToken was NOT touched by the hunk
    assert "parseUserToken" not in sym_names


def test_diff_analysis_pipeline_end_to_end() -> None:
    analyzer = DiffAnalyzer()
    repo_id = uuid.uuid4()
    base_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    head_sha = "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5"

    result = analyzer.analyze(
        repository_id=repo_id,
        base_sha=base_sha,
        head_sha=head_sha,
        diff_text=SAMPLE_UNIFIED_DIFF,
        file_contents={"src/core/security.py": PYTHON_SECURITY_CONTENT},
    )

    assert result.repository_id == repo_id
    assert result.base_sha == base_sha
    assert result.head_sha == head_sha
    assert len(result.files) == 5
    assert result.total_added_lines > 0
    assert result.is_bounded is True
    assert any(s.name == "verify_password" for s in result.changed_symbols)
