"""
Script to test get_total_files and contract calls on Sepolia
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.blockchain_service import get_blockchain_service

def check_contract():
    bc = get_blockchain_service()
    bc.initialize()
    if not bc.is_ready:
        print("[FAIL] Blockchain service not ready:", bc.initialization_error)
        return

    try:
        total = bc.get_total_files()
        print(f"[OK] Total files in smart contract: {total}")
        if total > 0:
            last_file = bc.get_file_from_blockchain(total - 1)
            print("Last file on blockchain:", last_file)
    except Exception as e:
        print(f"[FAIL] Contract call error: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    check_contract()
