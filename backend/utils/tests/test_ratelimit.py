"""Kuota atomik di basis data (utils.ratelimit) untuk panggilan AI berbayar."""

import datetime
import threading

import pytest
from django.db import close_old_connections
from django.utils import timezone

from utils import ratelimit
from utils.models import RateCounter


@pytest.mark.django_db
def test_consume_stops_at_limit_and_resets_after_window():
    assert [ratelimit.consume("uji", 3, 60) for _ in range(5)] == [
        True,
        True,
        True,
        False,
        False,
    ]
    assert RateCounter.objects.get(key="uji").count == 3
    RateCounter.objects.filter(key="uji").update(
        expires_at=timezone.now() - datetime.timedelta(seconds=1)
    )
    assert ratelimit.consume("uji", 3, 60) is True
    assert RateCounter.objects.get(key="uji").count == 1
    assert ratelimit.consume("kosong", 0, 60) is False


@pytest.mark.django_db(transaction=True)
def test_concurrent_consumers_never_exceed_limit():
    limit, workers = 5, 16
    barrier = threading.Barrier(workers)
    results = []
    lock = threading.Lock()

    def worker():
        try:
            barrier.wait()
            taken = ratelimit.consume("serentak", limit, 3600)
            with lock:
                results.append(taken)
        finally:
            close_old_connections()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == workers
    assert results.count(True) == limit
    assert RateCounter.objects.get(key="serentak").count == limit
