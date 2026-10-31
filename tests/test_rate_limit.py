import pytest
from pydantic import ValidationError

from app.models import ChatRequest
from app.rate_limit import RateLimiter, RecentThreads


def test_one_client_cannot_use_the_whole_allowance() -> None:
    limiter = RateLimiter(per_client=2, overall=10, window_seconds=60)

    assert [limiter.allow("a", now=0) for _ in range(3)] == [True, True, False]
    assert limiter.allow("b", now=0)


def test_the_overall_limit_holds_when_clients_change_their_address() -> None:
    limiter = RateLimiter(per_client=1, overall=3, window_seconds=60)

    results = [limiter.allow(f"forged-{n}", now=0) for n in range(5)]

    assert results == [True, True, True, False, False]


def test_limits_recover_after_the_window() -> None:
    limiter = RateLimiter(per_client=1, overall=1, window_seconds=60)

    assert limiter.allow("a", now=0)
    assert not limiter.allow("a", now=59)
    assert limiter.allow("a", now=60)


def test_the_oldest_thread_is_forgotten_first() -> None:
    threads = RecentThreads(capacity=2)

    assert threads.touch("a") == []
    assert threads.touch("b") == []
    assert threads.touch("a") == []  # Using a thread makes it the newest again.
    assert threads.touch("c") == ["b"]


@pytest.mark.parametrize(
    "fields",
    [
        {"thread_id": "t", "message": "x" * 1001},
        {"thread_id": "t", "message": ""},
        {"thread_id": "t" * 129, "message": "hi"},
        {"thread_id": "t", "message": "hi", "menu": {f"d{n}": 1 for n in range(51)}},
        {"thread_id": "t", "message": "hi", "menu": {"d" * 61: 1}},
    ],
)
def test_oversized_requests_are_refused(fields: dict) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(**fields)


def test_a_normal_request_is_accepted() -> None:
    assert ChatRequest(thread_id="t", message="two pizzas", menu={"pizza": 3})
