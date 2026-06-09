from app.services.reconciliation import OrderReconciliationService


def test_reconciliation_maps_exchange_statuses():
    service = OrderReconciliationService()
    assert service._map_status("closed") == "FILLED"
    assert service._map_status("canceled") == "CANCELLED"
    assert service._map_status("rejected") == "FAILED"
    assert service._map_status("open") == "NEW"
    assert service._map_status("mystery") is None
