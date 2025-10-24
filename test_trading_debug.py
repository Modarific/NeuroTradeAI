#!/usr/bin/env python3
"""
Debug script to test trading engine directly.
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from app.trading.engine import TradingEngine
from app.core.storage import StorageManager
from app.config import DATA_PATH, DB_PATH

async def test_trading_engine():
    """Test the trading engine directly."""
    print("Testing Trading Engine Directly...")
    
    try:
        # Create trading engine
        engine = TradingEngine()
        
        print("Trading engine created")
        
        # Test broker connection
        print("Testing broker connection...")
        connected = await engine.broker.connect()
        print(f"Broker connected: {connected}")
        
        # Test market hours
        print("Testing market hours...")
        market_open = await engine._is_market_open()
        print(f"Market open: {market_open}")
        
        # Test data fetching
        print("Testing data fetching...")
        data = await engine._get_latest_data()
        print(f"Data fetched: {len(data)} symbols")
        if data:
            print(f"Sample data: {list(data.keys())[:3]}")
        
        # Test feature computation
        if data:
            print("Testing feature computation...")
            features = await engine._compute_features(data)
            print(f"Features computed: {len(features)} features")
            
            # Test signal generation
            print("Testing signal generation...")
            signals = await engine._generate_signals(features)
            print(f"Signals generated: {len(signals)} signals")
            
            if signals:
                print(f"Sample signal: {signals[0]}")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_trading_engine())
