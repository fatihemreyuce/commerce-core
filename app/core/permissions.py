import enum
from app.models.user import UserRole


class Permission(str, enum.Enum):
    """Sistemdeki tüm yetkiler (kaynak:aksiyon)."""
    PRODUCT_MANAGE = "product:manage"
    CATEGORY_MANAGE = "category:manage"
    ORDER_READ_ALL = "order:read_all"
    ORDER_UPDATE_STATUS = "order:update_status"
    USER_MANAGE = "user:manage"


# Her rolün sahip olduğu yetkiler. Admin her şeyi yapar; staff kullanıcı yönetemez.
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.admin: set(Permission),
    UserRole.staff: {
        Permission.PRODUCT_MANAGE,
        Permission.CATEGORY_MANAGE,
        Permission.ORDER_READ_ALL,
        Permission.ORDER_UPDATE_STATUS,
    },
    UserRole.customer: set(),
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Verilen rolün belirtilen yetkiye sahip olup olmadığını döner."""
    return permission in ROLE_PERMISSIONS.get(role, set())
