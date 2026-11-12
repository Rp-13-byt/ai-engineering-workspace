import ast

from ai_workspace_api.core.logging import get_logger
from ai_workspace_api.modules.indexing.parsers.base import BaseCodeParser
from ai_workspace_api.modules.indexing.parsers.fallback_parser import FallbackParser
from ai_workspace_api.modules.indexing.parsers.models import ParsedChunk

logger = get_logger(__name__)


class PythonCodeParser(BaseCodeParser):
    """Syntax-aware Python AST parser and chunker."""

    def parse_and_chunk(self, content: str, file_path: str = "") -> list[ParsedChunk]:
        lines = content.splitlines()
        if not lines:
            return []

        try:
            tree = ast.parse(content, filename=file_path or "<string>")
        except SyntaxError as exc:
            logger.warning(
                "python_parser.syntax_error_fallback",
                file_path=file_path,
                line=exc.lineno,
                msg=exc.msg,
            )
            return FallbackParser(self.max_chunk_lines).parse_and_chunk(content, file_path)

        covered_ranges: list[tuple[int, int]] = []
        raw_chunks: list[ParsedChunk] = []

        # 1. Identify module-level imports
        import_nodes = [
            node for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if import_nodes:
            imp_start = min(node.lineno for node in import_nodes)
            imp_end = max(getattr(node, "end_lineno", node.lineno) for node in import_nodes)
            covered_ranges.append((imp_start, imp_end))
            raw_chunks.extend(
                self.sub_chunk_oversized(
                    lines,
                    imp_start,
                    imp_end,
                    symbol="imports",
                    symbol_type="import",
                    parent_scope=None,
                )
            )

        # 2. Extract classes and functions
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                self._process_class(node, lines, raw_chunks, covered_ranges)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_function(node, lines, raw_chunks, covered_ranges, parent_scope=None)

        # 3. Fill in any uncovered top-level lines (e.g. constants, module code)
        sorted_ranges = sorted(covered_ranges, key=lambda r: r[0])
        current_line = 1
        total_lines = len(lines)

        for start, end in sorted_ranges:
            if start > current_line:
                gap_start = current_line
                gap_end = start - 1
                raw_chunks.extend(
                    self.sub_chunk_oversized(
                        lines,
                        gap_start,
                        gap_end,
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

        # Sort chunks by start_line
        raw_chunks.sort(key=lambda chunk: chunk.start_line)
        return raw_chunks

    def _get_start_line(self, node: ast.AST) -> int:
        decorators = getattr(node, "decorator_list", None)
        if decorators:
            return int(min(d.lineno for d in decorators))
        return int(getattr(node, "lineno", 1))

    def _get_end_line(self, node: ast.AST) -> int:
        return int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))

    def _process_class(
        self,
        class_node: ast.ClassDef,
        lines: list[str],
        chunks: list[ParsedChunk],
        covered_ranges: list[tuple[int, int]],
    ) -> None:
        cls_start = self._get_start_line(class_node)
        cls_end = self._get_end_line(class_node)
        covered_ranges.append((cls_start, cls_end))

        # Check for methods
        methods = [
            m for m in class_node.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if not methods:
            # Entire class is a single chunk (or sub-chunked if oversized)
            chunks.extend(
                self.sub_chunk_oversized(
                    lines,
                    cls_start,
                    cls_end,
                    symbol=class_node.name,
                    symbol_type="class",
                    parent_scope=None,
                )
            )
            return

        # Class header / docstring before first method
        first_method_start = min(self._get_start_line(m) for m in methods)
        if first_method_start > cls_start:
            header_end = first_method_start - 1
            chunks.extend(
                self.sub_chunk_oversized(
                    lines,
                    cls_start,
                    header_end,
                    symbol=class_node.name,
                    symbol_type="class",
                    parent_scope=None,
                )
            )

        # Process each method
        for method in methods:
            self._process_function(
                method,
                lines,
                chunks,
                covered_ranges=[],
                parent_scope=class_node.name,
            )

    def _process_function(
        self,
        fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        chunks: list[ParsedChunk],
        covered_ranges: list[tuple[int, int]],
        parent_scope: str | None,
    ) -> None:
        fn_start = self._get_start_line(fn_node)
        fn_end = self._get_end_line(fn_node)
        if covered_ranges is not None and parent_scope is None:
            covered_ranges.append((fn_start, fn_end))

        symbol_type = "method" if parent_scope else "function"
        chunks.extend(
            self.sub_chunk_oversized(
                lines,
                fn_start,
                fn_end,
                symbol=fn_node.name,
                symbol_type=symbol_type,
                parent_scope=parent_scope,
            )
        )
