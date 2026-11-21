from dataclasses import dataclass, field

from ai_workspace_api.modules.changelens.graph_models import (
    GraphTraversalPath,
    ImpactGraph,
    ImpactNode,
    NodeType,
)
from ai_workspace_api.modules.changelens.impact_graph import ImpactGraphTraverser


@dataclass(frozen=True)
class ReachabilityAssessment:
    changed_node_ids: list[str]
    total_affected_count: int
    direct_dependents_count: int
    indirect_dependents_count: int
    max_reach_depth: int
    affected_nodes: list[ImpactNode] = field(default_factory=list)
    affected_tests: list[ImpactNode] = field(default_factory=list)
    affected_api_routes: list[ImpactNode] = field(default_factory=list)
    security_critical_paths: list[GraphTraversalPath] = field(default_factory=list)
    traversal_paths: list[GraphTraversalPath] = field(default_factory=list)
    blast_radius_score: float = 0.0  # Normalized 0 to 25


class ReachabilityAnalyzer:
    """Computes downstream blast radius, affected tests, API routes, and security-sensitive paths."""

    def __init__(self, max_depth: int = 4) -> None:
        self.traverser = ImpactGraphTraverser(max_depth=max_depth)

    def analyze_reachability(
        self,
        graph: ImpactGraph,
        changed_node_ids: list[str],
    ) -> ReachabilityAssessment:
        paths = self.traverser.find_dependents(graph, changed_node_ids)

        direct_dependents: set[str] = set()
        indirect_dependents: set[str] = set()
        affected_nodes_dict: dict[str, ImpactNode] = {}
        affected_tests_dict: dict[str, ImpactNode] = {}
        affected_routes_dict: dict[str, ImpactNode] = {}
        security_paths: list[GraphTraversalPath] = []
        max_depth_found = 0

        for path in paths:
            target = path.target_node
            affected_nodes_dict[target.id] = target
            max_depth_found = max(max_depth_found, path.depth)

            if path.depth == 1:
                direct_dependents.add(target.id)
            else:
                indirect_dependents.add(target.id)

            if target.node_type == NodeType.TEST:
                affected_tests_dict[target.id] = target
            elif target.node_type == NodeType.API_ROUTE:
                affected_routes_dict[target.id] = target

            if target.is_security_boundary or target.node_type == NodeType.SECURITY_BOUNDARY:
                security_paths.append(path)

        # Calculate blast radius contribution (capped at 25 points)
        # Direct dependents have weight 3.0, indirect 1.5, critical paths 4.0
        raw_score = (
            (len(direct_dependents) * 3.0)
            + (len(indirect_dependents) * 1.5)
            + (len(security_paths) * 4.0)
        )
        blast_radius_score = min(25.0, round(raw_score, 2))

        return ReachabilityAssessment(
            changed_node_ids=changed_node_ids,
            total_affected_count=len(affected_nodes_dict),
            direct_dependents_count=len(direct_dependents),
            indirect_dependents_count=len(indirect_dependents),
            max_reach_depth=max_depth_found,
            affected_nodes=list(affected_nodes_dict.values()),
            affected_tests=list(affected_tests_dict.values()),
            affected_api_routes=list(affected_routes_dict.values()),
            security_critical_paths=security_paths,
            traversal_paths=paths,
            blast_radius_score=blast_radius_score,
        )
