from types import SimpleNamespace

from app.worker import main as worker_main


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, object] | None]] = []

    def info(self, message: str, *, extra: dict[str, object] | None = None) -> None:
        self.infos.append((message, extra))


def test_run_worker_once_passes_configured_claim_options(monkeypatch):
    session = FakeSession()
    llm_client = object()
    embedding_client = object()
    calls: list[dict[str, object]] = []

    def session_factory() -> FakeSession:
        return session

    def fake_execute_next_queued_run(
        current_session: FakeSession,
        *,
        workspace_id: object,
        llm_client: object,
        embedding_client: object,
        worker_id: str,
        lease_seconds: int,
    ) -> SimpleNamespace:
        calls.append(
            {
                "session": current_session,
                "workspace_id": workspace_id,
                "llm_client": llm_client,
                "embedding_client": embedding_client,
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
            }
        )
        return SimpleNamespace(id="run-1", status="succeeded")

    monkeypatch.setattr(worker_main, "execute_next_queued_run", fake_execute_next_queued_run)
    logger = FakeLogger()

    result = worker_main.run_worker_once(
        session_factory=session_factory,
        llm_client=llm_client,
        embedding_client=embedding_client,
        worker_id="worker-east-1",
        lease_seconds=90,
        logger=logger,
    )

    assert result is not None
    assert calls == [
        {
            "session": session,
            "workspace_id": None,
            "llm_client": llm_client,
            "embedding_client": embedding_client,
            "worker_id": "worker-east-1",
            "lease_seconds": 90,
        }
    ]
    assert session.committed is True
    assert session.closed is True
    assert logger.infos == [("Executed queued run", {"run_id": "run-1", "status": "succeeded"})]


def test_run_worker_poll_cycle_processes_until_empty_or_limit(monkeypatch):
    llm_client = object()
    embedding_client = object()
    logger = FakeLogger()
    calls: list[dict[str, object]] = []
    queued_results = [
        SimpleNamespace(id="run-1", status="succeeded"),
        SimpleNamespace(id="run-2", status="failed"),
        SimpleNamespace(id="run-3", status="succeeded"),
    ]

    def fake_run_worker_once(**kwargs: object) -> SimpleNamespace | None:
        calls.append(kwargs)
        if len(calls) > len(queued_results):
            return None
        return queued_results[len(calls) - 1]

    monkeypatch.setattr(worker_main, "run_worker_once", fake_run_worker_once)

    processed = worker_main.run_worker_poll_cycle(
        session_factory=lambda: object(),
        llm_client=llm_client,
        embedding_client=embedding_client,
        worker_id="worker-east-1",
        lease_seconds=90,
        max_runs=2,
        logger=logger,
    )

    assert processed == queued_results[:2]
    assert len(calls) == 2
    assert all(call["worker_id"] == "worker-east-1" for call in calls)
    assert all(call["lease_seconds"] == 90 for call in calls)
