import asyncio
import time
from api.spot_markets import SpotMarketAPI
from api.polymarket_clob import PolymarketCLOB
from strategies.arbitrage import ArbitrageStrategy

class PredatorEngine:
    def __init__(self, config: dict):
        self.config = config
        self.spot_api = SpotMarketAPI()
        self.clob_api = PolymarketCLOB()
        self.strategy = ArbitrageStrategy(config)
        self.is_running = False

    async def start(self):
        """
        Main HFT event loop. Scans micro-intervals and executes trades.
        """
        self.is_running = True
        
        # Connect to WebSockets for real-time data
        await self.spot_api.connect()
        await self.clob_api.connect()

        while self.is_running:
            start_time = time.time()
            
            # 1. Fetch current spot prices (e.g., Binance)
            spot_prices = await self.spot_api.get_latest_prices(self.config["assets"])
            
            # 2. Fetch Polymarket order book states
            clob_states = await self.clob_api.get_order_books(self.config["assets"])
            
            # 3. Pass data to the arbitrage strategy to find spreads
            signals = self.strategy.analyze(spot_prices, clob_states)
            
            # 4. Execute trades if EV is positive
            if signals:
                await self._execute_signals(signals)

            # Ensure we don't spam the CPU, maintaining the 500ms EV recalculation cycle
            elapsed = time.time() - start_time
            sleep_time = max(0, 0.5 - elapsed)
            await asyncio.sleep(sleep_time)

    async def _execute_signals(self, signals):
        """
        Executes trade signals using Limit Orders and Anti-Frontrun Shield.
        """
        for signal in signals:
            # Example: Send limit order to Polymarket
            await self.clob_api.place_limit_order(
                asset=signal["asset"],
                price=signal["target_price"],
                size=signal["size"],
                side=signal["side"]
            )

    async def stop(self):
        """
        Gracefully stops the engine and cleans up connections.
        """
        self.is_running = False
        await self.spot_api.disconnect()
        await self.clob_api.disconnect()
