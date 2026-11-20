import enum
from dataclasses import dataclass, field


class NodeType(str, enum.Enum):
    FILE = "file"
    SYMBOL = "symbol"
    MODULE = "module"
    API_ROUTE = "api_route"
    TEST = "test"
    MIGRATION = "migration"
    CONFIG = "config"
    SECURITY_BOUNDARY = "security_boundary"


class EdgeType(str, enum.Enum):
    AST_IMPORT = "AST_IMPORT"
    STATIC_CALL = "STATIC_CALL"
    COVERAGE = "COVERAGE"
    SCHEMA_RELATION = "SCHEMA_RELATION"
    CONFIG_DEPENDENCY = "CONFIG_DEPENDENCY"
    CRITICAL_BOUNDARY = "CRITICAL_BOUNDARY"
    NAME_HEURISTIC = "NAME_HEURISTIC"


@dataclass(frozen=True)
class EdgeProvenance:
    edge_type: EdgeType
    confidence: float = 1.0
    source_file: str = ""
    source_line: int | None = None
    reason: str = ""


@dataclass(frozen=True)
class ImpactNode:
    id: str  # Format: "file_path" or "file_path:symbol_name"
    name: str
    node_type: NodeType
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    is_security_boundary: bool = False
    parent_scope: str | None = None


@dataclass(frozen=True)
class ImpactEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    provenance: EdgeProvenance


@dataclass(frozen=True)
class GraphTraversalPath:
    source_node: ImpactNode
    target_node: ImpactNode
    steps: list[str]  # e.g. ["src/core/security.py:verify_password", "src/modules/auth/service.py:login"]
    depth: int
    edge_types: list[EdgeType] = field(default_factory=list)


@dataclass
class ImpactGraph:
    nodes: dict[str, ImpactNode] = field(default_factory=dict)
    outgoing: dict[str, list[ImpactEdge]] = field(default_factory=dict)
    incoming: dict[str, list[ImpactEdge]] = field(default_factory=dict)

    def add_node(self, node: ImpactNode) -> None:
        self.nodes[node.id] = node
        if node.id not in self.outgoing:
            self.outgoing[node.id] = []
        if node.id not in self.incoming:
            self.incoming[node.id] = []

    def add_edge(self, edge: ImpactEdge) -> None:
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            return
        self.outgoing[edge.source_id].append(edge)
        self.incoming[edge.target_id].append(edge)
