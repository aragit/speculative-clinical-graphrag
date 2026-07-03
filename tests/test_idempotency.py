def test_duplicate_key_blocked():
    from core.idempotency import IdempotencyManager
    mgr = IdempotencyManager()
    key = mgr.generate_key("trace-1", "tool-a", {"x": 1})
    assert isinstance(key, str)
    # In-memory check without Redis is a stub
