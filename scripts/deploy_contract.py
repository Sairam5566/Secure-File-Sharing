"""
Deploy FileRegistry.sol to Sepolia using py-solc-x + web3.py.
Reads PRIVATE_KEY and WEB3_PROVIDER_URL from .env.
Does NOT print or log the private key at any point.
Writes CONTRACT_ADDRESS back into .env on success.
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────
load_dotenv(override=True)
PROVIDER_URL  = os.getenv("WEB3_PROVIDER_URL", "")
PRIVATE_KEY   = os.getenv("PRIVATE_KEY", "")
SOL_FILE      = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "contracts", "FileRegistry.sol")
ABI_OUT       = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "app", "abi.json")
ENV_FILE      = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

if not PROVIDER_URL:
    sys.exit("[ERROR] WEB3_PROVIDER_URL not set in .env")
if not PRIVATE_KEY:
    sys.exit("[ERROR] PRIVATE_KEY not set in .env")

# ── Connect ───────────────────────────────────────────────
print(f"Connecting to: {PROVIDER_URL}")
w3 = Web3(Web3.HTTPProvider(PROVIDER_URL, request_kwargs={"timeout": 60}))
if not w3.is_connected():
    sys.exit("[ERROR] Cannot connect to Web3 provider")
print(f"[OK] Connected. Chain ID: {w3.eth.chain_id}  (11155111 = Sepolia)")

# Derive account from key — key never printed
pk = PRIVATE_KEY.strip()
if pk.startswith("0x") or pk.startswith("0X"):
    pk = pk[2:]
account = Account.from_key(pk)
print(f"[OK] Deployer address: {account.address}")
balance_wei = w3.eth.get_balance(account.address)
balance_eth = w3.from_wei(balance_wei, "ether")
print(f"[OK] Deployer balance: {balance_eth:.6f} ETH")
if balance_wei == 0:
    sys.exit("[ERROR] Deployer wallet has 0 ETH — fund it on Sepolia faucet first")

# ── Compile with py-solc-x ────────────────────────────────
print("\nCompiling FileRegistry.sol ...")
try:
    from solcx import compile_source, install_solc, get_installed_solc_versions
    SOLC_VERSION = "0.8.20"
    installed = [str(v) for v in get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        print(f"  Installing solc {SOLC_VERSION} ...")
        install_solc(SOLC_VERSION)
    with open(SOL_FILE, "r") as f:
        source = f.read()
    compiled = compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
    )
    contract_id = "<stdin>:FileRegistry"
    abi       = compiled[contract_id]["abi"]
    bytecode  = compiled[contract_id]["bin"]
    print(f"  Bytecode size: {len(bytecode)//2} bytes")
    print(f"  ABI entries: {len(abi)}")
except Exception as e:
    sys.exit(f"[ERROR] Compilation failed: {e}")

# ── Write ABI ─────────────────────────────────────────────
with open(ABI_OUT, "w") as f:
    json.dump(abi, f, indent=4)
print(f"[OK] ABI written to {ABI_OUT}")

# ── Deploy ────────────────────────────────────────────────
print("\nDeploying contract ...")
contract = w3.eth.contract(abi=abi, bytecode=bytecode)
nonce = w3.eth.get_transaction_count(account.address)

# EIP-1559 fee estimation
latest = w3.eth.get_block("latest")
base_fee = latest.get("baseFeePerGas", 0)
if base_fee:
    max_priority = w3.to_wei(2, "gwei")
    max_fee      = base_fee + max_priority
    tx = contract.constructor().build_transaction({
        "chainId": w3.eth.chain_id,
        "nonce":   nonce,
        "maxPriorityFeePerGas": max_priority,
        "maxFeePerGas":         max_fee,
        "gas": 800000,
    })
else:
    tx = contract.constructor().build_transaction({
        "chainId": w3.eth.chain_id,
        "nonce":   nonce,
        "gasPrice": w3.eth.gas_price,
        "gas": 800000,
    })

signed = w3.eth.account.sign_transaction(tx, pk)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
tx_hash_hex = w3.to_hex(tx_hash)
print(f"[OK] Deploy tx submitted: {tx_hash_hex}")
print("     Waiting for confirmation (up to 180s) ...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
if receipt["status"] != 1:
    sys.exit(f"[ERROR] Deploy transaction REVERTED. Receipt: {dict(receipt)}")

contract_address = receipt["contractAddress"]
print(f"[OK] Deployed successfully!")
print(f"     Contract address : {contract_address}")
print(f"     Block number     : {receipt['blockNumber']}")
print(f"     Gas used         : {receipt['gasUsed']}")

# ── Verify bytecode at address ────────────────────────────
code = w3.eth.get_code(contract_address)
print(f"[OK] get_code length : {len(code)} bytes  (>0 = contract exists)")
if len(code) == 0:
    sys.exit("[ERROR] get_code returned empty — contract was NOT deployed!")

# ── Quick smoke-test ──────────────────────────────────────
deployed = w3.eth.contract(address=contract_address, abi=abi)
total = deployed.functions.getTotalFiles().call()
print(f"[OK] getTotalFiles() = {total}  (should be 0 on fresh deploy)")

# ── Write CONTRACT_ADDRESS into .env ─────────────────────
print(f"\nWriting CONTRACT_ADDRESS={contract_address} to .env ...")
with open(ENV_FILE, "r") as f:
    env_text = f.read()

if "CONTRACT_ADDRESS=" in env_text:
    env_text = re.sub(
        r"^CONTRACT_ADDRESS=.*$",
        f"CONTRACT_ADDRESS={contract_address}",
        env_text,
        flags=re.MULTILINE,
    )
else:
    env_text += f"\nCONTRACT_ADDRESS={contract_address}\n"

with open(ENV_FILE, "w") as f:
    f.write(env_text)
print("[OK] .env updated.")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print(f"  Tx hash          : {tx_hash_hex}")
print(f"  Contract address : {contract_address}")
print(f"  ABI              : {ABI_OUT}")
print("=" * 60)
