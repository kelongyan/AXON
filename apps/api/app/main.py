from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agents import router as agents_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.tools import router as tools_router
from app.api.routes.workflows import router as workflows_router
from app.core.config import Settings
from app.core.errors import unhandled_exception_handler
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory
from app.services.embeddings import OpenAICompatibleEmbeddingClient
from app.services.llm import OpenAICompatibleLLMClient
from app.services.storage import MinioObjectStore


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    logger = configure_logging()

    app = FastAPI(
        title="AgentFlow API",
        version=app_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = app_settings
    app.state.logger = logger
    app.state.engine = create_database_engine(app_settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.llm_client = OpenAICompatibleLLMClient.from_settings(app_settings)
    app.state.embedding_client = OpenAICompatibleEmbeddingClient.from_settings(app_settings)
    app.state.object_store = MinioObjectStore.from_settings(app_settings)

    if app_settings.cors_allowed_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_allowed_origin_list,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(health_router)
    app.include_router(agents_router)
    app.include_router(tools_router)
    app.include_router(knowledge_bases_router)
    app.include_router(workflows_router)
    app.include_router(evaluations_router)
    return app


app = create_app()
