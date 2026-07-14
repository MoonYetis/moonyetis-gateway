# MoonYetis x402 Gateway — Developer Guide

Complete documentation for integrating with the MoonYetis x402 API Gateway on Fractal Bitcoin.

## Table of Contents

- [How x402 Works](./how-x402-works.md) — The payment flow explained
- [API Reference](./api-reference.md) — All endpoints, parameters, and responses
- [Quickstart: Python](./quickstart-python.md) — Build an agent in 5 minutes
- [Quickstart: TypeScript](./quickstart-typescript.md) — Build an agent in 5 minutes
- [Authentication & Payments](./payments.md) — How FB payments work

## Base URL

```
https://api.moonyetis.com
```

## Live Endpoints

| Endpoint | Method | Price | Description |
|----------|--------|-------|-------------|
| `/rng/v1/rng` | GET | 0.5 FB | Verifiable random number from block hash |
| `/balance/v1/balance/{address}` | GET | 0.1 FB | On-chain balance lookup |
| `/timestamp/v1/timestamp` | POST | 2.0 FB | Permanent OP_RETURN notarization |

## Quick Example

```bash
# Try it — no auth needed, you'll get a 402:
curl https://api.moonyetis.com/rng/v1/rng?min=1&max=100

# Response:
# {
#   "x402Version": 1,
#   "error": "payment required",
#   "accepts": [{
#     "scheme": "type_0",
#     "network": "fractal-mainnet",
#     "asset": "fb",
#     "amount": 50000,
#     ...
#   }],
#   "price": "0.50 FB (50000 sats)"
# }
```

## Architecture

```
Your Agent ──→ api.moonyetis.com (VPS + Nginx)
                    │
                    ├── x402 Facilitator (payment verification)
                    ├── Endpoint Server (data)
                    └── Postgres (state)
                          │
                    Tailscale tunnel (encrypted)
                          │
                    Fractal Full Node (RPC)
                    - Block data
                    - UTXO scanning
                    - Transaction verification
                    - OP_RETURN notarization
```

## Requirements for Integration

1. **A Fractal Bitcoin wallet** with FB balance
2. **Ability to broadcast transactions** to Fractal mainnet
3. **The x402 SDK** (optional but recommended): `npm i os-x402`

## Support

- **API Status:** https://api.moonyetis.com/health
- **Dashboard:** https://panel.moonyetis.com
- **GitHub:** https://github.com/MoonYetis/moonyetis-gateway
- **x402 Protocol:** https://github.com/thelonelybit/os-x402
