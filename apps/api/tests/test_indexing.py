from ai_workspace_api.core.config import Settings
from ai_workspace_api.modules.indexing.service import IndexingService


def test_chunk_content_preserves_line_ranges() -> None:
    service = IndexingService(session=None, settings=Settings())  # type: ignore[arg-type]
    chunks = service._chunk_content("\n".join(f"line {number}" for number in range(250)), max_lines=100)
    assert len(chunks) == 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 100
    assert chunks[-1].start_line == 201
    assert chunks[-1].end_line == 250


def test_language_detection() -> None:
    service = IndexingService(session=None, settings=Settings())  # type: ignore[arg-type]
    assert service._language("app/main.py") == "python"
    assert service._language("app/page.tsx") == "typescript"
    assert service._language("README.md") == "markdown"
