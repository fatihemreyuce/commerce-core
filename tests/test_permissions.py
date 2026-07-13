from app.models.user import UserRole
from app.core.permissions import Permission, has_permission


def test_admin_has_all_permissions():
    for perm in Permission:
        assert has_permission(UserRole.admin, perm) is True


def test_staff_manages_catalog_and_orders_but_not_users():
    assert has_permission(UserRole.staff, Permission.PRODUCT_MANAGE) is True
    assert has_permission(UserRole.staff, Permission.CATEGORY_MANAGE) is True
    assert has_permission(UserRole.staff, Permission.ORDER_READ_ALL) is True
    assert has_permission(UserRole.staff, Permission.ORDER_UPDATE_STATUS) is True
    assert has_permission(UserRole.staff, Permission.USER_MANAGE) is False


def test_customer_has_no_admin_permissions():
    for perm in Permission:
        assert has_permission(UserRole.customer, perm) is False
