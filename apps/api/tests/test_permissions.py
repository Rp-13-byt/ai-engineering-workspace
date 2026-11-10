from ai_workspace_api.core.models import Role
from ai_workspace_api.core.permissions import Permission, role_has_permission


def test_owner_has_all_permissions() -> None:
    for permission in Permission:
        assert role_has_permission(Role.owner, permission)


def test_viewer_cannot_import_repository() -> None:
    assert not role_has_permission(Role.viewer, Permission.import_repository)
    assert role_has_permission(Role.viewer, Permission.read_repository)
