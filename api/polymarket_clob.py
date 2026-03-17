import aiohttp
import asyncio
import time
import json
import logging

# In a production environment, you would use the official SDK or web3.py for EIP-712 signing
# from py_clob_client.client import ClobClient 
# from py_clob_client.clob_types import OrderArgs

logger = logging.getLogger("Predator_CLOB")

class PolymarketCLOB:
    def __init__(self, host: str = "https://clob.polymarket.com"):
        """
        Initializes the Polymarket Central Limit Order Book (CLOB) client.
        In a real scenario, this takes the L2 API Key, Secret, and Passphrase.
        """
        self.host = host
        self.session = None
        # Mock credentials loaded from config/.env
        self.api_key = "YOUR_CLOB_API_KEY"
        self.wallet_address = "0xYOURWALLET..."

    async def connect(self):
        """
        Opens a persistent asynchronous HTTP session.
        Reusing the same session is critical for HFT to reduce TCP handshake latency.
        """
        # We use a custom TCP connector to optimize connection pooling for HFT
        connector = aiohttp.TCPConnector(limit=100, keepalive_timeout=60)
        self.session = aiohttp.ClientSession(connector=connector)
        logger.info(f"Connected to Polymarket CLOB at {self.host}")

    async def disconnect(self):
        """
        Gracefully closes the async session to prevent memory leaks.
        """
        if self.session:
            await self.session.close()
            logger.info("Disconnected from Polymarket CLOB.")

    async def get_order_books(self, token_ids: list) -> dict:
        """
        Fetches the L2 order book (bids and asks) for specific outcome tokens.
        
        :param token_ids: List of ERC-1155 token IDs representing market outcomes.
        :return: A dictionary containing the current best bid/ask and implied probabilities.
        """
        order_books = {}
        # HFT Optimization: Use asyncio.gather to fetch multiple order books concurrently
        tasks = [self._fetch_single_book(token_id) for token_id in token_ids]
        results = await asyncio.gather(*tasks)
        
        for token_id, book_data in zip(token_ids, results):
            order_books[token_id] = book_data
            
        return order_books

    async def _fetch_single_book(self, token_id: str) -> dict:
        """
        Internal method to hit the /book endpoint for a specific token.
        """
        url = f"{self.host}/book?token_id={token_id}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Calculate implied probability based on the best ask price
                    best_ask = float(data.get('asks', [{'price': '1'}])[0]['price'])
                    return {
                        "best_bid": float(data.get('bids', [{'price': '0'}])[0]['price']),
                        "best_ask": best_ask,
                        "implied_probability": best_ask  # Price directly correlates to probability (e.g., $0.60 = 60%)
                    }
                else:
                    logger.warning(f"Failed to fetch book for {token_id}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Network error fetching book for {token_id}: {e}")
            return None

    async def place_limit_order(self, token_id: str, price: float, size: float, side: str):
        """
        Constructs, signs (EIP-712), and submits a zero-fee Limit Order to the CLOB.
        This represents the 'Market Making Style' mentioned in the README.
        
        :param token_id: The asset/outcome being traded.
        :param price: Target price (e.g., 0.55 cents).
        :param size: Amount of shares to buy/sell.
        :param side: "BUY" or "SELL".
        """
        # 1. Construct the raw order payload
        order_payload = {
            "token_id": token_id,
            "price": str(price),
            "size": str(size),
            "side": side,
            "expiration": int(time.time()) + 60, # Order expires in 60 seconds (GTC/GTD logic)
            "fee_rate_bps": "0" # Zero-fee maker order!
        }

        # 2. Cryptographic Signature (EIP-712)
        # In actual implementation, we hash the order struct and sign it with the wallet's private key.
        signature = self._sign_order_eip712(order_payload)
        
        # Add the signature to the payload for the API request
        order_payload["signature"] = signature

        # 3. Transmit the signed order to the matching engine
        url = f"{self.host}/order"
        headers = {
            "POLYMARKET-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            start_time = time.time()
            # POST request to submit the order
            async with self.session.post(url, headers=headers, json=order_payload) as response:
                latency = (time.time() - start_time) * 1000 # Calculate latency in ms
                
                if response.status == 200:
                    logger.info(f"[{latency:.2f}ms] Order Placed: {side} {size} @ ${price} for {token_id}")
                    return await response.json()
                else:
                    error_msg = await response.text()
                    logger.error(f"Order rejected: {error_msg}")
                    return None
        except Exception as e:
            logger.error(f"Failed to transmit order: {e}")
            return None

    def _sign_order_eip712(self, order_payload: dict) -> str:
        """
        Simulates the EIP-712 cryptographic signing process required by Polymarket's L2 contracts.
        Ensures that our bot can trade directly from a non-custodial wallet without giving up funds.
        """
        # Placeholder for web3.eth.account.sign_typed_data(...)
        logger.debug("Signing order payload via EIP-712...")
        return "0x_mock_cryptographic_signature_hash_8a9b..."
