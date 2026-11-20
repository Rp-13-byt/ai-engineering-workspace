from ai_workspace_api.modules.changelens.graph_models import (
    EdgeProvenance,
    EdgeType,
    ImpactEdge,
    ImpactGraph,
    ImpactNode,
    NodeType,
)
from ai_workspace_api.modules.changelens.impact_graph import ImpactGraphBuilder, ImpactGraphTraverser

FILE_A_SECURITY = """\
def verify_token(token: str) -> bool:
    return len(token) > 10

def hash_token(token: str) -> str:
    return token + "_hashed"
"""

FILE_B_AUTH_SERVICE = """\
from src.core.security import verify_token

class AuthService:
    def authenticate(self, token: str) -> bool:
        return verify_token(token)
"""

FILE_C_API_ROUTER = """\
from src.modules.auth.service import AuthService

router = {}

def login_endpoint(token: str):
    service = AuthService()
    return service.authenticate(token)
"""

FILE_D_TEST = """\
from src.api.router import login_endpoint

def test_login():
    assert login_endpoint("valid_token_123") is True
"""


def test_build_impact_graph_from_python_files() -> None:
    files = {
        "src/core/security.py": FILE_A_SECURITY,
        "src/modules/auth/service.py": FILE_B_AUTH_SERVICE,
        "src/api/router.py": FILE_C_API_ROUTER,
        "tests/test_auth.py": FILE_D_TEST,
    }

    builder = ImpactGraphBuilder()
    graph = builder.build_from_files(files)

    # Verify nodes registered
    assert "src/core/security.py" in graph.nodes
    assert "src/core/security.py:verify_token" in graph.nodes
    assert "src/modules/auth/service.py" in graph.nodes
    assert "src/modules/auth/service.py:AuthService" in graph.nodes
    assert "src/api/router.py:login_endpoint" in graph.nodes
    assert "tests/test_auth.py" in graph.nodes

    # Check node types
    sec_node = graph.nodes["src/core/security.py:verify_token"]
    assert sec_node.is_security_boundary is True

    test_node = graph.nodes["tests/test_auth.py"]
    assert test_node.node_type == NodeType.TEST

    router_node = graph.nodes["src/api/router.py"]
    assert router_node.node_type == NodeType.API_ROUTE


def test_impact_graph_traversal_discovers_dependents() -> None:
    files = {
        "src/core/security.py": FILE_A_SECURITY,
        "src/modules/auth/service.py": FILE_B_AUTH_SERVICE,
        "src/api/router.py": FILE_C_API_ROUTER,
        "tests/test_auth.py": FILE_D_TEST,
    }

    builder = ImpactGraphBuilder()
    graph = builder.build_from_files(files)

    traverser = ImpactGraphTraverser(max_depth=4)
    # If verify_token changes in security.py
    changed_ids = ["src/core/security.py:verify_token"]
    paths = traverser.find_dependents(graph, changed_ids)

    reached_targets = [p.target_node.id for p in paths]

    # AuthService imports verify_token -> should be reached
    assert any("service.py" in target for target in reached_targets)

    # Verify explainable path
    auth_path = next(p for p in paths if "service.py" in p.target_node.id)
    assert auth_path.depth >= 1
    assert auth_path.steps[0] == "src/core/security.py:verify_token"
    assert "src/modules/auth/service.py" in auth_path.steps[1]


def test_impact_graph_cycle_prevention() -> None:
    graph = ImpactGraph()

    node_a = ImpactNode(id="A", name="A", node_type=NodeType.MODULE, file_path="A.py")
    node_b = ImpactNode(id="B", name="B", node_type=NodeType.MODULE, file_path="B.py")

    graph.add_node(node_a)
    graph.add_node(node_b)

    # Circular dependency: A imports B, B imports A
    # In graph: edge source=A, target=B (A depends on B). And source=B, target=A.
    prov = EdgeProvenance(edge_type=EdgeType.AST_IMPORT)
    graph.add_edge(ImpactEdge(source_id="A", target_id="B", edge_type=EdgeType.AST_IMPORT, provenance=prov))
    graph.add_edge(ImpactEdge(source_id="B", target_id="A", edge_type=EdgeType.AST_IMPORT, provenance=prov))

    traverser = ImpactGraphTraverser(max_depth=5)
    paths = traverser.find_dependents(graph, ["A"])

    # Must terminate without infinite loop and not have duplicate cyclic steps
    assert len(paths) <= 2
    for p in paths:
        assert len(p.steps) == len(set(p.steps))  # No duplicate nodes in path
