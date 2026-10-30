import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class PortalError(Exception):
    """Base exception for upstream portal errors."""
    pass


class PortalAuthError(PortalError):
    """Raised when portal authentication fails."""
    pass


class PortalRequestError(PortalError):
    """Raised when upstream returns an unexpected error."""
    pass


class PortalClient:
    """Robust client interfacing with the upstream Urja Meter Ops portal.
    
    Handles:
    - SvelteKit CSRF headers and form actions
    - Better-Auth session cookie persistence and auto-renewal on 401
    - HMAC-SHA256 signature generation for authenticated bulk exports
    - Error handling, timeouts, and transparent retries
    """

    def __init__(
        self,
        base_url: str = "https://urja-ops.flockenergy.tech",
        email: str = "operator@urja.local",
        password: str = "urja-ops-2026",
        timeout: float = 15.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._auth_lock: Optional[asyncio.Lock] = None
        self._is_authenticated = False
        self._session_token: Optional[str] = None

    def _get_auth_lock(self) -> asyncio.Lock:
        if self._auth_lock is None:
            self._auth_lock = asyncio.Lock()
        return self._auth_lock

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Urja-API-Gateway/1.0",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/login",
                },
            )
        return self._client

    async def close(self):
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            self._is_authenticated = False

    async def authenticate(self) -> None:
        """Authenticate with the Urja portal and store the session cookie."""
        async with self._get_auth_lock():
            client = await self._get_client()
            logger.info("Authenticating with Urja Meter Ops at %s", self.base_url)

            # SvelteKit login action requires 'email' and 'password' form fields
            login_data = {
                "email": self.email,
                "password": self.password,
            }

            try:
                # Do NOT follow redirects automatically on login so we capture 200/303 and set-cookie
                resp = await client.post(
                    f"{self.base_url}/login",
                    data=login_data,
                    headers={
                        "Origin": self.base_url,
                        "Referer": f"{self.base_url}/login",
                    },
                )
            except Exception as e:
                raise PortalAuthError(f"Network error during login: {e}") from e

            if resp.status_code not in (200, 303):
                raise PortalAuthError(
                    f"Login failed with status {resp.status_code}: {resp.text[:200]}"
                )

            # Check if session cookie was established
            cookies = client.cookies
            token = cookies.get("__Secure-better-auth.session_token")
            if not token:
                # In case cookies dict format differs, inspect headers
                set_cookie = resp.headers.get("set-cookie", "")
                if "__Secure-better-auth.session_token" not in set_cookie and not cookies:
                    raise PortalAuthError("No session cookie set after login")

            self._is_authenticated = True
            self._session_token = token
            logger.info("Urja portal authentication successful")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """Execute request with automatic 401 re-authentication."""
        if not self._is_authenticated:
            await self.authenticate()

        client = await self._get_client()
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"

        req_headers = {
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/meters",
        }
        if headers:
            req_headers.update(headers)

        try:
            resp = await client.request(
                method=method,
                url=url,
                params=params,
                headers=req_headers,
            )
        except Exception as e:
            raise PortalRequestError(f"Request failed to {path}: {e}") from e

        if resp.status_code == 401 and retry_on_401:
            logger.warning("Session expired (401). Re-authenticating...")
            self._is_authenticated = False
            await self.authenticate()
            return await self._request(
                method, path, params=params, headers=headers, retry_on_401=False
            )

        return resp

    async def search_meters(self, query: str = "", page: int = 1) -> Dict[str, Any]:
        """Query the portal's search endpoint (/portal/meters/search)."""
        resp = await self._request(
            "GET",
            "/portal/meters/search",
            params={"q": query, "page": page},
        )
        if resp.status_code != 200:
            raise PortalRequestError(f"Search failed: HTTP {resp.status_code}")
        return resp.json()

    async def get_meter_geo(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """Fetch real-time geolocation for a meter (/portal/meters/{id}/geo)."""
        resp = await self._request("GET", f"/portal/meters/{meter_id}/geo")
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise PortalRequestError(f"Get geo failed: HTTP {resp.status_code}")
        data = resp.json()
        return data.get("data")

    async def get_meter_energy(self, meter_id: str) -> List[Dict[str, Any]]:
        """Fetch interval energy consumption readings for a meter (/portal/meters/{id}/energy)."""
        resp = await self._request("GET", f"/portal/meters/{meter_id}/energy")
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            raise PortalRequestError(f"Get energy failed: HTTP {resp.status_code}")
        data = resp.json()
        return data.get("data", [])

    async def get_transformers(self, page: int = 1) -> Dict[str, Any]:
        """Fetch a page of distribution transformers (/portal/dts)."""
        resp = await self._request("GET", "/portal/dts", params={"page": page})
        if resp.status_code != 200:
            raise PortalRequestError(f"Get transformers failed: HTTP {resp.status_code}")
        return resp.json()

    async def get_all_transformers(self) -> List[Dict[str, Any]]:
        """Fetch all distribution transformers across all pages."""
        first_page = await self.get_transformers(page=1)
        total = first_page.get("total", 0)
        items = list(first_page.get("data", []))
        page = 2
        while len(items) < total:
            next_page = await self.get_transformers(page=page)
            data = next_page.get("data", [])
            if not data:
                break
            items.extend(data)
            page += 1
        return items

    async def get_signing_secret(self) -> str:
        """Fetch export signing secret key (/portal/keys)."""
        resp = await self._request("GET", "/portal/keys")
        if resp.status_code != 200:
            raise PortalRequestError(f"Get keys failed: HTTP {resp.status_code}")
        body = resp.json()
        secret = body.get("data", {}).get("signingSecret")
        if not secret:
            raise PortalRequestError("Signing secret not found in portal response")
        return secret

    def compute_hmac_signature(
        self, method: str, path: str, query: str, timestamp: str, secret: str
    ) -> str:
        """Compute HMAC-SHA256 signature matching the portal's SubtleCrypto implementation.
        
        Format: String composed of lines:
        <METHOD>
        <PATH>
        <QUERY>
        <TIMESTAMP>
        """
        payload = f"{method}\n{path}\n{query}\n{timestamp}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return signature

    async def export_all_meters(self) -> List[Dict[str, Any]]:
        """Execute signed bulk export endpoint (/portal/export?page=1).
        
        Returns all meters with full network hierarchy and geolocation.
        """
        secret = await self.get_signing_secret()
        timestamp = str(int(time.time()))
        path = "/portal/export"
        query = "page=1"
        signature = self.compute_hmac_signature("GET", path, query, timestamp, secret)

        resp = await self._request(
            "GET",
            f"{path}?{query}",
            headers={
                "x-timestamp": timestamp,
                "x-signature": signature,
            },
        )
        if resp.status_code != 200:
            raise PortalRequestError(
                f"Export failed with status {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        return data.get("data", [])

    async def check_health(self) -> bool:
        """Ping upstream portal login page to verify connectivity."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/login")
            return resp.status_code == 200
        except Exception:
            return False
