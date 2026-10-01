"""
Production-Grade Blockchain Service
Lazy initialization, secure key handling, and graceful degradation
"""
import json
import os
import re
import logging
import time
from typing import Optional, Dict, Any, cast, List
from dataclasses import dataclass
from functools import wraps

from web3 import Web3
from web3.exceptions import Web3RPCError, ContractLogicError
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address
from eth_typing import ChecksumAddress
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BlockchainTransactionResult:
    """Result of a blockchain transaction"""
    tx_hash: str
    block_number: int
    status: str
    gas_used: Optional[int] = None
    confirmations: int = 0


class BlockchainServiceError(Exception):
    """Custom exception for blockchain service errors"""
    def __init__(self, message: str, http_status: int = 500, error_code: str = "BLOCKCHAIN_ERROR"):
        self.message = message
        self.http_status = http_status
        self.error_code = error_code
        super().__init__(self.message)


class BlockchainService:
    """
    Production-grade blockchain service with:
    - Lazy initialization (no startup crashes)
    - Secure key validation
    - Address checksum validation
    - Connection retry logic
    - Graceful degradation
    - Secure logging (no secrets)
    """
    
    def __init__(self):
        self._web3: Optional[Web3] = None
        self._contract = None
        self._account: Optional[LocalAccount] = None
        self._abi: Optional[list] = None
        self._initialized: bool = False
        self._initialization_error: Optional[str] = None
        self._contract_address: Optional[ChecksumAddress] = None
        
    @property
    def is_enabled(self) -> bool:
        """Check if blockchain is enabled in configuration"""
        return settings.BLOCKCHAIN_ENABLED
    
    @property
    def enabled(self) -> bool:
        """Alias for is_enabled to match health check usage"""
        return self.is_enabled

    @property
    def w3(self) -> Optional[Web3]:
        """Expose Web3 instance for health checks"""
        return self._web3

    @property
    def contract(self):
        """Expose Contract instance for health checks"""
        return self._contract
    
    @property
    def is_ready(self) -> bool:
        """Check if blockchain service is initialized and ready"""
        return self._initialized and self._web3 is not None
    
    @property
    def initialization_error(self) -> Optional[str]:
        """Get initialization error message if any"""
        return self._initialization_error
    
    def _validate_private_key(self, key: str) -> str:
        """Validate and clean private key format. Returns cleaned key (0x removed)."""
        if not key or not isinstance(key, str):
            raise ValueError("Private key is required")
        
        key = key.strip()
        
        # Remove 0x prefix if present
        if key.startswith("0x") or key.startswith("0X"):
            key = key[2:]
        
        # Must be exactly 64 hex characters
        if len(key) != 64:
            raise ValueError(f"Private key must be 64 hex characters (got {len(key)})")
        
        # Must be valid hex
        if not re.match(r"^[0-9a-fA-F]+$", key):
            raise ValueError("Private key contains non-hexadecimal characters")
        
        return key
    
    def _validate_contract_address(self, address: str) -> ChecksumAddress:
        """Validate and checksum contract address. Returns checksum address."""
        if not address or not isinstance(address, str):
            raise ValueError("Contract address is required")
        
        address = address.strip()
        
        # Must be 42 characters (0x + 40 hex)
        if len(address) != 42:
            raise ValueError(f"Contract address must be 42 characters (got {len(address)})")
        
        if not address.startswith("0x"):
            raise ValueError("Contract address must start with '0x'")
        
        if not re.match(r"^0x[0-9a-fA-F]{40}$", address):
            raise ValueError("Contract address must be hex format (0x + 40 hex characters)")
        
        # Convert to checksum address
        try:
            return to_checksum_address(address)
        except Exception as e:
            raise ValueError(f"Invalid Ethereum address: {str(e)}")
    
    def _load_abi(self) -> List[Dict[str, Any]]:
        """Load contract ABI from file"""
        try:
            abi_path = os.path.join(os.path.dirname(__file__), "abi.json")
            with open(abi_path, "r", encoding="utf-8") as f:
                return cast(List[Dict[str, Any]], json.load(f))
        except FileNotFoundError:
            raise BlockchainServiceError(
                "Contract ABI file not found (abi.json)",
                error_code="ABI_NOT_FOUND"
            )
        except json.JSONDecodeError as e:
            raise BlockchainServiceError(
                f"Invalid ABI JSON format: {str(e)}",
                error_code="ABI_INVALID"
            )
    
    def _connect_with_retry(self, provider_url: str, max_retries: int = 3, delay: float = 1.0) -> Web3:
        """Connect to blockchain node with retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                web3 = Web3(Web3.HTTPProvider(provider_url, request_kwargs={"timeout": 30}))
                
                # Test connection
                if web3.is_connected():
                    logger.info(f"Connected to blockchain node at {provider_url}")
                    return web3
                else:
                    raise ConnectionError("Web3 reports not connected")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Blockchain connection attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
        
        raise BlockchainServiceError(
            f"Failed to connect to blockchain after {max_retries} attempts: {str(last_error)}",
            http_status=503,
            error_code="CONNECTION_FAILED"
        )
    
    def initialize(self) -> bool:
        """
        Initialize blockchain connection lazily.
        Returns True if successful, False otherwise.
        Does NOT raise exceptions - safe for startup.
        """
        if self._initialized:
            return self._web3 is not None
        
        # Check if blockchain is enabled
        if not settings.BLOCKCHAIN_ENABLED:
            logger.info("Blockchain integration disabled (BLOCKCHAIN_ENABLED=false)")
            self._initialized = True
            return False
        
        # Check required settings
        if not settings.PRIVATE_KEY or not settings.CONTRACT_ADDRESS:
            logger.warning("Blockchain enabled but missing PRIVATE_KEY or CONTRACT_ADDRESS")
            self._initialization_error = "Missing blockchain configuration (PRIVATE_KEY or CONTRACT_ADDRESS)"
            self._initialized = True
            return False
        
        try:
            # Validate private key (sanitized logging)
            cleaned_key = self._validate_private_key(settings.PRIVATE_KEY)
            logger.info("Private key validated (format: 64 hex chars)")
            
            # Validate contract address
            self._contract_address = self._validate_contract_address(settings.CONTRACT_ADDRESS)
            logger.info(f"Contract address validated: {self._contract_address[:10]}...{self._contract_address[-8:]}")
            
            # Connect to blockchain with retry
            self._web3 = self._connect_with_retry(settings.WEB3_PROVIDER_URL)
            
            # Load ABI
            self._abi = self._load_abi()
            
            # Create account from private key (secure - key never logged)
            self._account = Account.from_key(cleaned_key)
            logger.info(f"Blockchain account loaded: {self._account.address[:10]}...{self._account.address[-8:]}")
            
            # Initialize contract
            self._contract = self._web3.eth.contract(address=self._contract_address, abi=self._abi)
            
            # Item 3: verify contract bytecode exists — if empty, DISABLE anchoring.
            try:
                code = self._web3.eth.get_code(self._contract_address)
                code_bytes = bytes(code) if not isinstance(code, bytes) else code
                if len(code_bytes) == 0:
                    self._initialization_error = (
                        f"No contract bytecode at {self._contract_address}. "
                        "Blockchain anchoring DISABLED. Deploy the contract first."
                    )
                    logger.warning(
                        f"[BLOCKCHAIN DISABLED] No contract code at "
                        f"{self._contract_address[:10]}...{self._contract_address[-8:]}. "
                        "File anchoring will be skipped until a valid contract is deployed."
                    )
                    self._web3 = None   # Mark as not ready
                    self._initialized = True
                    return False
            except Exception as e:
                logger.warning(f"Could not verify contract code: {str(e)}")

            self._initialized = True
            logger.info("Blockchain service initialized successfully")
            return True
            
        except BlockchainServiceError as e:
            self._initialization_error = e.message
            logger.error(f"Blockchain initialization failed: {e.message}")
            self._initialized = True
            return False
            
        except Exception as e:
            self._initialization_error = f"Unexpected error: {str(e)}"
            logger.error(f"Blockchain initialization failed: {str(e)}")
            self._initialized = True
            return False
    
    def _require_initialized(self):
        """Ensure blockchain is initialized before operations"""
        if not self._initialized:
            self.initialize()
        
        if not self.is_ready:
            error_msg = self._initialization_error or "Blockchain service not available"
            raise BlockchainServiceError(
                error_msg,
                http_status=503,
                error_code="SERVICE_UNAVAILABLE"
            )
        assert self._web3 is not None
        assert self._contract is not None
        assert self._account is not None
        assert self._contract_address is not None
    
    def upload_file_to_blockchain(
        self, 
        file_hash: str, 
        file_name: str,
        timeout: int = 120
    ) -> BlockchainTransactionResult:
        """
        Store file hash on blockchain with full error handling.
        
        Args:
            file_hash: SHA-256 hash of file (64 hex chars)
            file_name: Original file name
            timeout: Max seconds to wait for confirmation
            
        Returns:
            BlockchainTransactionResult with transaction details
            
        Raises:
            BlockchainServiceError: On blockchain errors
            HTTPException: For API responses
        """
        self._require_initialized()
        
        # Type checker hints
        assert self._web3 is not None
        assert self._contract is not None
        assert self._account is not None
        
        try:
            # Validate inputs
            if not file_hash or len(file_hash) != 64:
                raise BlockchainServiceError(
                    "Invalid file hash (must be 64 hex chars)",
                    http_status=400,
                    error_code="INVALID_HASH"
                )
            
            # Truncate filename to fit in blockchain constraints
            file_name_clean = file_name[:255] if len(file_name) > 255 else file_name
            
            # Get nonce
            nonce = self._web3.eth.get_transaction_count(self._account.address)
            
            # Build transaction with EIP-1559 support if available
            try:
                # Try EIP-1559 (modern) transaction
                latest_block = self._web3.eth.get_block("latest")
                base_fee = latest_block.get("baseFeePerGas", 0)
                
                if base_fee:
                    max_priority_fee = self._web3.to_wei(2, "gwei")
                    max_fee = base_fee + max_priority_fee
                    
                    tx = self._contract.functions.uploadFile(file_hash, file_name_clean).build_transaction({
                        "chainId": self._web3.eth.chain_id,
                        "nonce": nonce,
                        "maxPriorityFeePerGas": max_priority_fee,
                        "maxFeePerGas": max_fee,
                        "gas": 200000,
                    })
                else:
                    # Fallback to legacy transaction
                    tx = self._contract.functions.uploadFile(file_hash, file_name_clean).build_transaction({
                        "chainId": self._web3.eth.chain_id,
                        "nonce": nonce,
                        "gas": 200000,
                        "gasPrice": self._web3.eth.gas_price,
                    })
            except Exception:
                # Final fallback
                tx = self._contract.functions.uploadFile(file_hash, file_name_clean).build_transaction({
                    "chainId": self._web3.eth.chain_id,
                    "nonce": nonce,
                    "gas": 200000,
                    "gasPrice": self._web3.eth.gas_price,
                })
            
            logger.info(f"Submitting blockchain transaction for file: {file_name_clean[:20]}...")
            
            # Sign transaction (secure - key never logged)
            signed_tx = self._web3.eth.account.sign_transaction(tx, self._account.key)
            
            # Send transaction
            tx_hash = self._web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = self._web3.to_hex(tx_hash)
            
            logger.info(f"Transaction submitted: {tx_hash_hex[:20]}...")
            
            # Wait for receipt with timeout
            try:
                receipt = self._web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            except Exception as e:
                raise BlockchainServiceError(
                    f"Transaction timeout after {timeout}s: {str(e)}",
                    http_status=504,
                    error_code="TRANSACTION_TIMEOUT"
                )
            
            # Item 4: Parse receipt and verify FileUploaded event was emitted.
            gas_used    = receipt.get("gasUsed") or receipt.get("gas", 0)
            tx_status   = receipt.get("status", 0)
            block_number = receipt.get("blockNumber", 0)

            if tx_status != 1:
                raise BlockchainServiceError(
                    "Transaction failed (reverted on-chain)",
                    http_status=502,
                    error_code="TRANSACTION_REVERTED"
                )

            # Decode logs to confirm the FileUploaded event was emitted.
            # If the event is missing the call succeeded at the EVM level but
            # produced no state change — treat as failure and do NOT anchor.
            event_found = False
            try:
                logs = self._contract.events.FileUploaded().process_receipt(receipt)
                event_found = len(logs) > 0
                if event_found:
                    ev = logs[0]["args"]
                    logger.info(
                        f"FileUploaded event confirmed: hash={ev['fileHash'][:12]}... "
                        f"file={ev['fileName'][:30]} block={block_number}"
                    )
            except Exception as ev_err:
                logger.error(f"Event decode error (tx={tx_hash_hex[:20]}): {ev_err}")

            if not event_found:
                logger.error(
                    f"Transaction {tx_hash_hex} confirmed (status=1) but FileUploaded "
                    "event NOT found in receipt. File will NOT be marked as anchored."
                )
                raise BlockchainServiceError(
                    "Transaction confirmed but FileUploaded event missing — file not anchored.",
                    http_status=502,
                    error_code="EVENT_MISSING"
                )

            logger.info(f"Transaction confirmed in block {block_number}")

            return BlockchainTransactionResult(
                tx_hash=tx_hash_hex,
                block_number=block_number,
                status="confirmed",
                gas_used=gas_used,
                confirmations=1
            )
            
        except ContractLogicError as e:
            logger.error(f"Contract logic error: {str(e)}")
            raise BlockchainServiceError(
                "Smart contract execution failed",
                http_status=400,
                error_code="CONTRACT_ERROR"
            )
            
        except Web3RPCError as e:
            logger.error(f"RPC error: {str(e)}")
            raise BlockchainServiceError(
                "Blockchain node communication error",
                http_status=503,
                error_code="RPC_ERROR"
            )
            
        except BlockchainServiceError:
            raise
            
        except Exception as e:
            logger.error(f"Unexpected blockchain error: {str(e)}")
            raise BlockchainServiceError(
                "Blockchain operation failed",
                http_status=500,
                error_code="BLOCKCHAIN_ERROR"
            )
    
    def get_file_from_blockchain(self, index: int) -> Dict[str, Any]:
        """Retrieve file metadata from blockchain by index."""
        self._require_initialized()
        
        # Type checker hints
        assert self._web3 is not None
        assert self._contract is not None
        assert self._account is not None
        
        try:
            if index < 0:
                raise BlockchainServiceError(
                    "Invalid index (must be non-negative)",
                    http_status=400,
                    error_code="INVALID_INDEX"
                )
            
            file_data = self._contract.functions.getFile(index).call()
            
            return {
                "file_hash": file_data[0],
                "file_name": file_data[1],
                "uploader": file_data[2],
                "timestamp": file_data[3],
                "blockchain_index": index
            }
            
        except ContractLogicError as e:
            error_str = str(e).lower()
            if "index" in error_str or "bounds" in error_str:
                raise BlockchainServiceError(
                    "File not found on blockchain",
                    http_status=404,
                    error_code="NOT_FOUND"
                )
            raise BlockchainServiceError(
                "Smart contract error",
                http_status=400,
                error_code="CONTRACT_ERROR"
            )
            
        except Exception as e:
            logger.error(f"Blockchain read error: {str(e)}")
            raise BlockchainServiceError(
                "Failed to fetch file from blockchain",
                http_status=500,
                error_code="READ_ERROR"
            )
    
    def get_total_files(self) -> int:
        """Get total number of files stored on blockchain"""
        self._require_initialized()
        
        # Type checker hints
        assert self._web3 is not None
        assert self._contract is not None
        assert self._account is not None
        
        try:
            return int(self._contract.functions.getTotalFiles().call())
        except Exception as e:
            logger.error(f"Failed to get total files: {str(e)}")
            raise BlockchainServiceError(
                "Failed to query blockchain",
                http_status=500,
                error_code="QUERY_ERROR"
            )
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get blockchain health status for monitoring"""
        status: Dict[str, Any] = {
            "enabled": self.is_enabled,
            "ready": self.is_ready,
            "initialization_error": self._initialization_error,
            "connected": False,
            "block_number": None,
            "contract_address": None,
            "account_address": None
        }
        
        if not self.is_enabled:
            status["status"] = "disabled"
            return status
        
        if not self.is_ready:
            status["status"] = "unavailable"
            return status
        
        # Type checker hints
        assert self._web3 is not None
        
        try:
            if self._web3.is_connected():
                status["connected"] = True
                status["block_number"] = self._web3.eth.block_number
                status["status"] = "healthy"
            else:
                status["status"] = "disconnected"
        except Exception as e:
            status["status"] = "error"
            status["error"] = str(e)
        
        # Safe logging - only show truncated addresses
        if self._contract_address:
            status["contract_address"] = f"{self._contract_address[:10]}...{self._contract_address[-8:]}"
        if self._account:
            status["account_address"] = f"{self._account.address[:10]}...{self._account.address[-8:]}"
        
        return status


# Global singleton instance - lazy initialization
_blockchain_service_instance: Optional[BlockchainService] = None


def get_blockchain_service() -> BlockchainService:
    """Get or initialize blockchain service singleton"""
    global _blockchain_service_instance
    if _blockchain_service_instance is None:
        _blockchain_service_instance = BlockchainService()
    return _blockchain_service_instance


def handle_blockchain_error(func):
    """Decorator to convert BlockchainServiceError to HTTPException"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BlockchainServiceError as e:
            raise HTTPException(
                status_code=e.http_status,
                detail={
                    "error": e.message,
                    "code": e.error_code
                }
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in blockchain endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Blockchain operation failed",
                    "code": "INTERNAL_ERROR"
                }
            )
    return wrapper

