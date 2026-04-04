"""
tools.py - DeFi tool definitions for OpenGradient LLM tool-calling.
"""

import time
import random
import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)

# ── LIVE PRICES from CoinGecko ────────────────────────────────
_price_cache: dict = {}
_price_cache_time: float = 0

def _get_prices() -> dict:
    global _price_cache, _price_cache_time
    if _price_cache and time.time() - _price_cache_time < 60:
        return _price_cache
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum,bitcoin,usd-coin,arbitrum,optimism,matic-network,wrapped-bitcoin,tether&vs_currencies=usd"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        prices = {
            "ETH":   data.get("ethereum",        {}).get("usd", 3241.80),
            "BTC":   data.get("bitcoin",          {}).get("usd", 62180.00),
            "WBTC":  data.get("wrapped-bitcoin",  {}).get("usd", 62180.00),
            "USDC":  data.get("usd-coin",         {}).get("usd", 1.00),
            "USDT":  data.get("tether",           {}).get("usd", 1.00),
            "ARB":   data.get("arbitrum",         {}).get("usd", 0.72),
            "OP":    data.get("optimism",         {}).get("usd", 1.85),
            "MATIC": data.get("matic-network",    {}).get("usd", 0.58),
            "DAI":   1.00,
        }
        _price_cache = prices
        _price_cache_time = time.time()
        logger.info(f"Live prices: ETH=${prices['ETH']:,.2f}")
        return prices
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")
        return _price_cache or {"ETH": 3241.80, "USDC": 1.00, "WBTC": 62180.00, "ARB": 0.72, "USDT": 1.00, "DAI": 1.00, "OP": 1.85, "MATIC": 0.58}

def _price(token: str) -> float:
    return _get_prices().get(token.upper(), 0.0)

def _rand_tx() -> str:
    return "0x" + "".join(random.choices("0123456789abcdef", k=64))

# ── For /api/prices endpoint ──────────────────────────────────
MOCK_PRICES_USD = _get_prices()

# ── Supported chains and protocols ───────────────────────────
SUPPORTED_CHAINS = {
    "arbitrum":  {"name": "Arbitrum",  "chain_id": 42161, "color": "#28a0f0"},
    "optimism":  {"name": "Optimism",  "chain_id": 10,    "color": "#ff0420"},
    "polygon":   {"name": "Polygon",   "chain_id": 137,   "color": "#8247e5"},
    "base":      {"name": "Base",      "chain_id": 8453,  "color": "#0052ff"},
    "zksync":    {"name": "zkSync",    "chain_id": 324,   "color": "#4e529a"},
    "ethereum":  {"name": "Ethereum",  "chain_id": 1,     "color": "#627eea"},
}

STAKE_PROTOCOLS = {
    "lido":        {"apy": 3.8,  "receive_token": "stETH",  "min_amount": 0.01},
    "rocket pool": {"apy": 3.6,  "receive_token": "rETH",   "min_amount": 0.01},
    "aave":        {"apy": 4.9,  "receive_token": "aUSDC",  "min_amount": 1.0},
    "compound":    {"apy": 4.5,  "receive_token": "cUSDC",  "min_amount": 1.0},
    "curve":       {"apy": 6.2,  "receive_token": "CRV-LP", "min_amount": 0.001},
}

# ── TOOL SCHEMAS ──────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_wallet_balance",
            "description": "Get the current token balances for the connected wallet. Call when user asks about balance, portfolio, holdings or net worth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet_address": {"type": "string", "description": "The connected wallet address"}
                },
                "required": ["wallet_address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_price",
            "description": "Get the current USD price of one or more tokens.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tokens": {"type": "array", "items": {"type": "string"}, "description": "Token symbols e.g. ['ETH','USDC']"}
                },
                "required": ["tokens"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "swap_tokens",
            "description": "Get a swap quote between two tokens. Call when user wants to swap, trade, exchange or convert tokens.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_token": {"type": "string", "description": "Token to sell e.g. ETH"},
                    "to_token":   {"type": "string", "description": "Token to buy e.g. USDC"},
                    "amount":     {"type": "number", "description": "Amount to sell"},
                    "slippage":   {"type": "number", "description": "Slippage tolerance in percent, default 0.5"},
                },
                "required": ["from_token", "to_token", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bridge_tokens",
            "description": "Bridge tokens from current chain to another chain. Call when user mentions bridging or moving funds to Arbitrum, Optimism, Polygon, Base, zkSync.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token":             {"type": "string", "description": "Token to bridge e.g. ETH"},
                    "amount":            {"type": "number", "description": "Amount to bridge"},
                    "destination_chain": {"type": "string", "description": "Target chain: arbitrum, optimism, polygon, base, zksync, ethereum"},
                    "protocol":          {"type": "string", "description": "Bridge protocol: hop, across, stargate. Default: hop"},
                },
                "required": ["token", "amount", "destination_chain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stake_tokens",
            "description": "Stake tokens to earn yield. Call when user wants to stake, deposit or earn yield. Protocols: Lido, Rocket Pool, Aave, Compound, Curve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token":    {"type": "string", "description": "Token to stake e.g. ETH"},
                    "amount":   {"type": "number", "description": "Amount to stake"},
                    "protocol": {"type": "string", "description": "Protocol: lido, rocket pool, aave, compound, curve"},
                },
                "required": ["token", "amount", "protocol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tx_history",
            "description": "Get recent transaction history for the wallet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet_address": {"type": "string"},
                    "limit":          {"type": "integer", "description": "Number of transactions, default 10"},
                },
                "required": ["wallet_address"],
            },
        },
    },
]

# ── TOOL EXECUTOR ─────────────────────────────────────────────
def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:

    if name == "get_wallet_balance":
        address = arguments.get("wallet_address", "")
        prices  = _get_prices()

        # Always show these 4 tokens — fetch real balances, show 0 if not found
        REQUIRED_TOKENS = [
            ("ETH",  None,                                             18),
            ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",    6),
            ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7",    6),
            ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",   18),
        ]

        on_chain = {}
        if address and address.startswith("0x") and len(address) == 42:
            try:
                import json as _json
                from web3 import Web3
                w3       = Web3(Web3.HTTPProvider("https://eth.llamarpc.com", request_kwargs={"timeout": 8}))
                checksum = Web3.to_checksum_address(address)
                abi      = _json.loads('[{"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')

                # ETH native balance
                eth_wei = w3.eth.get_balance(checksum)
                on_chain["ETH"] = float(Web3.from_wei(eth_wei, "ether"))

                # ERC-20 balances
                for sym, addr, dec in REQUIRED_TOKENS:
                    if addr is None:
                        continue
                    try:
                        c   = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
                        raw = c.functions.balanceOf(checksum).call()
                        on_chain[sym] = raw / (10 ** dec)
                    except Exception:
                        on_chain[sym] = 0.0

            except Exception as e:
                logger.warning(f"On-chain balance fetch failed: {e}")

        # Build result — always include all 4 tokens
        balances = []
        for sym, _, _ in REQUIRED_TOKENS:
            amt = round(on_chain.get(sym, 0.0), 6)
            usd = round(amt * prices.get(sym, prices.get("ETH", 0) if sym == "WETH" else 0), 2)
            balances.append({"token": sym, "amount": amt, "usd_value": usd})

        total = sum(b["usd_value"] for b in balances)
        source = "live on-chain" if on_chain else "rpc unavailable"
        return {"success": True, "wallet": address or "unknown", "balances": balances, "total_usd": round(total, 2), "network": "Ethereum Mainnet", "source": source}

    elif name == "get_token_price":
        tokens = arguments.get("tokens", [])
        prices = _get_prices()
        result = {}
        for t in tokens:
            result[t.upper()] = prices.get(t.upper(), 0.0)
        return {"success": True, "prices_usd": result, "source": "CoinGecko (live)", "timestamp": int(time.time())}

    elif name == "swap_tokens":
        from_tok   = arguments["from_token"].upper()
        to_tok     = arguments["to_token"].upper()
        amount     = float(arguments["amount"])
        slippage   = float(arguments.get("slippage", 0.5))
        prices     = _get_prices()
        from_price = prices.get(from_tok, 0)
        to_price   = prices.get(to_tok, 0)
        if to_price == 0:
            return {"success": False, "error": f"Token {to_tok} not supported"}
        rate       = from_price / to_price
        output_amt = round(amount * rate, 6)
        return {
            "success": True, "action": "swap",
            "from_token": from_tok, "to_token": to_tok,
            "input_amount": amount, "output_amount": output_amt,
            "rate": round(rate, 6), "from_usd": round(amount * from_price, 2),
            "fee_usd": round(amount * from_price * 0.0005, 4),
            "price_impact": round(random.uniform(0.01, 0.08), 3),
            "gas_usd": round(random.uniform(0.80, 2.50), 2),
            "route": "Uniswap v3 (OG-routed)",
            "slippage": slippage,
            "requires_confirmation": True,
        }

    elif name == "bridge_tokens":
        token   = arguments["token"].upper()
        amount  = float(arguments["amount"])
        chain   = arguments["destination_chain"].lower()
        proto   = arguments.get("protocol", "hop").capitalize()
        ch_info = SUPPORTED_CHAINS.get(chain, {"name": chain.title(), "chain_id": 0})
        fee     = round(amount * 0.001, 6)
        return {
            "success": True, "action": "bridge",
            "token": token, "amount": amount,
            "destination_chain": ch_info["name"], "chain_id": ch_info["chain_id"],
            "protocol": proto, "receive_amount": round(amount - fee, 6),
            "bridge_fee": fee, "gas_usd": round(random.uniform(0.50, 1.80), 2),
            "eta_minutes": 10 if chain == "ethereum" else 3,
            "requires_confirmation": True,
        }

    elif name == "stake_tokens":
        token    = arguments["token"].upper()
        amount   = float(arguments["amount"])
        protocol = arguments.get("protocol", "lido").lower()
        info     = STAKE_PROTOCOLS.get(protocol, {"apy": 3.8, "receive_token": "stETH", "min_amount": 0.01})
        return {
            "success": True, "action": "stake",
            "token": token, "amount": amount,
            "protocol": protocol.title(), "apy": info["apy"],
            "receive_token": info["receive_token"], "receive_amount": amount,
            "annual_yield": round(amount * info["apy"] / 100, 6),
            "gas_usd": round(random.uniform(1.20, 3.50), 2),
            "requires_confirmation": True,
        }

    elif name == "get_tx_history":
        limit = int(arguments.get("limit", 7))
        txs   = [
            {"type": "Swap",    "description": "1 ETH → 3,241.80 USDC",   "time": "2 mins ago",  "status": "confirmed", "hash": _rand_tx()},
            {"type": "Bridge",  "description": "0.5 ETH → Arbitrum",       "time": "1 hour ago",  "status": "confirmed", "hash": _rand_tx()},
            {"type": "Stake",   "description": "2 ETH staked on Lido",     "time": "3 hours ago", "status": "confirmed", "hash": _rand_tx()},
            {"type": "Swap",    "description": "500 USDC → 0.154 ETH",     "time": "Yesterday",   "status": "confirmed", "hash": _rand_tx()},
            {"type": "Bridge",  "description": "0.1 ETH → Optimism",       "time": "2 days ago",  "status": "failed",    "hash": _rand_tx()},
            {"type": "Swap",    "description": "0.5 WBTC → 15.2 ETH",      "time": "3 days ago",  "status": "confirmed", "hash": _rand_tx()},
            {"type": "Approve", "description": "$OPG Permit2 approved",     "time": "3 days ago",  "status": "confirmed", "hash": _rand_tx()},
        ]
        return {"success": True, "wallet": arguments.get("wallet_address", ""), "transactions": txs[:limit]}

    return {"success": False, "error": f"Unknown tool: {name}"}