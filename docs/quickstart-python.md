# Quickstart: Python Agent

Build a Python agent that pays FB for API calls on the MoonYetis x402 gateway. This example uses the RNG endpoint.

## Prerequisites

- Python 3.8+
- A Fractal Bitcoin wallet with FB balance
- `bitcoinrpc` or `bitcoin-cli` access for broadcasting transactions

## Option A: Using the x402 SDK (recommended)

```bash
pip install os-x402
```

```python
from x402 import PayAndFetch

# Initialize the client with your wallet
client = PayAndFetch(
    facilitator_url="https://api.moonyetis.com",
    rpc_host="your_node_ip",
    rpc_port=8332,
    rpc_user="your_user",
    rpc_password="your_pass",
    wallet_name="your_wallet"
)

# Call RNG — the SDK handles 402 → pay → retry automatically
result = client.get("/rng/v1/rng", params={"min": 1, "max": 100})

print(f"Random number: {result['random']}")
print(f"Block: {result['block']}")
print(f"Verify: {result['verify_url']}")
```

The SDK handles the full x402 flow automatically:
1. Sends request
2. Receives 402
3. Constructs and broadcasts FB payment
4. Retries with payment proof
5. Returns the result

## Option B: Manual Flow

If you want to understand exactly how x402 works, here's the full manual flow:

```python
import requests
import json
import hashlib
import base64
from urllib.request import Request, urlopen

API_URL = "https://api.moonyetis.com"
RPC_HOST = "your_node_ip"
RPC_PORT = "8332"
RPC_USER = "your_user"
RPC_PASS = "your_pass"


def rpc_call(method, params=None):
    """Call your Fractal node"""
    payload = json.dumps({
        "jsonrpc": "1.0",
        "id": "agent",
        "method": method,
        "params": params or []
    }).encode()
    req = Request(f"http://{RPC_HOST}:{RPC_PORT}", data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f'{RPC_USER}:{RPC_PASS}'.encode()).decode()}"
    })
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["result"]


def pay_for_call(url, amount_sats):
    """
    Step 1: Request without payment → get 402
    Step 2: Pay FB to the address
    Step 3: Return payment proof (nonce + txid)
    """
    # Step 1: Get payment requirements
    resp = requests.get(url)
    if resp.status_code != 402:
        raise Exception(f"Expected 402, got {resp.status_code}")

    payment_data = resp.json()
    payment_req = payment_data["accepts"][0]
    pay_to_address = payment_req["payTo"]["address"]

    print(f"Payment required: {payment_data['price']}")
    print(f"Pay to: {pay_to_address}")

    # Step 2: Pay FB using your node wallet
    txid = rpc_call("sendtoaddress", [
        pay_to_address,
        amount_sats / 100000,  # Convert sats to FB
        "x402 payment",
        "",
        False,  # subtractfeefromamount
        True,   # replaceable
        False,  # conf_target
        "UNSET" # estimate_mode
    ])

    print(f"Payment sent: {txid}")

    # Wait for confirmation (simplified — in production, poll for 1 conf)
    import time
    print("Waiting for confirmation...")
    time.sleep(30)  # ~1 Fractal block

    # Step 3: Return payment proof
    # The nonce comes from the 402 response resource field
    nonce = payment_req.get("resource", url)
    return nonce, txid


def call_rng(min_val=1, max_val=100):
    """Call the RNG endpoint with payment"""
    url = f"{API_URL}/rng/v1/rng?min={min_val}&max={max_val}"

    # Get payment proof
    nonce, txid = pay_for_call(url, 50000)  # 0.5 FB in sats

    # Retry with payment proof
    resp = requests.get(url, headers={
        "X-PAYMENT-NONCE": nonce,
        "X-PAYMENT-TXID": txid
    })

    if resp.status_code == 200:
        result = resp.json()
        print(f"\n🎲 Random number: {result['random']}")
        print(f"📦 Block: {result['block']}")
        print(f"🔗 Verify: {result['verify_url']}")
        return result
    else:
        print(f"Error: {resp.json()}")
        return None


if __name__ == "__main__":
    print("=== MoonYetis x402 RNG Agent ===\n")
    result = call_rng(1, 100)
```

## Running the Agent

```bash
python agent.py
```

Expected output:

```
=== MoonYetis x402 RNG Agent ===

Payment required: 0.50 FB (50000 sats)
Pay to: bc1q...
Payment sent: 2d4e774e5a3b...
Waiting for confirmation...

🎲 Random number: 42
📦 Block: 1934516
🔗 Verify: https://mempool.fractalbitcoin.io/block/1934516
```

## Using Other Endpoints

```python
# Balance check
url = f"{API_URL}/balance/v1/balance/bc1qxy2kg3g6m..."
nonce, txid = pay_for_call(url, 10000)  # 0.1 FB
resp = requests.get(url, headers={
    "X-PAYMENT-NONCE": nonce,
    "X-PAYMENT-TXID": txid
})

# Timestamp
import hashlib
data = hashlib.sha256(b"my important document").hexdigest()
url = f"{API_URL}/timestamp/v1/timestamp"
# POST with payment — see API reference for details
```

## Next Steps

- Read the [API Reference](./api-reference.md) for all endpoints
- Understand [How x402 Works](./how-x402-works.md)
- Check the [x402 SDK source](https://github.com/thelonelybit/os-x402) for advanced usage
