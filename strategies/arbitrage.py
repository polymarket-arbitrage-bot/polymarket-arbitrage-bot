from core.ev_calculator import calculate_ev
from strategies.hedging import calculate_partial_hedge
from utils.shield import split_order_for_anti_frontrun

class ArbitrageStrategy:
    def __init__(self, config: dict):
        self.risk_profile = config.get("risk_profile", "Conservative")
        self.min_profit_margin = 0.005 # 0.5% micro-profit target

    def analyze(self, spot_prices: dict, clob_states: dict) -> list:
        """
        Compares spot prices with Polymarket outcome prices to find arbitrage windows.
        """
        executable_signals = []

        for asset, spot_price in spot_prices.items():
            clob_data = clob_states.get(asset)
            if not clob_data:
                continue

            # Calculate Expected Value (EV Maximizer)
            ev = calculate_ev(spot_price, clob_data["implied_probability"])
            
            # If EV is positive and covers our minimum margin
            if ev > self.min_profit_margin:
                # 1. Calculate base order size
                base_size = self._calculate_position_size(ev)
                
                # 2. Apply Partial Hedge (Delta-neutral logic)
                hedged_size = calculate_partial_hedge(base_size, self.risk_profile)
                
                # 3. Apply Anti-Frontrun Shield (split the order)
                stealth_orders = split_order_for_anti_frontrun(hedged_size)
                
                for order in stealth_orders:
                    executable_signals.append({
                        "asset": asset,
                        "side": "BUY" if clob_data["implied_probability"] < 0.5 else "SELL",
                        "target_price": clob_data["best_ask"],
                        "size": order["size"]
                    })

        return executable_signals

    def _calculate_position_size(self, ev: float) -> float:
        """
        Kelly criterion or dynamic sizing based on EV.
        """
        # Placeholder for position sizing math
        return 100.0 * ev
