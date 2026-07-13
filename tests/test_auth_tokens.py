from app.core.security import create_access_token, create_refresh_token
from jose import jwt
from app.core.config import settings
from app.core.security import ALGORITHM


def test_access_token_has_type_claim(normal_user):
    token = create_access_token(subject=str(normal_user.id))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["type"] == "access"


def test_refresh_token_has_type_claim(normal_user):
    token = create_refresh_token(subject=str(normal_user.id))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["type"] == "refresh"


def test_refresh_token_rejected_on_protected_endpoint(client, normal_user):
    refresh = create_refresh_token(subject=str(normal_user.id))
    resp = client.get("/orders/", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401
