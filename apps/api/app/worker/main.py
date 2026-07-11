import logging
import threading
import time
from collections.abc import Callable

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.services.embeddings import OpenAICompatibleEmbeddingClient
from app.services.llm import OpenAICompatibleLLMClient
from app.services.workflows import RunExecutionError, claim_next_queued_run, execute_claimed_run, renew_run_lease


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
        claimed = claim_next_queued_run(
            session,
            workspace_id=None,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if claimed is None:
            return None
        if claimed.claim_token is None:
            raise RunExecutionError("Claimed run is missing claim token")
        run_id = claimed.id
        workspace_id = claimed.workspace_id
        claim_token = claimed.claim_token

    stop_heartbeat = threading.Event()
    heartbeat = threading.Thread(
        target=_renew_claim_until_stopped,
        kwargs={
            "session_factory": session_factory,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "claim_token": claim_token,
            "lease_seconds": lease_seconds,
            "stop_event": stop_heartbeat,
            "logger": logger,
        },
        daemon=True,
    )
    heartbeat.start()
    try:
        with session_scope(session_factory) as session:
            result = execute_claimed_run(
                session,
                workspace_id=workspace_id,
                run_id=run_id,
                claim_token=claim_token,
                llm_client=llm_client,
                embedding_client=embedding_client,
            )
            logger.info("Executed queued run", extra={"run_id": str(result.id), "status": result.status})
            return result
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=1)


def _renew_claim_until_stopped(
    *,
    session_factory: Callable[[], object],
    workspace_id: object,
    run_id: object,
    claim_token: str,
    lease_seconds: int,
    stop_event: threading.Event,
    logger: logging.Logger,
) -> None:
    interval_seconds = max(1.0, lease_seconds / 2)
    while not stop_event.is_set():
        try:
            with session_scope(session_factory) as session:
                renewed = renew_run_lease(
                    session,
                    workspace_id=workspace_id,
                    run_id=run_id,
                    claim_token=claim_token,
                    lease_seconds=lease_seconds,
                )
            if not renewed:
                logger.warning("Run lease renewal skipped", extra={"run_id": str(run_id)})
                return
        except Exception:
            logger.exception("Run lease renewal failed", extra={"run_id": str(run_id)})
            return
        stop_event.wait(interval_seconds)


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
