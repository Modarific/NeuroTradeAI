"""
API key management endpoints for the trading data scraper.
Allows users to add, update, and manage API keys through the web interface.
"""
from fastapi import APIRouter, HTTPException, Form, Request
from typing import Dict, Any, Optional
import logging

from app.security.vault import CredentialVault
from app.config import KEYS_PATH

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize vault (will be set by main app)
vault: Optional[CredentialVault] = None

def set_vault(vault_instance: CredentialVault):
    """Set the vault instance from main app."""
    global vault
    vault = vault_instance

@router.get("/keys")
async def get_api_keys():
    """Get list of configured API keys (without revealing the actual keys)."""
    if not vault or not vault.is_unlocked():
        raise HTTPException(status_code=401, detail="Vault not unlocked")
    
    try:
        services = vault.list_services()
        key_info = {}
        
        for service in services:
            credentials = vault.get_credentials()
            service_data = credentials.get(service, {})
            key_info[service] = {
                "configured": bool(service_data.get('api_key')),
                "has_key": bool(service_data.get('api_key')),
                "last_updated": service_data.get('last_updated', 'Unknown')
            }
        
        return {
            "services": key_info,
            "total_configured": len([s for s in key_info.values() if s['configured']])
        }
        
    except Exception as e:
        logger.error(f"Error getting API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keys/{service}")
async def add_api_key(
    service: str,
    api_key: str = Form(...),
    description: Optional[str] = Form(None)
):
    """Add or update an API key for a service."""
    if not vault or not vault.is_unlocked():
        raise HTTPException(status_code=401, detail="Vault not unlocked")
    
    try:
        # Validate service name
        valid_services = ["finnhub", "twelvedata", "alphavantage", "edgar", "fmp", "reddit"]
        if service not in valid_services:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid service. Must be one of: {', '.join(valid_services)}"
            )
        
        # Store the API key
        success = vault.set_api_key(
            service, 
            api_key, 
            description=description,
            last_updated=vault._get_or_create_salt().hex()[:8]  # Simple timestamp
        )
        
        if success:
            logger.info(f"API key added for {service}")
            return {
                "message": f"API key for {service} added successfully",
                "service": service,
                "configured": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store API key")
            
    except Exception as e:
        logger.error(f"Error adding API key for {service}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/keys/{service}")
async def remove_api_key(service: str):
    """Remove an API key for a service."""
    if not vault or not vault.is_unlocked():
        raise HTTPException(status_code=401, detail="Vault not unlocked")
    
    try:
        success = vault.remove_service(service)
        
        if success:
            logger.info(f"API key removed for {service}")
            return {
                "message": f"API key for {service} removed successfully",
                "service": service,
                "configured": False
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to remove API key")
            
    except Exception as e:
        logger.error(f"Error removing API key for {service}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keys/status")
async def get_key_status():
    """Get detailed status of API key configuration."""
    if not vault or not vault.is_unlocked():
        return {
            "vault_unlocked": False,
            "message": "Vault not unlocked"
        }
    
    try:
        services = vault.list_services()
        credentials = vault.get_credentials()
        
        status = {
            "vault_unlocked": True,
            "services": {}
        }
        
        # Check each service
        for service in ["finnhub", "twelvedata", "alphavantage", "edgar", "fmp"]:
            service_data = credentials.get(service, {})
            has_key = bool(service_data.get('api_key'))
            
            status["services"][service] = {
                "configured": has_key,
                "has_key": has_key,
                "description": service_data.get('description', ''),
                "last_updated": service_data.get('last_updated', 'Never')
            }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting key status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keys/test/{service}")
async def test_api_key(service: str):
    """Test an API key for a service."""
    if not vault or not vault.is_unlocked():
        raise HTTPException(status_code=401, detail="Vault not unlocked")
    
    try:
        api_key = vault.get_api_key(service)
        if not api_key:
            raise HTTPException(status_code=404, detail=f"No API key found for {service}")
        
        # Test the API key based on service
        if service == "finnhub":
            return await _test_finnhub_key(api_key)
        elif service == "twelvedata":
            return await _test_twelvedata_key(api_key)
        elif service == "alphavantage":
            return await _test_alphavantage_key(api_key)
        else:
            return {
                "service": service,
                "status": "configured",
                "message": f"API key for {service} is configured but testing not implemented"
            }
            
    except Exception as e:
        logger.error(f"Error testing API key for {service}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _test_finnhub_key(api_key: str) -> Dict[str, Any]:
    """Test Finnhub API key."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = "https://finnhub.io/api/v1/quote"
            params = {"symbol": "AAPL", "token": api_key}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "service": "finnhub",
                        "status": "valid",
                        "message": "API key is valid and working",
                        "test_data": {"symbol": "AAPL", "price": data.get('c', 'N/A')}
                    }
                else:
                    return {
                        "service": "finnhub",
                        "status": "invalid",
                        "message": f"API returned status {response.status}"
                    }
    except Exception as e:
        return {
            "service": "finnhub",
            "status": "error",
            "message": f"Error testing API key: {str(e)}"
        }

async def _test_twelvedata_key(api_key: str) -> Dict[str, Any]:
    """Test TwelveData API key."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = "https://api.twelvedata.com/quote"
            params = {"symbol": "AAPL", "apikey": api_key}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "service": "twelvedata",
                        "status": "valid",
                        "message": "API key is valid and working",
                        "test_data": {"symbol": "AAPL", "price": data.get('close', 'N/A')}
                    }
                else:
                    return {
                        "service": "twelvedata",
                        "status": "invalid",
                        "message": f"API returned status {response.status}"
                    }
    except Exception as e:
        return {
            "service": "twelvedata",
            "status": "error",
            "message": f"Error testing API key: {str(e)}"
        }

async def _test_alphavantage_key(api_key: str) -> Dict[str, Any]:
    """Test Alpha Vantage API key."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "AAPL",
                "apikey": api_key
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "service": "alphavantage",
                        "status": "valid",
                        "message": "API key is valid and working",
                        "test_data": {"symbol": "AAPL", "price": data.get('Global Quote', {}).get('05. price', 'N/A')}
                    }
                else:
                    return {
                        "service": "alphavantage",
                        "status": "invalid",
                        "message": f"API returned status {response.status}"
                    }
    except Exception as e:
        return {
            "service": "alphavantage",
            "status": "error",
            "message": f"Error testing API key: {str(e)}"
        }
