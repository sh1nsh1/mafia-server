from typing import Annotated

from dishka import FromDishka
from fastapi import Cookie, Depends, Response, UploadFile, HTTPException, status
from sqlalchemy.exc import DatabaseError
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from dishka.integrations.fastapi import inject

from application.queries import UserAuthQuery
from application.commands import UserCreateCommand
from application.services import UserService, SecurityService
from infrastructure.logger import get_logger
from presentation.api.v1.dtos.requests import UserCreate, CurrentUser
from presentation.api.v1.dtos.responses import (
    RoomResponse,
    UserResponse,
)


logger = get_logger(__name__, 10)
user_router = APIRouter(prefix="/user", tags=["user"])


def set_refresh_token_to_cookie(response: Response, refresh_token: str):
    age_30days = 60 * 60 * 24 * 30

    response.set_cookie(
        key="refreshToken",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=age_30days,
        path="/user/refresh",
    )

    response.set_cookie(
        key="hasToken",
        value="true",
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=age_30days,
        path="/",
    )


def delete_refresh_token_from_cookie(response: Response):
    response.delete_cookie(
        key="refreshToken",
        httponly=True,
        secure=False,
        samesite="strict",
        path="/user/refresh",
    )

    response.delete_cookie(
        key="hasToken",
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
    )


@user_router.post("/login")
@inject
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    security_service: FromDishka[SecurityService],
    response: Response,
):
    logger.debug("/login")
    query = UserAuthQuery(form_data.username, form_data.password)
    try:
        token_pair = await security_service.login(query)
        set_refresh_token_to_cookie(response, token_pair.refresh_token)

        return {"accessToken": token_pair.access_token}
    except Exception as e:
        raise HTTPException(400, e.args)


@user_router.post("/register")
@inject
async def register(
    request: UserCreate,
    security_service: FromDishka[SecurityService],
    response: Response,
):
    user_command = UserCreateCommand(request.username, request.email, request.password)
    try:
        result = await security_service.register_user(user_command)
        set_refresh_token_to_cookie(response, result.refresh_token)

        return {"accessToken": result.access_token}
    except DatabaseError:
        raise HTTPException(405, "Username already exists")


@user_router.post("/refresh")
@inject
async def refresh(
    security_service: FromDishka[SecurityService],
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias="refreshToken"),
):
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")

    try:
        result = await security_service.refresh_token(refresh_token)
        set_refresh_token_to_cookie(response, result.refresh_token)

        return {"accessToken": result.access_token}
    except ValueError as e:
        raise HTTPException(491, e.args)


@user_router.post("/logout")
async def logout(
    response: Response,
):
    delete_refresh_token_from_cookie(response)

    return {"detail": "Logged out"}


@user_router.get("/room")
@inject
async def get_current_room(
    current_user: FromDishka[CurrentUser],
    user_service: FromDishka[UserService],
) -> RoomResponse | None:
    return await user_service.get_user_joined_room(current_user.id)


@user_router.get("/me")
@inject
async def get_me(
    user: FromDishka[CurrentUser],
) -> UserResponse:
    user_response = UserResponse(id=user.id, name=user.username, email=user.email)
    print(user_response)
    return user_response


@user_router.get("/avatar")
@inject
async def get_avatar(
    current_user: FromDishka[CurrentUser],
    user_service: FromDishka[UserService],
):
    file = await user_service.get_user_avatar(current_user.id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found"
        )
    return Response(content=file, media_type="image/jpeg")


@user_router.post("/avatar")
@inject
async def set_avatar(
    file: UploadFile,
    current_user: FromDishka[CurrentUser],
    user_service: FromDishka[UserService],
):
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
        )

    try:
        success = await user_service.set_user_avatar(current_user.id, file)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload avatar",
            )

        avatar_bytes = await user_service.get_user_avatar(current_user.id)

        return Response(
            content=avatar_bytes,
            media_type="image/jpeg",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
