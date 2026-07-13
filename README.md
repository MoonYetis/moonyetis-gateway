# 🌙 MoonYetis x402 Gateway

> **The first commercial x402 API gateway on Fractal Bitcoin.**
> Pay-per-call data endpoints for autonomous AI agents — settled in FB, no accounts, no API keys.

## What is this?

MoonYetis x402 Gateway is a production deployment of pay-per-call API endpoints on Fractal Bitcoin. AI agents pay FB (Fractal Bitcoin) for each API call using the [x402 protocol](https://github.com/thelonelybit/os-x402) — no registration, no credit cards, no API key management.

```
Agent → GET /rng/v1/rng → 402 Payment Required (0.5 FB)
Agent → Pays FB on-chain → retries with txid
Agent → 200 OK { random: 42, block: 1934516, hash: "0x..." }
```

## Live Endpoints

All endpoints are live and operational at `api.moonyetis.com`:

| Service | Endpoint | Price | Description |
|---------|----------|-------|-------------|
| 🎲 **RNG** | `GET /rng/v1/rng?min=1&max=100` | 0.5 FB | Verifiable random number from Fractal block hash |
| 💰 **Balance** | `GET /balance/v1/balance/{address}` | 0.1 FB | On-chain balance of any Fractal address |
| ⏱️ **Timestamp** | `POST /timestamp/v1/timestamp` | 2.0 FB | Permanent notarization via OP_RETURN |

- **Gateway:** https://api.moonyetis.com
- **Dashboard:** https://panel.moonyetis.com
- **Health:** https://api.moonyetis.com/health

## Architecture

```
AI Agents (internet)
       │
       ▼
┌──────────────────────────────────┐
│  VPS (Nginx + SSL)               │
│  ├── x402 Facilitator (:4040)    │  ← Payment verification
│  ├── RNG Server (:4055)          │  ← Our code
│  ├── Balance Server (:4056)      │  ← Our code
│  ├── Timestamp Server (:4057)    │  ← Our code
│  └── PostgreSQL                  │
└──────────┬───────────────────────┘
           │ Tailscale (encrypted)
┌──────────▼───────────────────────┐
│  Fractal Full Node (local)       │
│  RPC :8332 · txindex · wallet    │  ← Data source + payment verifier
└──────────────────────────────────┘
```

**Key design decision:** We replaced the default UniSat API payment verifier with our own Fractal node RPC via Tailscale. Zero external dependencies, zero rate limits, sub-100ms verification.

## How x402 works

The x402 protocol is an open HTTP standard for pay-per-request:

1. **Request** — Agent calls a paid endpoint (no auth needed)
2. **402** — Server responds with `402 Payment Required` + FB address + price
3. **Pay** — Agent broadcasts a FB transaction to the address
4. **200** — Server verifies payment on-chain and serves the result

No accounts. No API keys. No checkout flows. Just pay-per-call.

## What's in this repo

This repo contains the **endpoint servers** we built — the data services that sit behind the x402 payment layer:

```
endpoints/
├── rng-server.py         # Verifiable RNG from block hashes
├── balance-server.py     # On-chain balance checker
└── timestamp-server.py   # OP_RETURN notarization service
```

Each endpoint:
- Queries a Fractal full node via JSON-RPC
- Integrates with the x402 facilitator for payment enforcement
- Runs as a standalone Python HTTP server managed by PM2

The **x402 facilitator** (payment layer) is a separate component from [thelonelybit/os-x402](https://github.com/thelonelybit/os-x402). We did not write it — we deploy and operate it.

## Quick start

### Prerequisites

- A Fractal Bitcoin full node with RPC enabled and `txindex=1`
- [Tailscale](https://tailscale.com) connecting your VPS and node
- A registered x402 facilitator (see [x402 docs](https://github.com/thelonelybit/os-x402))

### Deploy endpoints

```bash
# Clone
git clone https://github.com/MoonYetis/moonyetis-gateway.git
cd moonyetis-gateway

# Configure
cp .env.example .env
# Edit .env with your RPC credentials and API keys

# Start with PM2
pm2 start ecosystem.config.js
pm2 save

# Test (without payment — expect 402)
curl http://localhost:4055/v1/rng?min=1&max=100
```

## Payment flow example (RNG)

```bash
# 1. Request without payment → 402
curl https://api.moonyetis.com/rng/v1/rng?min=1&max=100
# → 402 { "price": "0.50 FB (50000 sats)", "accepts": [...] }

# 2. Agent pays FB to the address in the 402 response
# 3. Retry with payment headers
curl https://api.moonyetis.com/rng/v1/rng?min=1&max=100 \
  -H "X-PAYMENT-NONCE: <nonce>" \
  -H "X-PAYMENT-TXID: <txid>"
# → 200 { "random": 42, "block": 1934516, "block_hash": "0x...", "verify_url": "..." }
```

## Credits & Attribution

This project builds on the **x402 protocol** created by **[The Lonely Bit](https://thelonelybit.org)** (MIT License).

| Component | Author | License |
|-----------|--------|---------|
| x402 facilitator + SDK | [The Lonely Bit](https://github.com/thelonelybit/os-x402) | MIT |
| Data endpoints (RNG, Balance, Timestamp) | **MoonYetis** | MIT |
| Node RPC adapter (Tailscale) | **MoonYetis** | MIT |
| Deployment configs (PM2, Nginx, Docker) | **MoonYetis** | MIT |

We did not create the x402 protocol. We are the **first to operate it as a commercial API gateway** on Fractal Bitcoin, with our own data endpoints and node RPC infrastructure.

## License

MIT — see [LICENSE](LICENSE)

## Links

- **Live API:** https://api.moonyetis.com
- **Dashboard:** https://panel.moonyetis.com
- **x402 Protocol:** https://github.com/thelonelybit/os-x402
- **Fractal Bitcoin:** https://fractalbitcoin.io
