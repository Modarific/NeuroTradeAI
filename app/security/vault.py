"""
Encrypted credential vault for storing API keys and sensitive data.
Uses Fernet (AES-128) symmetric encryption with user passphrase.
"""
import os
import base64
from typing import Dict, Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import getpass
import json
import logging

logger = logging.getLogger(__name__)

class CredentialVault:
    """Secure storage for API keys and credentials."""
    
    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        self._fernet: Optional[Fernet] = None
        self._salt: Optional[bytes] = None
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one."""
        if self._salt is None:
            salt_path = self.vault_path + ".salt"
            if os.path.exists(salt_path):
                with open(salt_path, 'rb') as f:
                    self._salt = f.read()
            else:
                self._salt = os.urandom(16)
                with open(salt_path, 'wb') as f:
                    f.write(self._salt)
        return self._salt
    
    def unlock(self, password: str) -> bool:
        """Unlock the vault with user password."""
        try:
            salt = self._get_or_create_salt()
            key = self._derive_key(password, salt)
            self._fernet = Fernet(key)
            
            # Test if vault exists and can be decrypted
            if os.path.exists(self.vault_path):
                with open(self.vault_path, 'rb') as f:
                    encrypted_data = f.read()
                self._fernet.decrypt(encrypted_data)
            
            logger.info("Vault unlocked successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to unlock vault: {e}")
            return False
    
    def lock(self):
        """Lock the vault (clear encryption key from memory)."""
        self._fernet = None
        logger.info("Vault locked")
    
    def is_unlocked(self) -> bool:
        """Check if vault is currently unlocked."""
        return self._fernet is not None
    
    def store_credentials(self, credentials: Dict[str, Any]) -> bool:
        """Store encrypted credentials in the vault."""
        if not self.is_unlocked():
            raise RuntimeError("Vault must be unlocked before storing credentials")
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
            
            # Encrypt and store
            json_data = json.dumps(credentials, indent=2)
            encrypted_data = self._fernet.encrypt(json_data.encode())
            
            with open(self.vault_path, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info("Credentials stored successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to store credentials: {e}")
            return False
    
    def get_credentials(self) -> Dict[str, Any]:
        """Retrieve and decrypt credentials from the vault."""
        if not self.is_unlocked():
            raise RuntimeError("Vault must be unlocked before retrieving credentials")
        
        if not os.path.exists(self.vault_path):
            return {}
        
        try:
            with open(self.vault_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to retrieve credentials: {e}")
            return {}
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a specific service."""
        credentials = self.get_credentials()
        return credentials.get(service, {}).get('api_key')
    
    def set_api_key(self, service: str, api_key: str, **kwargs) -> bool:
        """Set API key for a specific service."""
        credentials = self.get_credentials()
        if service not in credentials:
            credentials[service] = {}
        
        credentials[service]['api_key'] = api_key
        credentials[service].update(kwargs)
        
        return self.store_credentials(credentials)
    
    def remove_service(self, service: str) -> bool:
        """Remove all credentials for a service."""
        credentials = self.get_credentials()
        if service in credentials:
            del credentials[service]
            return self.store_credentials(credentials)
        return True
    
    def list_services(self) -> list:
        """List all services with stored credentials."""
        credentials = self.get_credentials()
        return list(credentials.keys())
    
    def prompt_for_password(self) -> str:
        """Prompt user for vault password."""
        return getpass.getpass("Enter vault password: ")
    
    def initialize_vault(self) -> bool:
        """Initialize vault with user password."""
        password = self.prompt_for_password()
        if len(password) < 8:
            print("Password must be at least 8 characters long")
            return False
        
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Passwords do not match")
            return False
        
        # Create empty vault
        return self.unlock(password) and self.store_credentials({})


def create_vault(vault_path: str) -> CredentialVault:
    """Create a new credential vault instance."""
    return CredentialVault(vault_path)


def setup_vault_interactive(vault_path: str) -> Optional[CredentialVault]:
    """Interactive setup for credential vault."""
    vault = CredentialVault(vault_path)
    
    if os.path.exists(vault_path):
        print(f"Vault exists at {vault_path}")
        password = vault.prompt_for_password()
        if vault.unlock(password):
            return vault
        else:
            print("Invalid password or corrupted vault")
            return None
    else:
        print(f"Creating new vault at {vault_path}")
        if vault.initialize_vault():
            return vault
        else:
            return None
