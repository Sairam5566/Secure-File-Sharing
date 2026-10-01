
import sys
import os

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.blockchain_service import get_blockchain_service

def test_get_file():
    print("Testing get_file_from_blockchain...")
    
    bc_service = get_blockchain_service()
    if not bc_service.is_ready:
        print("Blockchain service not available. Skipping test.")
        return
    
    # Try to get the first file (index 0)
    file_data = bc_service.get_file_from_blockchain(0)
    
    if file_data:
        print("Success! File data retrieved:")
        print(f"File Hash: {file_data['file_hash']}")
        print(f"File Name: {file_data['file_name']}")
        print(f"Uploader: {file_data['uploader']}")
        print(f"Timestamp: {file_data['timestamp']}")
    else:
        print("Failed to retrieve file. Is the blockchain empty?")

if __name__ == "__main__":
    test_get_file()
