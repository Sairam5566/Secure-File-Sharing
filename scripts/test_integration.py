
import sys
import os

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.blockchain_service import get_blockchain_service

def test_integration():
    print("Testing Blockchain Integration...")
    
    bc_service = get_blockchain_service()
    if not bc_service.is_ready:
        print("Blockchain service not available. Skipping test.")
        return
    
    file_hash = "QmTestHash123456789"
    file_name = "integration_test.txt"
    
    try:
        result = bc_service.upload_file_to_blockchain(file_hash, file_name)
        print(f"Success! Transaction Hash: {result.tx_hash}")
        print(f"Block Number: {result.block_number}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_integration()
