"""Shared pytest fixtures for E2E tests.

Two fixtures:
  - kafka_bootstrap_servers (session-scoped, sync):
      Provides a Kafka broker address. Uses the KAFKA_BOOTSTRAP_SERVERS env var if
      set (e.g. for CI with docker-compose), otherwise starts a KafkaContainer via
      testcontainers.

  - harness (function-scoped, async):
      Creates and tears down an E2ETestHarness per test. Depends on
      kafka_bootstrap_servers so each test gets a connected harness.

Usage in tests:
    @pytest.mark.e2e
    async def test_something(harness):
        result = await harness.run(make_ingest_envelope())
        assert result.published
"""

import os

import pytest

from tests.e2e.helpers import E2ETestHarness

# ---------------------------------------------------------------------------
# Kafka bootstrap server fixture (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def kafka_bootstrap_servers():
    """Provide a running Kafka bootstrap address for the entire test session.

    Precedence:
      1. KAFKA_BOOTSTRAP_SERVERS env var — use a pre-existing broker
         (e.g. started via `docker-compose -f docker-compose.e2e.yml up -d`)
      2. testcontainers KafkaContainer — spin up a temporary broker automatically

    The session scope ensures the container is started once and reused across
    all E2E tests, reducing total test time significantly.
    """
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if bootstrap:
        yield bootstrap
        return

    # Lazy import so non-E2E test runs don't pay the testcontainers import cost
    from testcontainers.kafka import KafkaContainer

    with KafkaContainer(image="confluentinc/cp-kafka:7.5.0") as kafka:
        yield kafka.get_bootstrap_server()


# ---------------------------------------------------------------------------
# E2ETestHarness fixture (function-scoped, async)
# ---------------------------------------------------------------------------


@pytest.fixture
async def harness(kafka_bootstrap_servers):
    """Create a wired E2ETestHarness for a single test function.

    The harness is started (Kafka producer connected, domain registry loaded)
    before the test and stopped (producer connection closed) after, regardless
    of whether the test passes or fails.

    Scope: function — each test gets a fresh harness with a new producer
    connection, avoiding cross-test state leakage.
    """
    h = E2ETestHarness(bootstrap_servers=kafka_bootstrap_servers)
    await h.start()
    yield h
    await h.stop()
