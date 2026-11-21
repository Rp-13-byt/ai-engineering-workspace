from ai_workspace_api.modules.changelens.graph_models import (
    ImpactGraph,
    ImpactNode,
    NodeType,
)
from ai_workspace_api.modules.changelens.impact_graph import ImpactGraphBuilder
from ai_workspace_api.modules.changelens.reachability import ReachabilityAnalyzer
from ai_workspace_api.modules.changelens.schema_linker import SchemaMigrationLinker

FILE_CORE_SEC = """\
def verify_hash(val: str) -> bool:
    return len(val) > 0
"""

FILE_AUTH = """\
from src.core.sec import verify_hash

def auth_user():
    return verify_hash("abc")
"""

FILE_ROUTE = """\
from src.auth import auth_user

def handle_login():
    return auth_user()
"""

FILE_TEST = """\
from src.route import handle_login

def test_login_flow():
    assert handle_login() is True
"""

MIGRATION_CONTENT = """\
def upgrade():
    op.add_column("users", sa.Column("avatar_url", sa.String(500)))
"""

MODEL_CONTENT = """\
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
"""


def test_reachability_analyzer_calculates_blast_radius_and_dependents() -> None:
    files = {
        "src/core/sec.py": FILE_CORE_SEC,
        "src/auth.py": FILE_AUTH,
        "src/route.py": FILE_ROUTE,
        "tests/test_flow.py": FILE_TEST,
    }

    graph = ImpactGraphBuilder().build_from_files(files)
    analyzer = ReachabilityAnalyzer(max_depth=4)

    assessment = analyzer.analyze_reachability(graph, ["src/core/sec.py:verify_hash"])

    assert assessment.total_affected_count >= 2
    assert assessment.direct_dependents_count >= 1
    assert assessment.blast_radius_score > 0.0
    assert any("test_flow.py" in t.id for t in assessment.affected_tests)
    assert any("route.py" in r.id for r in assessment.affected_api_routes)


def test_schema_migration_linker_connects_tables_to_models() -> None:
    graph = ImpactGraph()
    mig_node = ImpactNode(
        id="alembic/versions/0004_avatar.py",
        name="0004_avatar.py",
        node_type=NodeType.MIGRATION,
        file_path="alembic/versions/0004_avatar.py",
    )
    model_node = ImpactNode(
        id="src/models/user.py",
        name="user.py",
        node_type=NodeType.MODULE,
        file_path="src/models/user.py",
    )
    graph.add_node(mig_node)
    graph.add_node(model_node)

    linker = SchemaMigrationLinker()
    links = linker.link_migrations_to_models(
        graph=graph,
        migration_files={"alembic/versions/0004_avatar.py": MIGRATION_CONTENT},
        model_files={"src/models/user.py": MODEL_CONTENT},
    )

    assert len(links) == 1
    assert links[0].table_name == "users"
    assert "src/models/user.py" in links[0].affected_models

    # Verify edge added to graph
    edges = graph.outgoing["alembic/versions/0004_avatar.py"]
    assert len(edges) == 1
    assert edges[0].target_id == "src/models/user.py"
