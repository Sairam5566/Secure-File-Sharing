"""
Script to inspect exact transaction status on Sepolia for tx hash 0x6e14dac57d340033dfee48b227895ef82796d29eb2dc11690e54e82ecfe655ef
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from app.config import settings

def inspect_tx():
    tx_hash = "0x6e14dac57d340033dfee48b227895ef82796d29eb2dc11690e54e82ecfe655ef"
    print(f"Connecting to provider: {settings.WEB3_PROVIDER_URL}")
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
    
    if not w3.is_connected():
        print("[FAIL] Web3 not connected to provider!")
        return

    print(f"[OK] Web3 connected. Checking transaction receipt for: {tx_hash}")
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print("Receipt received:")
        print(f"  Block Number: {receipt.get('blockNumber')}")
        print(f"  Status: {receipt.get('status')} (1 = Success, 0 = Reverted)")
        print(f"  Gas Used: {receipt.get('gasUsed')}")
        print(f"  Contract Address: {receipt.get('contractAddress')}")
        print(f"  Logs: {len(receipt.get('logs', []))}")
    except Exception as e:
        print(f"Receipt error: {type(e).__name__} - {str(e)}")

    try:
        tx = w3.eth.get_transaction(tx_hash)
        print("\nTransaction details:")
        print(f"  From: {tx.get('from')}")
        print(f"  To: {tx.get('to')}")
        print(f"  Nonce: {tx.get('nonce')}")
        print(f"  Value: {tx.get('value')}")
    except Exception as e:
        print(f"Transaction query error: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    inspect_tx()
