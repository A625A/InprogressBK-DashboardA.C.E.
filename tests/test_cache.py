from unittest.mock import Mock

import pytest

from app.core.cache import DashboardCache
from app.schemas.dashboard import MonthlyValues, Totals


@pytest.fixture
def clock():
    return Mock(return_value=100.0)


def test_hit_miss_and_exact_expiration_without_sleep(clock):
    cache = DashboardCache(60, clock=clock)
    load = Mock(return_value=Totals(total_polizas=1, valor_importado_total=12))
    assert cache.get_or_load("totals", load).total_polizas == 1
    clock.return_value = 159.999
    assert cache.get_or_load("totals", load).total_polizas == 1
    assert load.call_count == 1
    clock.return_value = 160
    cache.get_or_load("totals", load)
    assert load.call_count == 2


def test_cached_values_are_not_shared_mutable_objects(clock):
    cache = DashboardCache(60, clock=clock)
    load = Mock(return_value=Totals(total_polizas=1, valor_importado_total=12))
    cache.get_or_load("totals", load).total_polizas = 999
    cache.get_or_load("totals", load).total_polizas = 888
    assert cache.get_or_load("totals", load).total_polizas == 1
    assert load.call_count == 1


def test_loader_errors_are_not_cached(clock):
    cache = DashboardCache(60, clock=clock)
    load = Mock(
        side_effect=[
            RuntimeError("database unavailable"),
            Totals(total_polizas=1, valor_importado_total=12),
        ]
    )
    with pytest.raises(RuntimeError):
        cache.get_or_load("totals", load)
    assert cache.get_or_load("totals", load).total_polizas == 1
    cache.get_or_load("totals", load)
    assert load.call_count == 2


def test_invalidation_during_load_does_not_repopulate_stale_value(clock):
    cache = DashboardCache(60, clock=clock)

    def load_before_commit():
        cache.invalidate_policy(2025)
        return Totals(total_polizas=0, valor_importado_total=0)

    cache.get_or_load("totals", load_before_commit)
    fresh = Mock(return_value=Totals(total_polizas=1, valor_importado_total=10))
    assert cache.get_or_load("totals", fresh).total_polizas == 1
    fresh.assert_called_once()


def test_memory_is_bounded_and_expired_entries_are_removed(clock):
    cache = DashboardCache(60, clock=clock)
    for year in range(1, 258):
        cache.get_or_load(
            "valor-por-mes", lambda year=year: MonthlyValues(year=year, meses=[]), year=year
        )
    assert len(cache._entries) == 256
    clock.return_value = 160
    cache.get_or_load("totals", lambda: Totals(total_polizas=0, valor_importado_total=0))
    assert len(cache._entries) == 1
