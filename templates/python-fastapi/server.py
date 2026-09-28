"""
Kite x402 service template (Python + FastAPI).

Wraps an existing HTTP API behind x402 payments settled on the Kite chain.
Requests to /v1/* return HTTP 402 until the caller attaches a valid
PAYMENT-SIGNATURE; the payment is verified by the facilitator, the request
is proxied to UPSTREAM_URL, and the payment is settled only if the upstream
answered with a non-error status.

Usage
-----
    # Set environment variables
    export PAY_TO=0xYourWallet
    export UPSTREAM_URL=https://api.example.com
    export PRICE_USD=0.001

    # Start the server
    uvicorn server:app --port 8080

    # Test unpaid
    curl -i http://localhost:8080/v1/forecast?latitude=52.52&longitude=13.41
"""

from __future__ import annotations

import logging
import os
import sys
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from kite import FACILITATOR_URL, kite_chain_by_name, kite_money_parser

# ---------------------------------------------------------------------------
# SDK imports (install via ``pip install 'x402[evm,fastapi]'``)
# ---------------------------------------------------------------------------
from x402.http import (
    HTTPFacilitatorClient,
    FacilitatorConfig,
    PaymentOption,
    RouteConfig,
    RoutesConfig,
)
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s kite-x402 %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()


def env(key: str, fallback: str = "") -> str:
    return (os.environ.get(key) or "").strip() or fallback


# ---- Required ----
PAY_TO = env("PAY_TO")
if not PAY_TO:
    raise SystemExit("PAY_TO is required: the Kite wallet address that receives payments")

UPSTREAM_URL = env("UPSTREAM_URL")
if not UPSTREAM_URL:
    raise SystemExit("UPSTREAM_URL is required, e.g. https://api.example.com")
# Quick validation
parsed_upstream = urlparse(UPSTREAM_URL)
if not parsed_upstream.scheme or not parsed_upstream.netloc:
    raise SystemExit(f"UPSTREAM_URL is not a valid URL: {UPSTREAM_URL}")

# ---- Optional ----
CHAIN = kite_chain_by_name(env("KITE_NETWORK", "mainnet"))
PRICE_RAW = env("PRICE_USD", "0.001")
PRICE = f"${PRICE_RAW}" if not PRICE_RAW.startswith("$") else PRICE_RAW
UPSTREAM_AUTH_HEADER = env("UPSTREAM_AUTH_HEADER", "Authorization")
UPSTREAM_AUTH_VALUE = env("UPSTREAM_AUTH_VALUE")
SERVICE_DESCRIPTION = env("SERVICE_DESCRIPTION", "Paid API wrapped for the Kite network")
PORT = int(env("PORT", "8080"))
FACILITATOR_URL_OVERRIDE = env("FACILITATOR_URL", FACILITATOR_URL)

# ---------------------------------------------------------------------------
# x402 server setup
# ---------------------------------------------------------------------------

# 1. Facilitator client
facilitator = HTTPFacilitatorClient(
    FacilitatorConfig(url=FACILITATOR_URL_OVERRIDE)
)

# 2. Resource server with Kite-specific money parser
scheme = ExactEvmServerScheme().register_money_parser(kite_money_parser(CHAIN))
server = x402ResourceServer(facilitator)
server.register(CHAIN.network, scheme)

# 3. Route config — every path under /v1/* is paid
routes: RoutesConfig = {
    "/v1/*": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                price=PRICE,
                network=CHAIN.network,
                pay_to=PAY_TO,
                max_timeout_seconds=60,
            ),
        ],
        description=SERVICE_DESCRIPTION,
        mime_type="application/json",
    ),
}

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

from fastapi import FastAPI, Request, Response
from starlette.responses import JSONResponse

app = FastAPI(
    title=f"Kite x402 service ({CHAIN.asset_symbol})",
    version="0.1.0",
)

# ---- Build middleware closure once (state persists across requests) ----
_x402_middleware = payment_middleware(
    routes,
    server,
)


@app.middleware("http")
async def x402_middleware(request: Request, call_next):
    return await _x402_middleware(request, call_next)


@app.get("/healthz")
async def healthz():
    """Free health-check endpoint (load-balancer safe)."""
    return {
        "ok": True,
        "network": CHAIN.network,
        "asset": CHAIN.asset_symbol,
        "price": PRICE,
    }


@app.api_route(
    "/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def proxy_v1(request: Request, path: str):
    """Proxy paid requests to the upstream API.

    This handler is reached only after the PaymentMiddlewareASGI has verified
    the caller's PAYMENT-SIGNATURE. The upstream credential is injected here
    and never reaches the caller.
    """
    # Reconstruct the upstream URL: strip /v1 prefix.
    upstream_path = f"/{path}" if path else "/"
    target_url = f"{UPSTREAM_URL.rstrip('/')}{upstream_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Build upstream headers (strip hop-by-hop + the payment signature).
    hop_by_hop = frozenset({
        "connection", "keep-alive", "transfer-encoding",
        "te", "trailer", "upgrade", "host", "content-length",
    })
    headers = dict(request.headers)
    for key in list(headers.keys()):
        lower = key.lower()
        if lower in hop_by_hop or lower == "payment-signature":
            del headers[key]

    if UPSTREAM_AUTH_VALUE:
        headers[UPSTREAM_AUTH_HEADER] = UPSTREAM_AUTH_VALUE

    # Forward the body for non-GET/HEAD requests.
    has_body = request.method not in ("GET", "HEAD")
    body = await request.body() if has_body else None

    try:
        async with httpx.AsyncClient() as client:
            upstream_resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                timeout=30.0,
            )
    except httpx.RequestError as exc:
        # 502 is >= 400, so the payment middleware does not settle the charge.
        return JSONResponse(
            status_code=502,
            content={"error": "upstream unreachable", "detail": str(exc)},
        )

    # Build the response — stream back the upstream body and headers.
    upstream_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in hop_by_hop and k.lower() != "content-encoding"
    }
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=upstream_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

log.info(
    "kite x402 service on :%d -> %s (network %s, %s per call to %s)",
    PORT,
    UPSTREAM_URL,
    CHAIN.network,
    PRICE,
    PAY_TO,
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
    )
