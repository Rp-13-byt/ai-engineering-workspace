import re
from dataclasses import dataclass

from ai_workspace_api.modules.changelens.graph_models import (
    EdgeProvenance,
    EdgeType,
    ImpactEdge,
    ImpactGraph,
)

TABLE_ALTER_RE = re.compile(
    r"""op\.(?:create_table|add_column|drop_column|alter_column|create_index|drop_table)\s*\(\s*['"]([A-Za-z0-9_]+)['"]"""
)
MODEL_TABLE_RE = re.compile(r"""__tablename__\s*=\s*['"]([A-Za-z0-9_]+)['"]""")


@dataclass(frozen=True)
class SchemaLink:
    migration_file: str
    table_name: str
    affected_models: list[str]


class SchemaMigrationLinker:
    """Detects database schema modifications in Alembic migrations and connects them to SQLAlchemy models."""

    def link_migrations_to_models(
        self,
        graph: ImpactGraph,
        migration_files: dict[str, str],
        model_files: dict[str, str],
    ) -> list[SchemaLink]:
        links: list[SchemaLink] = []

        # Map table_name -> list of (model_file, model_name)
        table_to_models: dict[str, list[tuple[str, str]]] = {}
        for model_path, content in model_files.items():
            for match in MODEL_TABLE_RE.finditer(content):
                table_name = match.group(1)
                if table_name not in table_to_models:
                    table_to_models[table_name] = []
                # Also find enclosing class name if possible
                table_to_models[table_name].append((model_path, table_name))

        for mig_path, content in migration_files.items():
            modified_tables: set[str] = set()
            for match in TABLE_ALTER_RE.finditer(content):
                modified_tables.add(match.group(1))

            for table in modified_tables:
                affected_model_ids: list[str] = []
                if table in table_to_models:
                    for m_path, _ in table_to_models[table]:
                        m_id = m_path
                        affected_model_ids.append(m_id)

                        # Add SCHEMA_RELATION edge
                        if mig_path in graph.nodes and m_id in graph.nodes:
                            graph.add_edge(
                                ImpactEdge(
                                    source_id=mig_path,
                                    target_id=m_id,
                                    edge_type=EdgeType.SCHEMA_RELATION,
                                    provenance=EdgeProvenance(
                                        edge_type=EdgeType.SCHEMA_RELATION,
                                        confidence=1.0,
                                        source_file=mig_path,
                                        reason=f"Migration modifies table '{table}' used by {m_path}",
                                    ),
                                )
                            )

                links.append(
                    SchemaLink(
                        migration_file=mig_path,
                        table_name=table,
                        affected_models=affected_model_ids,
                    )
                )

        return links
