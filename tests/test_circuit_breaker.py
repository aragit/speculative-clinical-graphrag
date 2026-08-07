import pytest
import asyncio
import time
from core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


@pytest.fixture
def breaker():
    return CircuitBreaker(
        name="test",
        failure_threshold=3,
        recovery_timeout=0.1,
        half_open_max_calls=1,
    )


def test_initial_state_closed(breaker):
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_closes_after_success(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.failure_count == 0


def test_opens_after_threshold(breaker):
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


def test_half_open_after_recovery_timeout(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    time.sleep(0.15)
    assert breaker._can_attempt() is True
    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_opens_on_failure(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    time.sleep(0.15)
    breaker._can_attempt()
    assert breaker.state == CircuitState.HALF_OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_half_open_closes_after_success(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    time.sleep(0.15)
    breaker._can_attempt()
    assert breaker.state == CircuitState.HALF_OPEN
    breaker.record_success()
    assert breaker.half_open_calls >= 1


@pytest.mark.asyncio
async def test_call_success(breaker):
    async def _ok():
        return "success"
    result = await breaker.call(_ok)
    assert result == "success"


@pytest.mark.asyncio
async def test_call_raises_on_open(breaker):
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(lambda: asyncio.sleep(0))


@pytest.mark.asyncio
async def test_call_records_failure(breaker):
    async def _fail():
        raise ValueError("test error")

    with pytest.raises(ValueError):
        await breaker.call(_fail)

    assert breaker.failure_count == 1
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_call_sync_function(breaker):
    def _sync_ok():
        return "sync_result"
    result = await breaker.call(_sync_ok)
    assert result == "sync_result"
