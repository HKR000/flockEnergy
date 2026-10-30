from app.client.portal_client import PortalClient


def test_hmac_signature_calculation():
    """Verify HMAC signature calculation format and output."""
    client = PortalClient()
    secret = "test-secret-key-12345"
    method = "GET"
    path = "/portal/export"
    query = "page=1"
    timestamp = "1729000000"

    sig = client.compute_hmac_signature(method, path, query, timestamp, secret)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex digest length
    expected = client.compute_hmac_signature(method, path, query, timestamp, secret)
    assert sig == expected


def test_client_initialization_defaults():
    client = PortalClient()
    assert client.base_url == "https://urja-ops.flockenergy.tech"
    assert client.email == "operator@urja.local"
    assert client.password == "urja-ops-2026"
