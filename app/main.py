import logging
from contextlib import asynccontextmanager

from dishka import make_async_container
from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dishka.integrations.fastapi import FastapiProvider, setup_dishka

from domain.providers import DomainProvider
from domain.exceptions import (
    AppException,
    RepoException,
    TokenException,
    DomainException,
)
from application.providers import ApplicationProvider
from infrastructure.logger import get_logger
from presentation.providers import AuthProvider
from infrastructure.providers import InfrastructureProvider
from presentation.api.v1.routers.user_router import user_router
from presentation.api.v1.routers.lobby_router import lobby_router
from infrastructure.factories.db_session_factory import DBSessionFactory
from presentation.api.v1.routers.room_websocket_router import (
    room_websocket_router,
)


logger = get_logger(__name__, logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.debug("Mafia server started")
    db_session_factory = await container.get(DBSessionFactory)
    await db_session_factory.create_tables()
    yield
    logger.debug("Mafia server shut down")


app = FastAPI(lifespan=lifespan)

container = make_async_container(
    FastapiProvider(),
    InfrastructureProvider(),
    DomainProvider(),
    ApplicationProvider(),
    AuthProvider(),
)
setup_dishka(container, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TokenException)
def token_exception_handler(request: Request, exc: TokenException):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "expectedTokenType": exc.expected_token,
            "detail": exc.message,
        },
    )


@app.exception_handler(RepoException)
def repo_exception_handler(request: Request, exc: RepoException):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": exc.message,
            "context_id": exc.context_id,
            "user_id": exc.user_id,
            "topic": exc.topic,
        },
    )


@app.exception_handler(DomainException)
def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        content={"detail": exc.message, "topic": exc.topic},
    )


@app.exception_handler(AppException)
def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.message},
    )


app.include_router(user_router)
app.include_router(lobby_router)
app.include_router(room_websocket_router)
