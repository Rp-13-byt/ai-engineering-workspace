import ast
import re
from collections import deque
from pathlib import Path

from ai_workspace_api.modules.changelens.graph_models import (
    EdgeProvenance,
    EdgeType,
    GraphTraversalPath,
    ImpactEdge,
    ImpactGraph,
    ImpactNode,
    NodeType,
)
from ai_workspace_api.modules.indexing.parsers.factory import get_parser_for_path

IMPORT_TS_RE = re.compile(
    r"""import\s+(?:(?:\{([^}]+)\})|(?:([A-Za-z0-9_$]+))|(?:\*\s+as\s+([A-Za-z0-9_$]+)))\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)

SECURITY_MARKERS = ("verify_password", "decode_access_token", "require_permission", "get_current_user", "Permission.")


def _classify_node_type(path_str: str, symbol_type: str | None = None) -> NodeType:
    lower = path_str.lower()
    if "test" in lower or lower.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
        return NodeType.TEST
    if "alembic/versions" in lower or "migrations" in lower:
        return NodeType.MIGRATION
    if "router" in lower or "routes" in lower or "endpoints" in lower:
        return NodeType.API_ROUTE
    if any(s in lower for s in ("security", "permission", "auth")):
        return NodeType.SECURITY_BOUNDARY
    if symbol_type:
        return NodeType.SYMBOL
    return NodeType.FILE


class ImpactGraphBuilder:
    """Constructs a cross-module AST dependency graph from repository code."""

    def build_from_files(self, file_contents: dict[str, str]) -> ImpactGraph:
        graph = ImpactGraph()

        # Step 1: Register all files and AST symbols as nodes
        for path_str, content in file_contents.items():
            file_node_id = path_str
            is_sec = "security" in path_str.lower() or "permission" in path_str.lower() or "auth" in path_str.lower()
            file_node = ImpactNode(
                id=file_node_id,
                name=Path(path_str).name,
                node_type=_classify_node_type(path_str),
                file_path=path_str,
                start_line=1,
                end_line=len(content.splitlines()),
                is_security_boundary=is_sec,
            )
            graph.add_node(file_node)

            # Extract symbols using Milestone A AST parsers
            parser = get_parser_for_path(path_str)
            parsed_chunks = parser.parse_and_chunk(content, path_str)

            for chunk in parsed_chunks:
                if chunk.symbol:
                    sym_id = f"{path_str}:{chunk.symbol}"
                    sym_node = ImpactNode(
                        id=sym_id,
                        name=chunk.symbol,
                        node_type=NodeType.SYMBOL,
                        file_path=path_str,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        is_security_boundary=is_sec or any(sm in chunk.content for sm in SECURITY_MARKERS),
                        parent_scope=chunk.parent_scope,
                    )
                    graph.add_node(sym_node)

                    # Edge: File contains symbol
                    graph.add_edge(
                        ImpactEdge(
                            source_id=file_node_id,
                            target_id=sym_id,
                            edge_type=EdgeType.STATIC_CALL,
                            provenance=EdgeProvenance(
                                edge_type=EdgeType.STATIC_CALL,
                                confidence=1.0,
                                source_file=path_str,
                                source_line=chunk.start_line,
                                reason="Symbol definition inside file",
                            ),
                        )
                    )

        # Step 2: Extract cross-file AST imports and calls
        for path_str, content in file_contents.items():
            if path_str.endswith(".py"):
                self._extract_python_imports(path_str, content, graph, file_contents)
            elif path_str.endswith((".ts", ".tsx", ".js", ".jsx")):
                self._extract_typescript_imports(path_str, content, graph, file_contents)

        return graph

    def _extract_python_imports(
        self,
        source_path: str,
        content: str,
        graph: ImpactGraph,
        all_files: dict[str, str],
    ) -> None:
        try:
            tree = ast.parse(content)
        except Exception:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module_dots = node.module.split(".")
                # Search for target file corresponding to module
                for target_path in all_files:
                    target_normalized = target_path.replace("\\", "/").replace(".py", "")
                    if target_normalized.endswith("/".join(module_dots)) or target_normalized.endswith(module_dots[-1]):
                        # Link each imported symbol
                        for alias in node.names:
                            target_sym_id = f"{target_path}:{alias.name}"
                            if target_sym_id in graph.nodes:
                                graph.add_edge(
                                    ImpactEdge(
                                        source_id=source_path,
                                        target_id=target_sym_id,
                                        edge_type=EdgeType.AST_IMPORT,
                                        provenance=EdgeProvenance(
                                            edge_type=EdgeType.AST_IMPORT,
                                            confidence=1.0,
                                            source_file=source_path,
                                            source_line=getattr(node, "lineno", None),
                                            reason=f"Direct import from {node.module}",
                                        ),
                                    )
                                )
                            else:
                                # Edge to target file directly
                                graph.add_edge(
                                    ImpactEdge(
                                        source_id=source_path,
                                        target_id=target_path,
                                        edge_type=EdgeType.AST_IMPORT,
                                        provenance=EdgeProvenance(
                                            edge_type=EdgeType.AST_IMPORT,
                                            confidence=0.9,
                                            source_file=source_path,
                                            source_line=getattr(node, "lineno", None),
                                            reason=f"Module import {node.module}",
                                        ),
                                    )
                                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for target_path in all_files:
                        if alias.name in target_path.replace("/", "."):
                            graph.add_edge(
                                ImpactEdge(
                                    source_id=source_path,
                                    target_id=target_path,
                                    edge_type=EdgeType.AST_IMPORT,
                                    provenance=EdgeProvenance(
                                        edge_type=EdgeType.AST_IMPORT,
                                        confidence=0.8,
                                        source_file=source_path,
                                        source_line=getattr(node, "lineno", None),
                                        reason=f"Module import {alias.name}",
                                    ),
                                )
                            )

    def _extract_typescript_imports(
        self,
        source_path: str,
        content: str,
        graph: ImpactGraph,
        all_files: dict[str, str],
    ) -> None:
        source_dir = Path(source_path).parent

        for match in IMPORT_TS_RE.finditer(content):
            specifiers = match.group(1)
            raw_import_path = match.group(4)

            # Resolve relative import
            if raw_import_path.startswith("."):
                resolved_base = (source_dir / raw_import_path).as_posix().replace("//", "/")
                target_candidates = [
                    f"{resolved_base}.ts",
                    f"{resolved_base}.tsx",
                    f"{resolved_base}.js",
                    f"{resolved_base}/index.ts",
                    f"{resolved_base}/index.tsx",
                ]
            else:
                target_candidates = [f for f in all_files if raw_import_path in f]

            for target in target_candidates:
                if target in graph.nodes:
                    if specifiers:
                        for sym in [s.strip() for s in specifiers.split(",")]:
                            sym_id = f"{target}:{sym}"
                            if sym_id in graph.nodes:
                                graph.add_edge(
                                    ImpactEdge(
                                        source_id=source_path,
                                        target_id=sym_id,
                                        edge_type=EdgeType.AST_IMPORT,
                                        provenance=EdgeProvenance(
                                            edge_type=EdgeType.AST_IMPORT,
                                            confidence=1.0,
                                            source_file=source_path,
                                            reason=f"TypeScript named import {sym}",
                                        ),
                                    )
                                )
                    graph.add_edge(
                        ImpactEdge(
                            source_id=source_path,
                            target_id=target,
                            edge_type=EdgeType.AST_IMPORT,
                            provenance=EdgeProvenance(
                                edge_type=EdgeType.AST_IMPORT,
                                confidence=0.9,
                                source_file=source_path,
                                reason=f"TypeScript import from {raw_import_path}",
                            ),
                        )
                    )


class ImpactGraphTraverser:
    """Traverses the impact graph to compute blast radius, dependent components, and explainable provenance paths."""

    def __init__(self, max_depth: int = 4) -> None:
        self.max_depth = max_depth

    def find_dependents(
        self,
        graph: ImpactGraph,
        changed_node_ids: list[str],
    ) -> list[GraphTraversalPath]:
        """Finds all downstream nodes that depend on the changed nodes.
        Note: If A imports B, then A depends on B (B is a dependency of A).
        Therefore, to find downstream dependents of B, we traverse the incoming edges to B.
        """
        paths: list[GraphTraversalPath] = []
        visited: set[str] = set()

        for start_id in changed_node_ids:
            if start_id not in graph.nodes:
                continue

            start_node = graph.nodes[start_id]
            visited.add(start_id)

            # Queue holds: (current_node_id, current_depth, path_steps, edge_types)
            queue: deque[tuple[str, int, list[str], list[EdgeType]]] = deque([(start_id, 0, [start_id], [])])

            while queue:
                curr_id, depth, path_steps, edge_types = queue.popleft()

                if depth >= self.max_depth:
                    continue

                # Dependents of curr_id are nodes that have an edge pointing TO curr_id (incoming edges)
                for edge in graph.incoming.get(curr_id, []):
                    dependent_id = edge.source_id
                    if dependent_id not in graph.nodes:
                        continue

                    # Prevent cycles
                    if dependent_id in path_steps:
                        continue

                    dependent_node = graph.nodes[dependent_id]
                    new_steps = path_steps + [dependent_id]
                    new_edge_types = edge_types + [edge.edge_type]

                    paths.append(
                        GraphTraversalPath(
                            source_node=start_node,
                            target_node=dependent_node,
                            steps=new_steps,
                            depth=depth + 1,
                            edge_types=new_edge_types,
                        )
                    )

                    queue.append((dependent_id, depth + 1, new_steps, new_edge_types))

        return paths
