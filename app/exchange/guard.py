"""Testnet-Only Safety Guard.

Per Section 2.1 of agent.md:
The system MUST refuse to start unless the configured exchange host is a recognised testnet host.
A denylist of production hosts must also exist. This is a startup check, not a convention.
No withdrawal or transfer functionality may exist anywhere in the codebase.
"""

from __future__ import annotations

from urllib.parse import urlparse


class ProductionAccessProhibitedError(RuntimeError):
    """Raised when an attempt is made to configure or connect to a production exchange host."""
    pass


class InvalidTestnetHostError(RuntimeError):
    """Raised when a configured host is not in the recognized testnet host allowlist."""
    pass


# Strict denylist of production Delta Exchange endpoints
DENIED_PRODUCTION_HOSTS: set[str] = {
    "api.delta.exchange",
    "cdn.deltaex.org",
    "socket.deltaex.org",
    "socket-pub.deltaex.org",
    "production-api.delta.exchange",
    "india-api.delta.exchange",
}

# Strict allowlist of recognized Delta Testnet endpoints (India Demo & Global Testnet)
ALLOWED_TESTNET_HOSTS: set[str] = {
    # India Testnet / Demo Account (Target per Section 6.1)
    "cdn-ind.testnet.deltaex.org",
    "socket-ind.testnet.deltaex.org",
    "socket-ind-pub.testnet.deltaex.org",
    # Global Testnet
    "testnet-api.delta.exchange",
    "socket.testnet.delta.exchange",
}


def extract_hostname(url_or_host: str) -> str:
    """Extract clean hostname from URL or raw host string."""
    if not url_or_host:
        return ""
    if "://" in url_or_host:
        parsed = urlparse(url_or_host)
        return parsed.hostname or ""
    # Strip any port or trailing slash
    return url_or_host.split(":")[0].split("/")[0].strip().lower()


def assert_testnet_environment(target_env: str, rest_url: str, ws_public_url: str = "", ws_private_url: str = "") -> None:
    """Validate that the target environment and all URLs target recognized testnet hosts only.

    Raises:
        ProductionAccessProhibitedError: If any host matches a production host.
        InvalidTestnetHostError: If any host is not an explicitly approved testnet host.
    """
    if target_env.lower() != "testnet":
        raise ProductionAccessProhibitedError(
            f"TARGET_ENV is configured as '{target_env}'. QuantPilot strictly enforces 'testnet' only."
        )

    urls_to_check = [rest_url]
    if ws_public_url:
        urls_to_check.append(ws_public_url)
    if ws_private_url:
        urls_to_check.append(ws_private_url)

    for url in urls_to_check:
        host = extract_hostname(url)
        if not host:
            raise InvalidTestnetHostError(f"Cannot parse valid hostname from URL: {url}")

        # 1. Denylist check
        if host in DENIED_PRODUCTION_HOSTS or "production" in host:
            raise ProductionAccessProhibitedError(
                f"SECURITY VIOLATION: Production exchange host '{host}' detected in URL '{url}'! Startup aborted."
            )

        # 2. Allowlist check
        if host not in ALLOWED_TESTNET_HOSTS and not host.endswith(".testnet.deltaex.org"):
            raise InvalidTestnetHostError(
                f"Host '{host}' is not a recognized Delta Exchange testnet host! Startup aborted."
            )
