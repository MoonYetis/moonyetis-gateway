# Quickstart: TypeScript Agent

Build a TypeScript agent that pays FB for API calls on the MoonYetis x402 gateway.

## Prerequisites

- Node.js 18+
- npm or pnpm
- A Fractal Bitcoin wallet with FB balance
- UniSat Wallet (browser) or node RPC access

## Option A: Using the x402 SDK (recommended)

```bash
npm install os-x402
```

```typescript
import { payAndFetch } from "os-x402/sdk";

// The SDK handles 402 → pay → retry automatically
const result = await payAndFetch(
  "https://api.moonyetis.com/rng/v1/rng?min=1&max=100",
  {
    facilitatorUrl: "https://api.moonyetis.com",
    wallet: {
      // Provide wallet signing capability
      // Can be UniSat wallet, RPC, or raw key
    }
  }
);

console.log(`Random: ${result.data.random}`);
console.log(`Block: ${result.data.block}`);
console.log(`Payment txid: ${result.txid}`);
```

## Option B: Manual Flow

```typescript
const API_URL = "https://api.moonyetis.com";

// Your Fractal node RPC credentials
const RPC_CONFIG = {
  host: "your_node_ip",
  port: 8332,
  user: "your_user",
  password: "your_pass",
};

interface PaymentRequirement {
  scheme: string;
  network: string;
  maxAmountRequired: number;
  resource: string;
  description: string;
  type: string;
  payTo: {
    address: string;
    asset: string;
    outputScript: string;
  };
}

interface RngResponse {
  random: number;
  min: number;
  max: number;
  block: number;
  block_hash: string;
  timestamp: number;
  verify_url: string;
}

/**
 * Call a paid endpoint using the x402 protocol.
 * Handles: request → 402 → pay → retry → 200
 */
async function callWithPayment<T>(
  url: string,
  amountSats: number
): Promise<T> {
  // Step 1: Request without payment
  const initialResp = await fetch(url);
  
  if (initialResp.status !== 402) {
    throw new Error(`Expected 402, got ${initialResp.status}`);
  }

  const paymentData = await initialResp.json();
  const requirement: PaymentRequirement = paymentData.accepts[0];
  const payToAddress = requirement.payTo.address;

  console.log(`Payment required: ${paymentData.price}`);
  console.log(`Pay to: ${payToAddress}`);

  // Step 2: Pay FB via your node RPC
  const txid = await sendFbPayment(payToAddress, amountSats);
  console.log(`Payment sent: ${txid}`);

  // Wait for block confirmation (~30s on Fractal)
  console.log("Waiting for confirmation...");
  await sleep(30_000);

  // Step 3: Retry with payment proof
  const nonce = requirement.resource;
  const finalResp = await fetch(url, {
    headers: {
      "X-PAYMENT-NONCE": nonce,
      "X-PAYMENT-TXID": txid,
    },
  });

  if (!finalResp.ok) {
    const error = await finalResp.json();
    throw new Error(`Payment failed: ${JSON.stringify(error)}`);
  }

  return finalResp.json();
}

/**
 * Send FB payment using Bitcoin RPC
 */
async function sendFbPayment(
  address: string,
  amountSats: number
): Promise<string> {
  const amount_fb = amountSats / 100_000; // sats → FB
  
  const auth = Buffer.from(
    `${RPC_CONFIG.user}:${RPC_CONFIG.password}`
  ).toString("base64");

  const resp = await fetch(
    `http://${RPC_CONFIG.host}:${RPC_CONFIG.port}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Basic ${auth}`,
      },
      body: JSON.stringify({
        jsonrpc: "1.0",
        id: "agent",
        method: "sendtoaddress",
        params: [
          address,
          amount_fb,
          "x402 payment",
        ],
      }),
    }
  );

  const data = await resp.json();
  if (data.error) throw new Error(data.error.message);
  return data.result;
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// === Example: Call RNG ===
async function main() {
  console.log("=== MoonYetis x402 RNG Agent ===\n");

  const result = await callWithPayment<RngResponse>(
    `${API_URL}/rng/v1/rng?min=1&max=100`,
    50_000 // 0.5 FB in sats
  );

  console.log(`\n🎲 Random number: ${result.random}`);
  console.log(`📦 Block: ${result.block}`);
  console.log(`🔗 Verify: ${result.verify_url}`);
}

main().catch(console.error);
```

## Running the Agent

```bash
# Install dependencies
npm install os-x402

# Run
npx tsx agent.ts
```

## Using Other Endpoints

```typescript
// Balance check
const balance = await callWithPayment(
  `${API_URL}/balance/v1/balance/bc1qxy2kg3g6m...`,
  10_000 // 0.1 FB
);
console.log(`Balance: ${balance.balance_fb} FB`);

// Timestamp (POST)
// For POST endpoints, adapt the fetch to include method and body
```

## Browser Agent (with UniSat Wallet)

If your agent runs in a browser with UniSat Wallet installed:

```typescript
// UniSat provides a window.unisat object for signing
async function payWithUnisat(
  address: string,
  amountSats: number
): Promise<string> {
  const txid = await (window as any).unisat.sendBitcoin(
    address,
    amountSats
  );
  return txid;
}

// Use the same callWithPayment flow, but pass payWithUnisat
```

## Next Steps

- Read the [API Reference](./api-reference.md) for all endpoints
- Understand [How x402 Works](./how-x402-works.md)
- Check the [x402 SDK source](https://github.com/thelonelybit/os-x402) for the full SDK API
