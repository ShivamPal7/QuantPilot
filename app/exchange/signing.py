"""Delta Exchange API request signature generation.

Per Section 6.2 of agent.md:
Authentication requires four headers:
1. 'api-key': User's API key
2. 'signature': HMAC-SHA256 hex digest of (method + timestamp + path + query_string + body)
3. 'timestamp': Unix timestamp in SECONDS as string
4. 'User-Agent': Custom user agent (required by CDN)
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping


DEFAULT_USER_AGENT = "QuantPilot-GlassBoxDesk/1.0"


def generate_delta_signature(
    secret: str,
    method: str,
    timestamp: str | int,
    path: str,
    query_string: str = "",
    body: str = "",
) -> str:
    """Generate the HMAC-SHA256 hex digest for Delta Exchange authentication."""
    # Ensure query string formatting has leading '?' if present and non-empty
    formatted_query = ""
    if query_string:
        formatted_query = query_string if query_string.startswith("?") else f"?{query_string}"

    # Concatenate method, timestamp, path, query, and payload
    payload = f"{method.upper()}{timestamp}{path}{formatted_query}{body}"

    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return digest


def build_auth_headers(
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    query_string: str = "",
    body: str = "",
    user_agent: str = DEFAULT_USER_AGENT,
    timestamp_seconds: int | None = None,
) -> dict[str, str]:
    """Construct all required headers for an authenticated Delta request."""
    ts = str(timestamp_seconds if timestamp_seconds is not None else int(time.time()))

    signature = generate_delta_signature(
        secret=api_secret,
        method=method,
        timestamp=ts,
        path=path,
        query_string=query_string,
        body=body,
    )

    return {
        "api-key": api_key,
        "signature": signature,
        "timestamp": ts,
        "User-Agent": user_agent,
        "Content-Type": "application/json",
    }
