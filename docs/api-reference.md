# API Reference

Complete specification of all MoonYetis x402 endpoints.

## Base URL

```
https://api.moonyetis.com
```

---

## 🎲 RNG — Verifiable Random Number

Generates a random number derived from the latest Fractal Bitcoin block hash. Every result is provably tied to a specific block — anyone can verify the randomness.

### Request

```http
GET /rng/v1/rng?min=1&max=100
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `min` | integer | No | 1 | Minimum value (inclusive) |
| `max` | integer | No | 100 | Maximum value (inclusive) |

**Constraints:** `min >= 0`, `max <= 1000000000`, `min < max`

### Response (200 OK)

```json
{
  "random": 42,
  "min": 1,
  "max": 100,
  "block": 1934516,
  "block_hash": "000000000000000000022ed8c5d8a...",
  "timestamp": 1720892400,
  "verify_url": "https://mempool.fractalbitcoin.io/block/1934516"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `random` | integer | Generated random number |
| `min` | integer | Minimum bound used |
| `max` | integer | Maximum bound used |
| `block` | integer | Fractal block height used for entropy |
| `block_hash` | string | SHA256 hash of the block |
| `timestamp` | integer | Unix timestamp of response |
| `verify_url` | string | Link to verify the block |

### How It Works

The RNG takes the latest block hash and nonce as entropy:

```
entropy = block_hash + str(nonce)
hash_hex = SHA256(entropy)
random = int(hash_hex[:16], 16) % (max - min + 1) + min
```

This means the random number is **deterministic and verifiable** — anyone can reproduce it given the same block hash.

### Price

**0.5 FB (50,000 sats)** per call.

---

## 💰 Balance — On-Chain Address Lookup

Queries the real UTXO-set balance of any Fractal Bitcoin address using the full node's `scantxoutset`. No third-party API — direct from the node.

### Request

```http
GET /balance/v1/balance/bc1qxy2kg3g6m...
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `address` | string | Yes | Any valid Fractal Bitcoin address |

Supports SegWit (bc1q), Taproot (bc1p), and Legacy (1...) addresses.

### Response (200 OK)

```json
{
  "address": "bc1qxy2kg3g6m...",
  "balance_fb": 11.8,
  "balance_sats": 1180000,
  "utxo_count": 3,
  "block_height": 1934516,
  "timestamp": 1720892400
}
 |
{
  "address": "string",
  "balance_fb": "number",
  "balance_sats": "integer",
  "utxo_count": "integer",
  "block_height": "integer",
  "timestamp": "integer"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | The queried address |
| `balance_fb** | float | Balance in FB (1 FB = 100,000 sats) |
| `balance_sats` | integer | Balance in sats |
| `utxo_count` | integer | Number of unspent outputs |
| `block_height` | integer | Current chain tip |
| `timestamp` | integer | Unix timestamp |

### How It Works

The endpoint uses Bitcoin Core's `scantxoutset` RPC method to scan the UTXO set for all outputs belonging to the address. This is a full-node operation — no indexer dependency.

### Price

**0.1 FB (10,000 sats)** per call.

---

## ⏱️ Timestamp — Permanent Notarization

Inscribes a SHA-256 hash of your data onto Fractal Bitcoin via OP_RETURN. Creates a permanent, immutable proof of existence.

### Request

```http
POST /timestamp/v1/timestamp
Content-Type: application/json

{
  "data": "any text, hash, or data to notarize",
  "label": "optional human-readable label"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | Yes | Text or hash to notarize (will be SHA-256 hashed) |
| `label` | string | No | Human-readable label for your reference |

### Response (200 OK)

```json
{
  "status": "timestamped",
  "txid": "2d4e774e5a3b...",
  "data_hash": "a3f5b8c1...",
  "label": "contract-signing-2026",
  "block_height": 1934516,
  "timestamp": 1720892400,
  "verify_url": "https://mempool.fractalbitcoin.io/tx/2d4e774e...",
  "note": "Hash permanently inscribed on Fractal Bitcoin via OP_RETURN"
}
```

| Field | Type | Description |
|-------|------|-------------|---|
| `status` | string | "timestamped" on success |
| `txid` | string | Fractal transaction ID |
| `data_hash` | string | SHA-256 hash of the input data |
| `label` | string | Your label (if provided) |
| `block_height` | integer | Block when inscribed |
| `timestamp` | integer | Unix timestamp |
| `verify_url` | string | Link to verify on explorer |

### How It Works

1. Server computes `SHA-256(data)` → `data_hash`
2. Creates a raw transaction with `OP_RETURN` containing `data_hash[:64]`
3. Signs with node wallet (`fractal_main`)
4. Broadcasts to Fractal mainnet
5. Returns the txid

The hash is now permanently embedded in the blockchain. Anyone with the original data can verify it existed at this point in time by recomputing the hash.

### Price

**2.0 FB (200,000 sats)** per call.

---

## Error Responses

All endpoints return standard HTTP status codes:

| Code | Meaning | When |
|------|---------|------|
| 200 | OK | Payment verified, data returned |
| 400 | Bad Request | Invalid parameters |
| 402 | Payment Required | No payment or invalid payment |
| 404 | Not Found | Wrong endpoint path |
| 500 | Internal Error | Server-side failure |

### 402 Payment Required (without payment)

```json
{
  "x402Version": 1,
  "error": "payment required",
  "accepts": [{
    "scheme": "type_0",
    "network": "fractal-mainnet",
    "maxAmountRequired": 50000,
    "resource": "/rng/v1/rng?min=1&max=100",
    "description": "...",
    "type": "fixed",
    "payTo": {
      "address": "bc1q...",
      "asset": "fb",
      "outputScript": "76a914..."
    }
  }],
  "price": "0.50 FB (50000 sats)"
}
```

### 402 Payment Invalid (with bad payment)

```json
{
  "error": "payment invalid",
  "status": "not_found"
}
```

### 400 Bad Request

```json
{
  "error": "invalid range"
}
```

---

## Rate Limits

There are no traditional rate limits. Each call requires payment, which serves as natural rate limiting. However, avoid spamming the 402 endpoint without paying — repeated unpaid requests from the same IP may be throttled at the Nginx layer.

## Pricing Summary

| Endpoint | Price (FB) | Price (sats) | Price (USD ≈) |
|---|---|---|---|
| RNG | 0.5 | 50,000 | ~$0.18 |
| Balance | 0.1 | 10,000 | ~$0.04 |
| Timestamp | 2.0 | 200,000 | ~$0.72 |

*USD estimates based on FB ≈ $0.36*

---

## Health Check

```http
GET /health
```

No payment required. Returns server status and current block height.

```json
{
  "ok": true,
  "service": "moonyetis-rng",
  "block": 1934516,
  "price_sats": 50000
}
```
