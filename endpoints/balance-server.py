#!/usr/bin/env python3
"""
MoonYetis x402 Balance Checker — On-chain balance lookup
Query the balance of any Fractal Bitcoin address.
Each call costs {BALANCE_PRICE_SATS} sats via x402.

Endpoint: GET /v1/balance/{address}
Response: { address, balance_fb, balance_sats, utxo_count, confirmed }

Copyright (c) 2026 MoonYetis (moonyetis.com)
Built on the x402.fb protocol (MIT) by The Lonely Bit
"""
import json, os, base64, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import urlparse

RPC_HOST = os.environ.get("FB_RPC_HOST", "100.90.169.23")
RPC_PORT = os.environ.get("FB_RPC_PORT", "8332")
RPC_USER = os.environ.get("FB_RPC_USER", "YOUR_RPC_USER")
RPC_PASS = os.environ.get("FB_RPC_PASS", "YOUR_RPC_PASS")
PORT = int(os.environ.get("BALANCE_PORT", "4056"))
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://127.0.0.1:4040")
SERVICE_API_KEY = os.environ.get("BALANCE_SERVICE_KEY", "YOUR_SERVICE_API_KEY")
PRICE_SATS = int(os.environ.get("BALANCE_PRICE_SATS", "10000"))  # 0.1 FB


def rpc_call(method, params=None):
    payload = json.dumps({"jsonrpc": "1.0", "id": "bal", "method": method, "params": params or []}).encode()
    req = Request(f"http://{RPC_HOST}:{RPC_PORT}", data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f'{RPC_USER}:{RPC_PASS}'.encode()).decode()}"
    })
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["result"]


def facilitator_post(path, body):
    payload = json.dumps(body).encode()
    req = Request(f"{FACILITATOR_URL}{path}", data=payload, headers={
        "Content-Type": "application/json",
        "x-api-key": SERVICE_API_KEY
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def get_balance(address):
    """Query UTXOs of an address via scantxoutset"""
    result = rpc_call("scantsxoutset", [{"desc": [f"addr({address})"]}])
    total_sats = 0
    utxo_count = 0
    if result and result.get("unspents"):
        utxo_count = len(result["unspents"])
        total_sats = sum(u.get("satoshi", 0) for u in result["unspents"])
    return {
        "address": address,
        "balance_fb": total_sats / 100000,
        "balance_sats": total_sats,
        "utxo_count": utxo_count,
        "block_height": rpc_call("getblockcount"),
        "timestamp": int(time.time())
    }


class BalanceHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "moonyetis-balance", "block": rpc_call("getblockcount"), "price_sats": PRICE_SATS})
            return

        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")

        if len(parts) < 2 or parts[0] != "v1" or parts[1] != "balance":
            self._send_json(404, {"error": "not found", "usage": "/v1/balance/{address}"})
            return

        if len(parts) < 3 or not parts[2]:
            self._send_json(400, {"error": "address required", "usage": "/v1/balance/{address}"})
            return

        address = parts[2]

        # === x402 PAYMENT FLOW ===
        payment_nonce = self.headers.get("X-PAYMENT-NONCE", "")
        payment_txid = self.headers.get("X-PAYMENT-TXID", "")

        if not payment_nonce or not payment_txid:
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

        try:
            result = facilitator_post("/v1/verify", {"nonce": payment_nonce, "txid": payment_txid})
            if not result.get("ok"):
                self._send_json(402, {"error": "payment invalid", "status": result.get("status")})
                return

            balance = get_balance(address)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-PAYMENT-CONFIRMED", payment_txid)
            self.end_headers()
            self.wfile.write(json.dumps(balance, indent=2).encode())
        except Exception as e:
            self._send_json(500, {"error": f"verify error: {str(e)}"})

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")


if __name__ == "__main__":
    block = rpc_call("getblockcount")
    print(f"💰 MoonYetis x402 Balance Checker starting...")
    print(f"   Fractal node: {RPC_HOST}:{RPC_PORT} (block {block:,})")
    print(f"   Endpoint: http://0.0.0.0:{PORT}/v1/balance/{{address}}")
    print(f"   Price: {PRICE_SATS} sats ({PRICE_SATS / 100000:.2f} FB)")
    server = HTTPServer(("0.0.0.0", PORT), BalanceHandler)
    server.serve_forever()
