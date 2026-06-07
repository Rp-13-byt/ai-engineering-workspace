from ai_workspace_api.modules.indexing.file_filter import FileFilter


def test_skips_binary_files() -> None:
    f = FileFilter()
    assert f.should_index("image.png", 100) is False
    assert f.should_index("lib.dll", 100) is False
    assert f.should_index("font.woff2", 100) is False
    assert f.should_index("archive.zip", 100) is False


def test_allows_source_files() -> None:
    f = FileFilter()
    assert f.should_index("main.py", 100) is True
    assert f.should_index("app.ts", 100) is True
    assert f.should_index("README.md", 100) is True
    assert f.should_index("Dockerfile", 100) is True


def test_skips_node_modules() -> None:
    f = FileFilter()
    assert f.should_index("node_modules/express/index.js", 100) is False


def test_skips_pycache() -> None:
    f = FileFilter()
    assert f.should_index("src/__pycache__/main.cpython-311.pyc", 100) is False


def test_skips_lock_files() -> None:
    f = FileFilter()
    assert f.should_index("package-lock.json", 5000) is False
    assert f.should_index("yarn.lock", 5000) is False
    assert f.should_index("poetry.lock", 5000) is False


def test_skips_large_files() -> None:
    f = FileFilter(max_file_size=100_000)
    assert f.should_index("big_file.py", 500_000) is False
    assert f.should_index("small_file.py", 50_000) is True


def test_gitignore_patterns() -> None:
    gitignore = """\n*.log\nlogs/\n.env\n"""
    f = FileFilter(gitignore_content=gitignore)
    assert f.should_index("app.log", 100) is False
    assert f.should_index("logs/debug.txt", 100) is False
    assert f.should_index(".env", 100) is False
    assert f.should_index("src/main.py", 100) is True


def test_skips_egg_info() -> None:
    f = FileFilter()
    assert f.should_index("src/mypackage.egg-info/PKG-INFO", 100) is False


def test_skips_build_dirs() -> None:
    f = FileFilter()
    assert f.should_index("dist/bundle.js", 100) is False
    assert f.should_index("build/output.css", 100) is False
    assert f.should_index(".next/cache/data.json", 100) is False


def test_skips_venv() -> None:
    f = FileFilter()
    assert f.should_index(".venv/lib/python3.11/site-packages/pip/__init__.py", 100) is False
    assert f.should_index("venv/bin/activate", 100) is False


def test_skips_ide_dirs() -> None:
    f = FileFilter()
    assert f.should_index(".idea/workspace.xml", 100) is False
    assert f.should_index(".vscode/settings.json", 100) is False
