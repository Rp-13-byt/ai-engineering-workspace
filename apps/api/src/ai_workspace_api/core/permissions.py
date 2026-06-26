from enum import StrEnum

from ai_workspace_api.core.models import Role


class Permission(StrEnum):
    read_repository = "repository:read"
    import_repository = "repository:import"
    index_repository = "repository:index"
    use_ai = "ai:use"
    generate_pull_request = "pull_request:generate"
    approve_pull_request = "pull_request:approve"
    manage_tasks = "tasks:manage"
    manage_members = "members:manage"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.owner: set(Permission),
    Role.admin: {
        Permission.read_repository,
        Permission.import_repository,
        Permission.index_repository,
        Permission.use_ai,
        Permission.generate_pull_request,
        Permission.approve_pull_request,
        Permission.manage_tasks,
        Permission.manage_members,
    },
    Role.engineer: {
        Permission.read_repository,
        Permission.index_repository,
        Permission.use_ai,
        Permission.generate_pull_request,
        Permission.manage_tasks,
    },
    Role.viewer: {Permission.read_repository, Permission.use_ai},
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
