# How x402 Works

The x402 protocol turns any HTTP endpoint into a pay-per-call service. No API keys, no registration, no credit cards. Agents pay with Fractal Bitcoin (FB) per request.

## The Flow

```
Step 1: REQUEST
───────────────
Agent ──→ GET /rng/v1/rng?min=1&max=100
         (no auth headers, no payment)

Step 2: 402 PAYMENT REQUIRED
────────────────────────────
Server ──→ HTTP 402
         {
           "x402Version": 1,
           "error": "payment required",
           "accepts": [{
             "scheme": "type_0",
             "network": "fractal-mainnet",
             "maxAmountRequired": 50000,
             "resource": "/rng/v1/rng?min=1&max=100",
             "description": "Verifiable RNG from Fractal block hash",
             "type": "fixed",
             "payTo": {
               "address": "bc1q...",
               "asset": "fb",
               "outputScript": "76a914...88ac"
             }
           }],
           "price": "0.50 FB (50000 sats)"
         }

Step 3: PAY
───────────
Agent ──→ Broadcasts FB transaction
         (sends 50000 sats to the payTo address)

         Tx: {
           "txid": "2d4e774e...",
           "vout": 0,
           "value": 50000,
           "address": "bc1q..."
         }

Step 4: RETRY WITH PAYMENT PROOF
────────────────────────────────
Agent ──→ GET /rng/v1/rng?min=1&max=100
         Headers:
           X-PAYMENT-NONCE: <unique-nonce-from-402>
           X-PAYMENT-TXID: 2d4e774e...

Step 5: 200 OK
──────────────
Server ──→ Verifies payment on-chain via Fractal node
         ──→ HTTP 200
         {
           "random": 42,
           "block": 1934516,
           "block_hash": "00000000...",
           "verify_url": "https://mempool.fractalbitcoin.io/block/1934516"
         }
```

## Why This Design?

| Traditional APIs | x402 |
|---|---|
| API key management | No keys needed |
| Monthly subscriptions | Pay only for what you use |
| Credit card required | Pay with FB from any wallet |
| Account registration | No account, no email |
| Rate limits by plan | No rate limits, pay per call |
| Censorship possible | Permissionless, on-chain payments |

## Payment Verification

The gateway verifies payments using its own Fractal full node (not UniSat API). This means:

- **Sub-second verification** — direct node RPC, no external API latency
- **Zero external dependencies** — no rate limits from third parties
- **Non-custodial** — the gateway never holds private keys, it only verifies that payment arrived

## What Happens If Payment Fails?

| Scenario | Server Response |
|---|---|
| No payment headers | 402 with payment requirements |
| Invalid txid | 402 "payment invalid" |
| Insufficient amount | 402 "payment invalid" |
| Payment confirmed | 200 with data |

## Supported Wallets

Any wallet that can:
1. Send FB to a Fractal address
2. Provide the transaction ID (txid)

Tested with: UniSat Wallet, Fractal Core wallet RPC

## Settlement

Payments are **on-chain FB transactions**. The gateway verifies that the transaction is confirmed on Fractal mainnet. Settlement time depends on Fractal block times (~30 seconds).

## Protocol Attribution

The x402 protocol was created by [The Lonely Bit](https://thelonelybit.org). It is open source under the MIT license. See [github.com/thelonelybit/os-x402](https://github.com/thelonelybit/os-x402).

MoonYetis operates the first commercial deployment of this protocol on Fractal Bitcoin, with custom data endpoints powered by a self-hosted full node.
