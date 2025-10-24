#!/usr/bin/env python3
"""
Test script to force signal generation by creating extreme market conditions.
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from app.trading.engine import TradingEngine
from app.trading.strategies.mean_reversion import MeanReversionStrategy

async def test_force_signals():
    """Test signal generation with extreme conditions."""
    print("Testing Signal Generation with Extreme Conditions...")
    
    try:
        # Create trading engine
        engine = TradingEngine()
        
        # Create mean reversion strategy
        strategy = MeanReversionStrategy()
        
        # Create extreme market conditions that should trigger signals
        extreme_features = {
            'AAPL': {
                'rsi': 25,  # Very oversold (should trigger BUY)
                'bb_lower': 100,
                'bb_upper': 200,
                'bb_middle': 150,
                'bb_position': 0.01,  # Very close to lower band
                'close': 102,  # Just above lower band
                'current_price': 102,
                'volume': 1000000
            },
            'MSFT': {
                'rsi': 75,  # Very overbought (should trigger SELL)
                'bb_lower': 300,
                'bb_upper': 400,
                'bb_middle': 350,
                'bb_position': 0.99,  # Very close to upper band
                'close': 398,  # Just below upper band
                'current_price': 398,
                'volume': 2000000
            }
        }
        
        print("Testing AAPL (oversold conditions)...")
        aapl_signals = strategy.generate_signals('AAPL', extreme_features['AAPL'], {})
        print(f"AAPL signals: {len(aapl_signals)}")
        if aapl_signals:
            print(f"AAPL signal: {aapl_signals[0]}")
        
        print("Testing MSFT (overbought conditions)...")
        msft_signals = strategy.generate_signals('MSFT', extreme_features['MSFT'], {})
        print(f"MSFT signals: {len(msft_signals)}")
        if msft_signals:
            print(f"MSFT signal: {msft_signals[0]}")
        
        print("All tests completed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_force_signals())
