"""Supabase client transport configuration."""

from types import SimpleNamespace

from app.core import supabase_client


def test_supabase_clients_disable_http2(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        supabase_client,
        "get_settings",
        lambda: SimpleNamespace(supabase_url="https://example.supabase.co"),
    )
    monkeypatch.setattr(
        supabase_client,
        "create_client",
        lambda _url, _key, options: captured.append(options) or object(),
    )
    supabase_client._http_client.cache_clear()

    supabase_client._build_client("test-key")

    client = captured[0].httpx_client
    assert client is not None
    assert client._transport._pool._http2 is False
    client.close()
