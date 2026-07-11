import logging
import time
from collections.abc import Callable

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.services.embeddings import OpenAICompatibleEmbeddingClient
from app.services.llm import OpenAICompatibleLLMClient
from app.services.workflows import execute_next_queued_run


def run_worker_once(
    *,
    session_factory: Callable[[], object],
    llm_client: object,
    embedding_client: object,
    worker_id: str,
    lease_seconds: int,
    logger: logging.Logger,
) -> object | None:
    with session_scope(session_factory) as session:
        result = execute_next_queued_run(
            session,
            workspace_id=None,
            llm_client=llm_client,
            embedding_client=embedding_client,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if result is not None:
            logger.info("Executed queued run", extra={"run_id": str(result.id), "status": result.status})
        return result


def run_worker_poll_cycle(
    *,
    session_factory: Callable[[], object],
    llm_client: object,
    embedding_client: object,
    worker_id: str,
    lease_seconds: int,
    max_runs: int,
    logger: logging.Logger,
) -> list[object]:
    processed: list[object] = []
    for _ in range(max(1, max_runs)):
        result = run_worker_once(
            session_factory=session_factory,
            llm_client=llm_client,
            embedding_client=embedding_client,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            logger=logger,
        )
        if result is None:
            break
        processed.append(result)
    return processed


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
            run_worker_poll_cycle(
                session_factory=session_factory,
                llm_client=llm_client,
                embedding_client=embedding_client,
                worker_id=settings.worker_id,
                lease_seconds=settings.worker_lease_seconds,
                max_runs=settings.worker_max_runs_per_cycle,
                logger=logger,
            )
        except Exception:
            logger.exception("Worker polling cycle failed")
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        logging.getLogger("agentflow.api").info("AgentFlow worker stopped")
