"""
Encryption Module
Handles file encryption/decryption and blockchain-ready hashing
Isolated module for Phase 3 TPM integration
"""
import os
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


class EncryptionManager:
    """Manages encryption keys and file encryption/decryption"""
    
    def __init__(self):
        self.key_path = settings.ENCRYPTION_KEY_PATH
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_create_key(self) -> bytes:
        """Load existing encryption key or create a new one"""
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as key_file:
                return key_file.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.key_path) if os.path.dirname(self.key_path) else ".", exist_ok=True)
            # Save key to file
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
            return key
    
    def encrypt_file(self, file_content: bytes) -> bytes:
        """
        Encrypt file content using Fernet (AES-128)
        
        Args:
            file_content: Raw file bytes
            
        Returns:
            Encrypted file bytes
        """
        return self.cipher.encrypt(file_content)
    
    def decrypt_file(self, encrypted_content: bytes) -> bytes:
        """
        Decrypt file content
        
        Args:
            encrypted_content: Encrypted file bytes
            
        Returns:
            Decrypted file bytes
        """
        return self.cipher.decrypt(encrypted_content)
    
    @staticmethod
    def generate_file_hash(file_content: bytes) -> str:
        """
        Generate SHA-256 hash of file content for blockchain anchoring
        This hash will be stored separately and used in Phase 2 for blockchain verification
        
        Args:
            file_content: Raw file bytes (before encryption)
            
        Returns:
            Hexadecimal SHA-256 hash string
        """
        sha256_hash = hashlib.sha256()
        sha256_hash.update(file_content)
        return sha256_hash.hexdigest()


# Global encryption manager instance
encryption_manager = EncryptionManager()
