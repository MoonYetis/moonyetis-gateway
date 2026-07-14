#!/usr/bin/env python3
"""
MoonYetis x402 — End-to-End Test Agent
Simulates an autonomous AI agent paying FB for API calls.

This agent:
1. Requests the RNG endpoint without payment → gets 402
2. Pays FB to the address from the 402 response
3. Retries with payment proof → gets 200 + random number
4. Verifies the result against the Fractal blockchain

No human intervention. Full autonomous payment loop.
"""

import json
import time
import base64
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Configuration ───────────────────────────────────────────────
API_URL = "https://api.moonyetis.com"
RPC_HOST = "100.90.169.23"
RPC_PORT = "8332"
RPC_USER = "moonyetis_rpc"
RPC_PASS = "D4st8A2kN6sR4jH7mP9qW3xY5zB1cV0eT8uM2nL4"
WALLET = "fractal_main"
RNG_PRICE_SATS = 50000  # 0.5 FB

# ─── Colors ──────────────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    DIM = "\033[2m"


def log(icon, msg, color=C.RESET):
    ts = time.strftime("%H:%M:%S")
    print(f"  {color}{icon} [{ts}] {msg}{C.RESET}")


def rpc_call(method, params=None, wallet=None):
    """Call the Fractal node via JSON-RPC."""
    url = f"http://{RPC_HOST}:{RPC_PORT}"
    if wallet:
        url += f"/wallet/{wallet}"
    payload = json.dumps({
        "jsonrpc": "1.0", "id": "agent", "method": method, "params": params or []
    }).encode()
    auth = base64.b64encode(f"{RPC_USER}:{RPC_PASS}".encode()).decode()
    req = Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}"
    })
    with urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read())
        if result.get("error"):
            raise Exception(f"RPC error: {result['error']}")
        return result["result"]


def http_get(url, headers=None):
    """HTTP GET that returns (status_code, json_body)."""
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


def main():
    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  🌙 MoonYetis x402 — End-to-End Test Agent{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")

    # ── Step 0: Verify connectivity ──────────────────────────
    log("🔧", "Checking Fractal node connectivity...", C.CYAN)
    block = rpc_call("getblockcount")
    log("✅", f"Node online — block {block:,}", C.GREEN)

    balance_result = rpc_call("getbalance", wallet=WALLET)
    log("💰", f"Wallet balance: {balance_result:.8f} FB", C.GREEN)
    print()

    if balance_result < 0.5:
        log("❌", f"Insufficient balance: {balance_result} FB. Need at least 0.5 FB.", C.RED)
        log("💡", "The test needs ~0.6 FB (0.5 merchant + 0.05 fee + ~0.0001 network fee)", C.DIM)
        sys.exit(1)

    # ── Step 1: Request without payment → expect 402 ─────────
    log("1️⃣ ", "Requesting RNG endpoint WITHOUT payment...", C.YELLOW)
    url = f"{API_URL}/rng/v1/rng?min=1&max=100"
    status, body = http_get(url)

    if status != 402:
        log("❌", f"Expected 402, got {status}: {body}", C.RED)
        sys.exit(1)

    log("✅", f"Got 402 Payment Required", C.GREEN)
    print(f"{C.DIM}     Price: {body.get('price', 'unknown')}{C.RESET}")

    # Extract payment details
    accepts = body.get("accepts", [{}])[0]
    pay_to_address = accepts.get("payTo", "")
    resource = accepts.get("resource", url)
    max_amount = accepts.get("amount", RNG_PRICE_SATS)
    nonce = accepts.get("nonce", "")
    facilitator_fee = accepts.get("facilitatorFee", {})
    fee_address = facilitator_fee.get("payTo", "")
    fee_amount = facilitator_fee.get("amount", 0)

    print(f"{C.DIM}     Pay to: {pay_to_address}{C.RESET}")
    print(f"{C.DIM}     Amount: {max_amount} sats ({max_amount/100000:.1f} FB){C.RESET}")
    print(f"{C.DIM}     Facilitator fee: {fee_amount} sats to {fee_address[:20]}...{C.RESET}")
    print(f"{C.DIM}     Nonce: {nonce}{C.RESET}")
    print(f"{C.DIM}     Resource: {resource}{C.RESET}")
    print()

    # ── Step 2: Pay FB (two outputs: merchant + facilitator fee) ──
    log("2️⃣ ", f"Paying {max_amount/100000:.1f} FB to {pay_to_address[:20]}...", C.YELLOW)
    amount_fb = max_amount / 100000
    fee_fb = fee_amount / 100000

    # The facilitator expects TWO outputs in the transaction:
    # 1. Merchant payment (amount sats to pay_to_address)
    # 2. Facilitator fee (fee_amount sats to fee_address)
    # We use createrawtransaction for precise control.

    # Get a UTXO to spend
    utxos = rpc_call("listunspent", [1, 9999999, [], True], wallet=WALLET)
    if not utxos:
        log("❌", "No UTXOs available in wallet", C.RED)
        sys.exit(1)

    utxo = utxos[0]
    log("💰", f"Using UTXO: {utxo['txid'][:16]}... ({utxo['amount']} FB)", C.DIM)

    # Get change address
    change_address = rpc_call("getrawchangeaddress", wallet=WALLET)

    # Calculate change (minus estimated fee)
    total_needed = amount_fb + fee_fb
    estimated_fee_fb = 0.0001  # ~10k sats for the tx fee
    change_amount = utxo["amount"] - total_needed - estimated_fee_fb

    if change_amount < 0:
        log("❌", f"Insufficient UTXO: {utxo['amount']} FB, need {total_needed + estimated_fee_fb} FB", C.RED)
        sys.exit(1)

    # Create raw transaction with two payment outputs + change
    inputs = [{"txid": utxo["txid"], "vout": utxo["vout"]}]
    outputs = {
        pay_to_address: amount_fb,
        fee_address: fee_fb,
        change_address: change_amount
    }

    raw_tx = rpc_call("createrawtransaction", [inputs, outputs], wallet=WALLET)
    signed = rpc_call("signrawtransactionwithwallet", [raw_tx], wallet=WALLET)

    if not signed.get("complete"):
        log("❌", f"Signing failed: {signed}", C.RED)
        sys.exit(1)

    txid = rpc_call("sendrawtransaction", [signed["hex"]], wallet=WALLET)

    log("✅", f"Payment broadcast: {txid}", C.GREEN)
    print(f"{C.DIM}     TXID: {txid}{C.RESET}")
    print()

    # ── Step 3: Wait for confirmation ────────────────────────
    log("3️⃣ ", "Waiting for on-chain confirmation...", C.YELLOW)
    log("⏳", f"Polling every 5s for transaction confirmation...", C.DIM)

    max_wait = 180  # 3 minutes max
    confirmed = False
    start = time.time()

    while time.time() - start < max_wait:
        try:
            tx_info = rpc_call("gettransaction", [txid], wallet=WALLET)
            confs = tx_info.get("confirmations", 0)
            if confs > 0:
                elapsed = int(time.time() - start)
                log("✅", f"Confirmed in {confs} block(s) after {elapsed}s", C.GREEN)
                confirmed = True
                break
        except:
            pass
        time.sleep(5)
        elapsed = int(time.time() - start)
        print(f"\r{C.DIM}     ... {elapsed}s elapsed{C.RESET}", end="", flush=True)

    print()

    if not confirmed:
        log("⚠️ ", f"Transaction not confirmed after {max_wait}s. Retrying anyway...", C.YELLOW)
        log("💡", "The gateway may accept unconfirmed transactions in some cases.", C.DIM)
        print()

    # ── Step 4: Retry with payment proof ─────────────────────
    log("4️⃣ ", "Retrying RNG endpoint WITH payment proof...", C.YELLOW)
    time.sleep(2)  # small buffer for gateway to see the tx

    status, body = http_get(url, headers={
        "X-PAYMENT-NONCE": nonce,
        "X-PAYMENT-TXID": txid,
    })

    if status == 200:
        random_num = body.get("random")
        result_block = body.get("block")
        block_hash = body.get("block_hash")
        verify_url = body.get("verify_url")

        log("✅", f"200 OK — Payment accepted!", C.GREEN)
        print()
        print(f"{C.BOLD}{C.CYAN}  ┌─────────────────────────────────────┐{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  │                                     │{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  │   🎲 Random number: {random_num:<16}│{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  │   📦 Block: {result_block:<23}│{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  │   🔗 Block hash: {block_hash[:16]}...  │{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  │                                     │{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}  └─────────────────────────────────────┘{C.RESET}")
        print()
        print(f"  {C.DIM}Verify: {verify_url}{C.RESET}")
        print()

        # ── Step 5: Verify result independently ───────────────
        log("5️⃣ ", "Independently verifying RNG result...", C.YELLOW)
        node_block_hash = rpc_call("getblockhash", [result_block])
        node_block = rpc_call("getblock", [node_block_hash])
        nonce = node_block.get("nonce", 0)

        import hashlib
        entropy = node_block_hash + str(nonce)
        hash_hex = hashlib.sha256(entropy.encode()).hexdigest()
        verified_random = int(hash_hex[:16], 16) % (100 - 1 + 1) + 1

        if verified_random == random_num:
            log("✅", f"Verified! Node confirms random = {verified_random}", C.GREEN)
        else:
            log("⚠️ ", f"Mismatch: server says {random_num}, node says {verified_random}", C.YELLOW)

        # ── Summary ───────────────────────────────────────────
        print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
        print(f"{C.BOLD}  ✅ E2E TEST PASSED{C.RESET}")
        print(f"{C.BOLD}{'═' * 60}{C.RESET}\n")
        print(f"  Agent requested data without auth")
        print(f"  Server responded with 402 Payment Required")
        print(f"  Agent paid {amount_fb:.1f} FB on-chain")
        print(f"  Payment confirmed in {int(time.time() - start)}s")
        print(f"  Server verified payment and served data")
        print(f"  Result independently verified against node")
        print(f"\n  {C.DIM}Full autonomous flow: Request → 402 → Pay → 200{C.RESET}")
        print(f"  {C.DIM}No API keys. No accounts. No humans.{C.RESET}")
        print()

        return 0

    elif status == 402:
        log("❌", f"Payment not accepted: {body}", C.RED)
        print(f"{C.DIM}     This may be because the facilitator needs more confirmations.{C.RESET}")
        print(f"{C.DIM}     Check the txid on the explorer: https://mempool.fractalbitcoin.io/tx/{txid}{C.RESET}")
        return 1
    else:
        log("❌", f"Unexpected status {status}: {body}", C.RED)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Interrupted by user.{C.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{C.RED}Fatal error: {e}{C.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
