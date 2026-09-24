from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class AtomicClaimFixture:
    """In-memory model of the DB claim invariant used only for concurrency certification."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.status = "queued"
        self.successful_claims = 0

    def claim(self) -> bool:
        with self._lock:
            if self.status != "queued":
                return False
            self.status = "running"
            self.successful_claims += 1
            return True


def test_many_simultaneous_watchers_produce_one_successful_claim() -> None:
    fixture = AtomicClaimFixture()
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: fixture.claim(), range(64)))
    assert sum(results) == 1
    assert fixture.successful_claims == 1
    assert fixture.status == "running"


def test_duplicate_wakeup_burst_does_not_imply_duplicate_execution() -> None:
    fixture = AtomicClaimFixture()
    # Wake-ups are deliberately allowed to be duplicated; execution ownership is not.
    wakeups = 25
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: fixture.claim(), range(wakeups)))
    assert wakeups == 25
    assert sum(claims) == 1
