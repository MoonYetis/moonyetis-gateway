#!/usr/bin/env python3
"""
MoonYetis x402 Timestamp — Permanent notarization on Fractal Bitcoin
Inscribes a hash on the Fractal blockchain as proof of existence.
Each call costs {TIMESTAMP_PRICE_SATS} sats via x402.

POST /v1/timestamp
Body: {"data": "hash or text to notarize", "label": "optional"}

Response: { txid, block, confirmations, label, data_hash, timestamp, verify_url }

Copyright (c) 2026 MoonYetis (moonyetis.com)
Built on the x402.fb protocol (MIT) by The Lonely Bit
"""
import json, os, hashlib, time, base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

RPC_HOST = os.environ.get("FB_RPC_HOST", "100.90.169.23")
RPC_PORT = os.environ.get("FB_RPC_PORT", "8332")
RPC_USER = os.environ.get("FB_RPC_USER", "YOUR_RPC_USER")
RPC_PASS = os.environ.get("FB_RPC_PASS", "YOUR_RPC_PASS")
PORT = int(os.environ.get("TIMESTAMP_PORT", "4057"))
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://127.0.0.1:4040")
SERVICE_API_KEY = os.environ.get("TIMESTAMP_SERVICE_KEY", "YOUR_SERVICE_API_KEY")
PRICE_SATS = int(os.environ.get("TIMESTAMP_PRICE_SATS", "200000"))  # 2 FB
TIMESTAMP_WALLET = os.environ.get("TIMESTAMP_WALLET", "fractal_main")


def rpc_call(method, params=None, wallet=None):
    payload = json.dumps({"jsonrpc": "1.0", "id": "ts", "method": method, "params": params or []}).encode()
    req = Request(f"http://{RPC_HOST}:{RPC_PORT}", data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f'{RPC_USER}:{RPC_PASS}'.encode()).decode()}"
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())["result"]


def facilitator_post(path, body):
    payload = json.dumps(body).encode()
    req = Request(f"{FACILITATOR_URL}{path}", data=payload, headers={
        "Content-Type": "application/json",
        "x-api-key": SERVICE_API_KEY
    })
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def create_timestamp(data, label=""):
    """Inscribe a hash on Fractal using OP_RETURN via the node wallet"""
    data_hash = hashlib.sha256(data.encode()).hexdigest()

    try:
        utxos = rpc_call("listunspent", [1, 9999999, [], True, None], wallet=TIMESTAMP_WALLET)

        if not utxos:
            return {"error": "no UTXOs available in timestamp wallet", "data_hash": data_hash}

        utxo = utxos[0]
        change_address = rpc_call("getrawchangeaddress", [], wallet=TIMESTAMP_WALLET)

        inputs = [{"txid": utxo["txid"], "vout": utxo["vout"]}]
        outputs = {"data": data_hash[:64]}
        outputs[change_address] = utxo["amount"] - 0.0001

        raw_tx = rpc_call("createrawtransaction", [inputs, outputs], wallet=TIMESTAMP_WALLET)
        signed = rpc_call("signrawtransactionwithwallet", [raw_tx], wallet=TIMESTAMP_WALLET)

        if not signed.get("complete"):
            return {"error": "signing failed", "details": signed}

        txid = rpc_call("sendrawtransaction", [signed["hex"]], wallet=TIMESTAMP_WALLET)

        return {
            "status": "timestamped",
            "txid": txid,
            "data_hash": data_hash,
            "label": label,
            "block_height": rpc_call("getblockcount"),
            "timestamp": int(time.time()),
            "verify_url": f"https://mempool.fractalbitcoin.io/tx/{txid}",
            "note": "Hash permanently inscribed on Fractal Bitcoin via OP_RETURN"
        }
    except Exception as e:
        return {"error": str(e), "data_hash": data_hash, "label": label}


class TimestampHandler(BaseHTTPRequestHandler):
    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "ok": True,
                "service": "moonyetis-timestamp",
                "block": rpc_call("getblockcount"),
                "price_sats": PRICE_SATS
            })
            return
        self._send_json(200, {
            "service": "moonyetis-timestamp",
            "method": "POST",
            "endpoint": "/v1/timestamp",
            "body_format": {"data": "string (hash, text, or data to notarize)", "label": "string (optional)"},
            "price": f"{PRICE_SATS / 100000:.2f} FB ({PRICE_SATS} sats)"
        })

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()

        try:
            payload = json.loads(body)
        except:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        data = payload.get("data", "")
        label = payload.get("label", "")

        if not data:
            self._send_json(400, {"error": "data field required"})
            return

        # === x402 PAYMENT FLOW ===
        payment_nonce = self.headers.get("X-PAYMENT-NONCE", "")
        payment_txid = self.headers.get("X-PAYMENT-TXID", "")

        if not payment_nonce or not payment_txid:
            try:
                req = facilitator_post("/v1/requirements", {
                    "resource": "/v1/timestamp",
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

            ts_result = create_timestamp(data, label)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-PAYMENT-CONFIRMED", payment_txid)
            self.end_headers()
            self.wfile.write(json.dumps(ts_result, indent=2).encode())
        except Exception as e:
            self._send_json(500, {"error": f"timestamp error: {str(e)}"})

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")


if __name__ == "__main__":
    block = rpc_call("getblockcount")
    print(f"⏱️ MoonYetis x402 Timestamp Service starting...")
    print(f"   Fractal node: {RPC_HOST}:{RPC_PORT} (block {block:,})")
    print(f"   Endpoint: http://0.0.0.0:{PORT}/v1/timestamp")
    print(f"   Price: {PRICE_SATS} sats ({PRICE_SATS / 100000:.2f} FB)")
    server = HTTPServer(("0.0.0.0", PORT), TimestampHandler)
    server.serve_forever()
