# Frankfurter FX Rates

Wraps the free [Frankfurter](https://frankfurter.dev) foreign-exchange API as an
x402 service on the Kite chain. Frankfurter serves European Central Bank
reference rates: no API key, no rate limit beyond fair use, and stable ISO-4217
currency codes. Built from the
[typescript-express template](../../templates/typescript-express); the only code
change from the template is that this wrapper forwards the `/v1` path unchanged
(Frankfurter's own routes already live under `/v1`).

| | |
|---|---|
| `GET /v1/latest` | latest rates -> `https://api.frankfurter.dev/v1/latest` |
| `GET /v1/YYYY-MM-DD` | rates for one date -> `.../v1/YYYY-MM-DD` |
| `GET /v1/START..END` | time series -> `.../v1/START..END` |
| Price | $0.001 per call ($0.002 for a range) in USDC.e (Kite mainnet) |
| Upstream auth | none |

## Endpoints

All three take the optional query params `base` (default EUR) and `symbols`
(comma-separated ISO-4217 codes). Rates publish once per working day around
16:00 CET; weekend requests return the previous Friday's quote.

```bash
# Latest USD rates for a few currencies
GET /v1/latest?base=USD&symbols=EUR,GBP,JPY

# Historical rates for a single day
GET /v1/2024-01-02?base=USD&symbols=EUR

# Time series across a date range (two dots between the dates)
GET /v1/2024-01-01..2024-01-31?base=USD&symbols=EUR
```

## Deploy

```bash
npm install
cp .env.example .env      # set PAY_TO to your Kite wallet; UPSTREAM_URL is already Frankfurter
npm run build && node dist/index.js
```

Any host that runs Node 22 works (Fly, Render, Cloud Run, a VPS). The service
must be reachable over public https: Kite Passport fetches the URL server-side,
so `localhost` and tunnels that require a browser check will not work.

`UPSTREAM_URL=https://api.frankfurter.dev` and Frankfurter needs no credential,
so `UPSTREAM_AUTH_VALUE` stays empty.

## Try it

```bash
curl -i "$BASE_URL/v1/latest?base=USD&symbols=EUR,GBP,JPY"
# 402 with a PAYMENT-REQUIRED header until a payment is attached

kpass agent session execute --method GET \
  --url "$BASE_URL/v1/latest?base=USD&symbols=EUR,GBP,JPY"
# 200 + Frankfurter JSON, paid from the agent's session
```

## Upstream terms

Frankfurter is open-source and free to use under fair-use terms (see
[frankfurter.dev](https://frankfurter.dev)). Data originates from the European
Central Bank. Keep call volume reasonable; there is no commercial tier to breach,
but heavy traffic should be cached rather than hammered through the proxy.
