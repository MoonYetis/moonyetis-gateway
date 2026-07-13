#!/usr/bin/env python3
"""
MoonYetis x402 RNG Service — Verifiable random number generator
Generates randomness from Fractal Bitcoin block hashes.
Each call costs {RNG_PRICE_SATS} sats via the x402 protocol.

Endpoint: GET /v1/rng?min=1&max=100
No payment → 402 Payment Required
With verified payment → 200 + RNG result

Copyright (c) 2026 MoonYetis (moonyetis.com)
Built on the x402.fb protocol (MIT) by The Lonely Bit
"""
import json, os, hashlib, time, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse, parse_qs

# Configuration — set via environment variables
RPC_HOST = os.environ.get("FB_RPC_HOST", "YOUR_TAILSCALE_IP")
RPC_PORT = os.environ.get("FB_RPC_PORT", "8332")
RPC_USER = os.environ.get("FB_RPC_USER", "YOUR_RPC_USER")
RPC_PASS = os.environ.get("FB_RPC_PASS", "YOUR_RPC_PASS")
PORT = int(os.environ.get("RNG_PORT", "4055"))
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://127.0.0.1:4040")
SERVICE_API_KEY = os.environ.get("RNG_SERVICE_KEY", "YOUR_SERVICE_API_KEY")
PRICE_SATS = int(os.environ.get("RNG_PRICE_SATS", "50000"))  # 0.5 FB = 50,000 sats


def rpc_call(method, params=None):
    """Call Fractal node via JSON-RPC over Tailscale"""
    payload = json.dumps({"jsonrpc": "1.0", "id": "rng", "method": method, "params": params or []}).encode()
    req = Request(f"http://{RPC_HOST}:{RPC_PORT}", data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f'{RPC_USER}:{RPC_PASS}'.encode()).decode()}"
    })
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["result"]


def facilitator_post(path, body):
    """Call x402 facilitator"""
    payload = json.dumps(body).encode()
    req = Request(f"{FACILITATOR_URL}{path}", data=payload, headers={
        "Content-Type": "application/json",
        "x-api-key": SERVICE_API_KEY
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def generate_rng(min_val, max_val):
    """Generate verifiable random number from latest block hash"""
    block_count = rpc_call("getblockcount")
    block_hash = rpc_call("getblockhash", [block_count])
    block = rpc_call("getblock", [block_hash])

    entropy = block_hash + str(block.get("nonce", 0))
    hash_hex = hashlib.sha256(entropy.encode()).hexdigest()
    num = int(hash_hex[:16], 16) % (max_val - min_val + 1) + min_val

    return {
        "random": num,
        "min": min_val,
        "max": max_val,
        "block": block_count,
        "block_hash": block_hash,
        "timestamp": int(time.time()),
        "verify_url": f"https://mempool.fractalbitcoin.io/block/{block_count}"
    }


class RNGHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "moonyetis-rng", "block": rpc_call("getblockcount"), "price_sats": PRICE_SATS})
            return

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path != "/v1/rng":
            self._send_json(404, {"error": "not found"})
            return

        min_val = int(params.get("min", ["1"])[0])
        max_val = int(params.get("max", ["100"])[0])

        if min_val < 0 or max_val > 10**9 or min_val >= max_val:
            self._send_json(400, {"error": "invalid range"})
            return

        # === x402 PAYMENT FLOW ===
        payment_nonce = self.headers.get("X-PAYMENT-NONCE", "")
        payment_txid = self.headers.get("X-PAYMENT-TXID", "")

        if not payment_nonce or not payment_txid:
            # No payment → issue 402 with payment requirements
            try:
                req = facilitator_post("/v1/requirements", {
                    "resource": self.path,
                    "price": PRICE_SATS
                })
                self._send_json(402, {
                    "x402Version": 1,
                    "error": "payment required",
                    "accepts": [req],
                    "price": f"{PRICE_SATS / 100000:.2f} FB ({PRICE_SATS} sats)"
                })
            except Exception as e:
                self._send_json(500, {"error": f"facilitator error: {str(e)}"})
            return

        # With payment → verify via facilitator
        try:
            result = facilitator_post("/v1/verify", {
                "nonce": payment_nonce,
                "txid": payment_txid
            })

            if not result.get("ok"):
                self._send_json(402, {"error": "payment invalid", "status": result.get("status")})
                return

            # Payment confirmed → generate RNG
            rng_result = generate_rng(min_val, max_val)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-PAYMENT-CONFIRMED", payment_txid)
            self.end_headers()
            self.wfile.write(json.dumps(rng_result, indent=2).encode())

        except Exception as e:
            self._send_json(500, {"error": f"verify error: {str(e)}"})

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")


if __name__ == "__main__":
    block = rpc_call("getblockcount")
    print(f"🎲 MoonYetis x402 RNG Service starting...")
    print(f"   Fractal node: {RPC_HOST}:{RPC_PORT} (block {block:,})")
    print(f"   Endpoint: http://0.0.0.0:{PORT}/v1/rng?min=1&max=100")
    print(f"   Price: {PRICE_SATS} sats ({PRICE_SATS / 100000:.2f} FB)")
    print(f"   Facilitator: {FACILITATOR_URL}")
    server = HTTPServer(("0.0.0.0", PORT), RNGHandler)
    server.serve_forever()
