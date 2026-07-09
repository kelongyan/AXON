import logging
import time

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.services.embeddings import OpenAICompatibleEmbeddingClient
from app.services.llm import OpenAICompatibleLLMClient
from app.services.workflows import execute_next_queued_run


def run_worker() -> None:
    logger = configure_logging()
    settings = Settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    llm_client = OpenAICompatibleLLMClient.from_settings(settings)
    embedding_client = OpenAICompatibleEmbeddingClient.from_settings(settings)
    logger.info(
        "AgentFlow worker started",
        extra={"settings": settings.safe_summary()},
    )
    while True:
        try:
            with session_scope(session_factory) as session:
                result = execute_next_queued_run(
                    session,
                    workspace_id=None,
                    llm_client=llm_client,
                    embedding_client=embedding_client,
                )
                if result is not None:
                    logger.info("Executed queued run", extra={"run_id": str(result.id), "status": result.status})
        except Exception:
            logger.exception("Worker polling cycle failed")
        time.sleep(30)


if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        logging.getLogger("agentflow.api").info("AgentFlow worker stopped")
