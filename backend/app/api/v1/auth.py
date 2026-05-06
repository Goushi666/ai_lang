"""注册、登录、当前用户、用户列表与级别（管理员）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import auth_service_dep, get_current_user, require_admin_user, user_repo_dep
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserLevelRequest,
    UserListItem,
    UserPublic,
    UsersListResponse,
)
from app.services.auth_service import AuthService, create_access_token

router = APIRouter()


@router.post("/register", response_model=TokenResponse, summary="注册（首名用户自动为管理员）")
async def register(body: RegisterRequest, svc: AuthService = Depends(auth_service_dep)):
    user = await svc.register(body.username, body.password)
    token = create_access_token(user_id=user.id, username=user.username, level=user.level)
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse, summary="登录")
async def login(body: LoginRequest, svc: AuthService = Depends(auth_service_dep)):
    token, user = await svc.login(body.username.strip(), body.password)
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserPublic, summary="当前登录用户")
async def me(user: UserPublic = Depends(get_current_user)):
    return user


@router.get("/users", response_model=UsersListResponse, summary="已注册用户列表（管理员）")
async def list_users(
    _: UserPublic = Depends(require_admin_user),
    repo: UserRepository = Depends(user_repo_dep),
):
    rows = await repo.list_all()
    items = [UserListItem.model_validate(r) for r in rows]
    return UsersListResponse(items=items)


@router.patch("/users/{user_id}/level", summary="修改用户级别（管理员）")
async def update_user_level(
    user_id: int,
    body: UpdateUserLevelRequest,
    _: UserPublic = Depends(require_admin_user),
    repo: UserRepository = Depends(user_repo_dep),
):
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.level == "admin" and body.level != "admin":
        if await repo.count_by_level("admin") <= 1:
            raise HTTPException(status_code=400, detail="不能降级最后一个管理员")
    ok = await repo.set_level(user_id, body.level)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user_id": user_id, "level": body.level}


@router.delete("/users/{user_id}", summary="删除用户（管理员）")
async def delete_user(
    user_id: int,
    admin: UserPublic = Depends(require_admin_user),
    repo: UserRepository = Depends(user_repo_dep),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.level == "admin" and await repo.count_by_level("admin") <= 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    ok = await repo.delete(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user_id": user_id}
