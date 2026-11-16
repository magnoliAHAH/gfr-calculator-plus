"""Аутентификация (ТЗ 6.1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text

from app.db import tx
from app.deps import CurrentUser, get_current_user, user_tx
from app.errors import ApiError
from app.schemas import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from app.security import (create_access_token, hash_password, password_acceptable,
                          verify_password)

router = APIRouter(prefix="/auth", tags=["auth"])

# Хеш для выравнивания времени ответа, когда пользователя нет (защита от перебора email)
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _authenticate(email: str, password: str) -> LoginResponse:
    with tx(None) as conn:
        row = conn.execute(text("SELECT * FROM auth_lookup_user(:e)"), {"e": email.strip()}).mappings().first()
    ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    if row is None or not ok or not row["is_active"] or not row["org_active"]:
        raise ApiError(401, "Invalid credentials", "Incorrect email or password",
                       headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(row["id"], row["organization_id"], row["role"])
    # auth_lookup_user не отдаёт must_change_password: читаем уже под tenant-контекстом пользователя
    with tx(row["organization_id"], privileged=row["role"] == "super_admin") as conn:
        must_change = conn.execute(text("SELECT must_change_password FROM users WHERE id = :i"),
                                   {"i": row["id"]}).scalar_one()
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut(id=row["id"], email=row["email"], full_name=row["full_name"], role=row["role"],
                     organization_id=row["organization_id"], organization_name=row["organization_name"],
                     must_change_password=must_change),
    )


@router.post("/login", response_model=LoginResponse, summary="Вход по email и паролю")
def login(body: LoginRequest) -> LoginResponse:
    return _authenticate(body.email, body.password)


@router.post("/token", response_model=LoginResponse, include_in_schema=False)
def token(form: OAuth2PasswordRequestForm = Depends()) -> LoginResponse:
    """OAuth2 password flow для кнопки Authorize в Swagger UI (username = email)."""
    return _authenticate(form.username, form.password)


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: CurrentUser = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role,
                   organization_id=user.organization_id, organization_name=user.organization_name,
                   must_change_password=user.must_change_password)


@router.post("/change-password", status_code=204, summary="Сменить пароль (в т.ч. временный)",
             responses={400: {"description": "Неверный текущий пароль или слабый новый"}})
def change_password(body: ChangePasswordRequest, user: CurrentUser = Depends(get_current_user)) -> Response:
    if not password_acceptable(body.new_password):
        raise ApiError(400, "Validation error", "New password must be at most 72 bytes")
    if body.new_password == body.current_password:
        raise ApiError(400, "Validation error", "New password must differ from the current one")
    with user_tx(user) as conn:
        current_hash = conn.execute(text("SELECT password_hash FROM users WHERE id = :i"),
                                    {"i": user.id}).scalar_one()
        if not verify_password(body.current_password, current_hash):
            raise ApiError(400, "Invalid password", "Current password is incorrect")
        conn.execute(text("UPDATE users SET password_hash = :h, must_change_password = FALSE WHERE id = :i"),
                     {"h": hash_password(body.new_password), "i": user.id})
    return Response(status_code=204)


@router.post("/logout", status_code=204, summary="Выход (клиент удаляет токен)")
def logout(_: CurrentUser = Depends(get_current_user)) -> Response:
    # Токены без состояния и без refresh (ТЗ 6.1): сервер ничего не отзывает.
    return Response(status_code=204)
