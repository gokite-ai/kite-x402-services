# Kite x402 Services

Turn any HTTP API into a paid service that AI agents on the [Kite](https://gokite.ai)
network can call and pay for per request, using the
[x402](https://www.x402.org) protocol with settlement on the Kite chain.

You bring the API. This repo gives you a wrapper template that answers
`402 Payment Required`, verifies and settles the payment through the Kite
facilitator, and proxies paid requests to your upstream. You deploy it, add a
manifest here, and Kite Passport agents can discover and pay for it.

```
agent (Kite Passport)                 your wrapper                      upstream API
────────────────────                 ─────────────                     ────────────
GET /v1/forecast ───────────────────► 402 + PAYMENT-REQUIRED
                                       (network, asset, amount, payTo)
sign EIP-3009 authorization
GET /v1/forecast
  PAYMENT-SIGNATURE: … ─────────────► facilitator /verify ✓
                                       GET /forecast ──────────────────► 200 JSON
                                       facilitator /settle ✓ (on-chain)
◄──────────────────────────────────── 200 JSON + PAYMENT-RESPONSE (tx hash)
```

**Who hosts what.** Kite also runs its own gateway, `kite-services`, which
fronts a curated set of upstream APIs behind Kite's wallet. This repo is the
self-hosted counterpart: you run the wrapper, you hold the upstream key, and
payments go to your wallet.

No smart contracts, no wallet code, no gas: the buyer signs a token
authorization, the facilitator broadcasts it and pays gas, and USDC.e lands in
your wallet. The wrapper is a ~100-line reverse proxy.

## Quick start

Pick a template:

| Template | Stack | Start here |
|---|---|---|
| [`templates/typescript-express`](templates/typescript-express) | Node 22, Express 5, `@x402/express` | `npm install && npm run dev` |
| [`templates/go-gin`](templates/go-gin) | Go 1.25, Gin, `github.com/coinbase/x402/go` | `go run .` |
| [`templates/python-fastapi`](templates/python-fastapi) | Python 3.14, FastAPI, `x402[fastapi]` | `just install && just run` |

Both read the same environment variables:

```bash
PAY_TO=0xYourKiteWallet          # receives the payments
KITE_NETWORK=mainnet             # mainnet (USDC.e) or testnet (pieUSD)
UPSTREAM_URL=https://api.open-meteo.com
PRICE_USD=0.001                  # per call
UPSTREAM_AUTH_HEADER=Authorization   # optional: credential injected upstream
UPSTREAM_AUTH_VALUE=Bearer sk-...    # never reaches the buyer
```

Run it and hit a paid route:

```bash
curl -i "localhost:8080/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m"
```

You get `HTTP/1.1 402 Payment Required` and a base64 `PAYMENT-REQUIRED` header
that decodes to:

```json
{
  "x402Version": 2,
  "accepts": [{
    "scheme": "exact",
    "network": "eip155:2366",
    "asset": "0x7aB6f3ed87C42eF0aDb67Ed95090f8bF5240149e",
    "amount": "1000",
    "payTo": "0xYourKiteWallet",
    "maxTimeoutSeconds": 60,
    "extra": { "name": "Bridged USDC (Kite AI)", "version": "2" }
  }]
}
```

Every path under `/v1/` is paid and proxied to `UPSTREAM_URL` with the `/v1`
prefix stripped. `/healthz` is free. That is the whole contract.

## Go live

1. Deploy the wrapper anywhere that serves public **https** (Fly, Render,
   Cloud Run, a VPS). Kite Passport calls your URL from its servers, so
   localhost and browser-gated tunnels do not work.
2. Copy your wrapper into `services/<name>/` with a `service.yaml` manifest
   and a `README.md`. The example [`services/open-meteo-weather`](services/open-meteo-weather)
   shows the shape; the schema is [`schema/service.schema.json`](schema/service.schema.json).
3. Pay for one call yourself (next section) and open a PR with the output.

Full checklist: [CONTRIBUTING.md](CONTRIBUTING.md).

## Test with a Kite Passport agent

Install the `kpass` CLI (see the
[Kite Passport docs](https://docs.gokite.ai)), then let an agent pay your
service. Use **testnet** first: set `KITE_NETWORK=testnet` on your deployment
and put the CLI in sandbox mode, which pays with free pieUSD on Kite testnet.

```bash
kpass login init --email you@example.com
kpass login verify --login-id <id-from-init> --code <otp>

kpass sandbox on                                   # testnet mode
kpass wallet address                               # your agent wallet
kpass faucet drop --recipient <that-address> --token pieUSD

kpass agent register --type service-tester
kpass agent session create \
  --task-summary "test my x402 wrapper" \
  --max-amount-per-tx 0.05 --max-total-amount 1 --assets pieUSD --ttl 1h
# open the printed approval URL in a browser and approve with your passkey

kpass agent session execute --method GET \
  --url "https://your-host/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m"
```

A successful run prints HTTP 200, the upstream body and the settlement
transaction hash. Run `kpass sandbox off` and repeat against a
`KITE_NETWORK=mainnet` deployment with `--assets USDC` to confirm the live path.

## Kite network reference

| | Mainnet | Testnet |
|---|---|---|
| CAIP-2 network | `eip155:2366` | `eip155:2368` |
| RPC | `https://rpc.gokite.ai` | `https://rpc-testnet.gokite.ai` |
| Settlement asset | USDC.e `0x7aB6f3ed87C42eF0aDb67Ed95090f8bF5240149e` (6 decimals) | pieUSD `0x38129cf4CE5E183eFF248F42A7D345Bb1B47621A` (18 decimals) |
| EIP-712 domain | name `Bridged USDC (Kite AI)`, version `2` | name `pieUSD`, version `1` |
| Facilitator | `https://facilitator.pieverse.io/v2` | same |

The templates encode all of this in `kite.ts` / `kite.go`. You should not need
to touch those files.

## Things that bite

- **Facilitator URL keeps the `/v2`.** The x402 SDKs append `/verify`, `/settle`
  and `/supported` to whatever base URL you give them. `https://facilitator.pieverse.io`
  without `/v2` returns 404s that surface as "settlement failed".
- **EIP-712 name/version must match the token exactly** or every signature is
  rejected. The Kite stablecoins are not in the x402 SDK's built-in asset table,
  which is why the templates register a custom money parser for `$0.001`-style
  prices instead of relying on defaults.
- **Settle only after the upstream succeeds.** Both templates verify the payment,
  call your upstream, then settle only when the upstream returned a status below
  400. Charging before validating is the number one complaint about paid APIs
  from agents. Do not reorder this.
- **The buyer never sees your upstream key.** It is injected by the proxy. Do not
  log request headers upstream of the strip, and do not commit `.env`.
- **Price in USD as a decimal string**, at most 6 fractional digits. Amounts in the
  402 challenge are integer token units (`"1000"` = $0.001 in USDC.e).
- **x402 is verb-agnostic.** Pattern `/v1/*` protects every method. If your
  upstream is read-only, restrict the proxy to `GET` in your wrapper.

## Repository layout

```
templates/typescript-express   Express wrapper template
templates/go-gin               Gin wrapper template
templates/python-fastapi       FastAPI (Python) wrapper template
services/<name>/               one deployed wrapper per directory + service.yaml
schema/service.schema.json     manifest schema (validated in CI)
scripts/validate.mjs           `npm run validate` (Node.js)
scripts/validate.py            `just validate` (Python)
```

## License

Apache-2.0. See [LICENSE](LICENSE).
