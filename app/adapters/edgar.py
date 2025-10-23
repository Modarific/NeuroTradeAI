"""
SEC EDGAR filings adapter.
Collects 10-K, 10-Q, 8-K filings from SEC EDGAR database.
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import json
import re

from .base import BaseAdapter
from ..core.normalizer import normalizer

logger = logging.getLogger(__name__)

class EdgarAdapter(BaseAdapter):
    """SEC EDGAR filings adapter."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.storage = config.get('storage')
        self.rate_limiter = config.get('rate_limiter')
        self.base_url = "https://www.sec.gov/Archives/edgar"
        self.api_url = "https://data.sec.gov/api/xbrl/companyfacts"
        self.watchlist = config.get('watchlist', ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"])
        self.session = None
        self.last_check = None
        
    async def start(self) -> bool:
        """Start EDGAR adapter."""
        try:
            # EDGAR doesn't require API key (public access)
            logger.info("Starting EDGAR adapter with public access")
            
            # Create aiohttp session
            self.session = aiohttp.ClientSession(
                headers={
                    'User-Agent': 'NeuroTradeAI Data Scraper (contact@example.com)',
                    'Accept': 'application/json',
                    'Host': 'data.sec.gov'
                },
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            logger.info("EDGAR adapter initialized")
            
            # Start background task for filing collection
            await self._start_background_task()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting EDGAR adapter: {e}")
            return False
    
    async def stop(self):
        """Stop EDGAR adapter."""
        try:
            if self.session:
                await self.session.close()
            logger.info("EDGAR adapter stopped")
        except Exception as e:
            logger.error(f"Error stopping EDGAR adapter: {e}")
    
    async def _fetch_data(self):
        """Fetch EDGAR filings data."""
        try:
            # Check for new filings every 6 hours
            if self.last_check and (datetime.now(timezone.utc) - self.last_check).hours < 6:
                await asyncio.sleep(3600)  # Wait 1 hour
                return
            
            logger.info("Checking for new EDGAR filings...")
            
            # Get company CIK numbers for watchlist
            cik_map = await self._get_cik_numbers()
            
            # Check for new filings for each company
            for symbol in self.watchlist:
                if symbol in cik_map:
                    await self._check_company_filings(symbol, cik_map[symbol])
                    await asyncio.sleep(1)  # Rate limiting
            
            self.last_check = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error fetching EDGAR data: {e}")
    
    async def _get_cik_numbers(self) -> Dict[str, str]:
        """Get CIK numbers for watchlist symbols."""
        cik_map = {}
        
        try:
            # Use SEC company tickers API
            url = "https://www.sec.gov/files/company_tickers.json"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Map tickers to CIK numbers
                    for entry in data.values():
                        ticker = entry.get('ticker', '').upper()
                        cik = str(entry.get('cik_str', ''))
                        
                        if ticker in self.watchlist and cik:
                            cik_map[ticker] = cik.zfill(10)  # Pad CIK to 10 digits
                            
                    logger.info(f"Found CIK numbers for {len(cik_map)} symbols")
                else:
                    logger.warning(f"Failed to get CIK numbers: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error getting CIK numbers: {e}")
        
        return cik_map
    
    async def _check_company_filings(self, symbol: str, cik: str):
        """Check for new filings for a specific company."""
        try:
            # Get recent filings from company facts API
            url = f"{self.api_url}/CIK{cik}.json"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract recent filings
                    recent_filings = self._extract_recent_filings(data, symbol)
                    
                    if recent_filings:
                        logger.info(f"Found {len(recent_filings)} recent filings for {symbol}")
                        
                        # Store filings
                        for filing in recent_filings:
                            normalized = self.normalize(filing)
                            if normalized:
                                await self._handle_data(normalized)
                else:
                    logger.warning(f"Failed to get filings for {symbol}: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error checking filings for {symbol}: {e}")
    
    def _extract_recent_filings(self, data: Dict[str, Any], symbol: str) -> List[Dict[str, Any]]:
        """Extract recent filings from company facts data."""
        filings = []
        
        try:
            # Look for recent 10-K, 10-Q, 8-K filings
            if 'facts' in data and 'dei' in data['facts']:
                dei_facts = data['facts']['dei']
                
                # Get recent 10-K filings
                if 'EntityRegistrantName' in dei_facts:
                    entity_name = dei_facts['EntityRegistrantName']
                    
                    # Check for recent filings in the last 30 days
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
                    
                    # Look for recent 10-K, 10-Q, 8-K filings
                    for filing_type in ['10-K', '10-Q', '8-K']:
                        if filing_type in dei_facts:
                            filing_data = dei_facts[filing_type]
                            
                            if 'units' in filing_data:
                                for unit in filing_data['units'].values():
                                    for filing in unit:
                                        filing_date = filing.get('end', '')
                                        
                                        if filing_date:
                                            try:
                                                # Parse filing date
                                                filing_dt = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                                                
                                                if filing_dt >= cutoff_date:
                                                    filings.append({
                                                        'symbol': symbol,
                                                        'filing_type': filing_type,
                                                        'filing_date': filing_date,
                                                        'entity_name': entity_name,
                                                        'raw_data': filing,
                                                        'source': 'edgar',
                                                        'timestamp_utc': datetime.now(timezone.utc).isoformat()
                                                    })
                                            except Exception as e:
                                                logger.debug(f"Error parsing filing date: {e}")
                                                continue
                                        
        except Exception as e:
            logger.error(f"Error extracting filings: {e}")
        
        return filings
    
    def normalize(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize filing data to canonical schema."""
        return normalizer.normalize_filing(raw_data, "edgar")
    
    async def _handle_data(self, data: Dict[str, Any]):
        """Handle processed filing data."""
        try:
            # Store filing data
            self.storage.store_filings([data])
            
            # Broadcast to WebSocket clients
            from app.api.websocket import broadcast_filing_update
            await broadcast_filing_update(data['symbol'], data)
            
            logger.info(f"Processed filing: {data.get('filing_type', 'Unknown')} for {data.get('symbol', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Error handling filing data: {e}")
    
    async def health_check(self) -> bool:
        """Check if EDGAR API is accessible."""
        try:
            if not self.session:
                return False
                
            # Test with a simple request
            url = "https://www.sec.gov/files/company_tickers.json"
            async with self.session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"EDGAR health check failed: {e}")
            return False
