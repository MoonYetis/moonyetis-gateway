# Authentication & Payments

## Overview

The MoonYetis x402 gateway uses **no authentication**. No API keys, no bearer tokens, no sessions. Instead, every call requires a **micro-payment in Fractal Bitcoin (FB)**.

## The Payment Header Flow

```
First request (no payment):
  GET /rng/v1/rng?min=1&max=100
  → 402 Payment Required
  → Response includes payment address and amount

Second request (with payment):
  GET /rng/v1/rng?min=1&max=100
  X-PAYMENT-NONCE: <resource-path-or-nonce>
  X-PAYMENT-TXID: <txid-of-your-payment>
  → 200 OK
```

## Payment Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-PAYMENT-NONCE` | Yes | Unique identifier for this payment (from the 402 response `resource` field) |
| `X-PAYMENT-TXID` | Yes | Transaction ID of your FB payment to the address provided |

## Payment Process

### 1. Receive Payment Address

When you get a 402 response, it includes a `payTo` object:

```json
{
  "payTo": {
    "address": "bc1qxy2kg3g6myxw...",
    "asset": "fb",
    "outputScript": "76a914..."
  }
}
```

### 2. Send FB Payment

Send the exact amount (in sats) to the provided address. You can use:

- **UniSat Wallet** (browser extension)
- **Bitcoin Core RPC** (`sendtoaddress`)
- **Any wallet** that can send FB on Fractal mainnet

**Important:** Send the exact amount in sats. The facilitator verifies exact amounts.

```bash
# Example: send 0.5 FB (50,000 sats = 0.5 FB)
bitcoin-cli -rpcwallet=your_wallet sendtoaddress "bc1q..." 0.5
```

### 3. Wait for Confirmation

The gateway verifies that your payment has been included in a confirmed block. Fractal block time is approximately 30 seconds.

```bash
# Check if your tx is confirmed
bitcoin-cli gettransaction "txid"
```

### 4. Retry Request with Proof

Include the payment headers in your retry:

```bash
curl https://api.moonyetis.com/rng/v1/rng?min=1&max=100 \
  -H "X-PAYMENT-NONCE: /rng/v1/rng?min=1&max=100" \
  -H "X-PAYMENT-TXID: 2d4e774e5a3b..."
```

## Pricing

| Endpoint | Sats | FB | USD (approx) |
|---|---|---|---|
| RNG | 50,000 | 0.5 | ~$0.18 |
| Balance | 10,000 | 0.1 | ~$0.04 |
| Timestamp | 200,000 | 2.0 | ~$0.72 |

## Where Do Payments Go?

Payments are split:

```
Total payment: 0.5 FB
      │
      ├── 90% (0.45 FB) → Merchant address (derived from xpub)
      │                    Goes to MoonYetis operator wallet
      │
      └── 10% (0.05 FB) → Facilitator fee address
                           Also MoonYetis operator wallet
```

**100% of the payment goes to MoonYetis.** The 90/10 split is a protocol accounting mechanism for future multi-merchant scenarios.

## FAQ

### What happens if I send the wrong amount?

The facilitator will reject the payment. You'll get:

```json
{
  "error": "payment invalid",
  "status": "amount_mismatch"
}
```

### Can I reuse a payment for multiple calls?

No. Each payment is single-use. The nonce ensures one payment = one API call.

### What if I pay but the server is down?

The payment is an on-chain FB transaction. It cannot be reversed. The gateway does not offer refunds for failed calls after payment. This is a known trade-off of pay-per-call protocols.

### Do I need a UniSat account?

No. You only need a Fractal Bitcoin address with FB and the ability to broadcast transactions.

### Is this custodial?

No. The gateway never holds your private keys. You sign and broadcast the payment from your own wallet. The gateway only verifies that it received payment.
