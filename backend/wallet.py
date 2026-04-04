"""
wallet.py — EVM wallet & chain utilities for openAgent.

Handles:
  - Web3 connection to Base Sepolia (OpenGradient payment network)
  - $OPG token balance and allowance checks
  - Wallet balance fetching (ETH + ERC-20 tokens)
  - Transaction signing helpers
  - Permit2 approval status check
  - Chain switching / network validation
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

from config import (
    OG_PRIVATE_KEY,
    BASE_SEPOLIA_CHAIN_ID,
    BASE_SEPOLIA_RPC,
    OPG_TOKEN_ADDRESS,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  ABI SNIPPETS  (minimal ERC-20 ABI)
# ─────────────────────────────────────────────────────────────
ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner",   "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
    {
        "name": "symbol",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
    },
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount",  "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
]

# Permit2 contract address (Uniswap, deployed on most EVM chains)
PERMIT2_ADDRESS = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

# Known ERC-20 tokens on Base Sepolia (testnet equivalents)
KNOWN_TOKENS: dict[str, dict] = {
    "USDC": {
        "address":  "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "decimals": 6,
    },
    "WETH": {
        "address":  "0x4200000000000000000000000000000000000006",
        "decimals": 18,
    },
    "OPG": {
        "address":  OPG_TOKEN_ADDRESS,
        "decimals": 18,
    },
}


# ─────────────────────────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────────────────────────
@dataclass
class TokenBalance:
    symbol:   str
    address:  str
    raw:      int       # raw on-chain amount (in smallest unit)
    decimals: int
    amount:   float     # human-readable
    usd_value: float = 0.0


@dataclass
class WalletInfo:
    address:    str
    eth_balance: float
    eth_balance_wei: int
    chain_id:   int
    is_correct_chain: bool
    opg_balance: float
    opg_allowance_permit2: float
    token_balances: list[TokenBalance]


# ─────────────────────────────────────────────────────────────
#  WEB3 CONNECTION
# ─────────────────────────────────────────────────────────────
def get_web3() -> Web3:
    """
    Returns a Web3 instance connected to Base Sepolia.
    Injects POA middleware since Base Sepolia uses a POA consensus.
    """
    w3 = Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        raise ConnectionError(
            f"Cannot connect to Base Sepolia RPC at {BASE_SEPOLIA_RPC}. "
            "Check your internet connection."
        )
    return w3


def get_account() -> Optional[Account]:
    """
    Returns the local signing account derived from OG_PRIVATE_KEY.
    Returns None if no private key is configured.
    """
    if not OG_PRIVATE_KEY:
        return None
    try:
        return Account.from_key(OG_PRIVATE_KEY)
    except Exception as e:
        logger.error(f"Invalid private key: {e}")
        return None


# ─────────────────────────────────────────────────────────────
#  BALANCE CHECKS
# ─────────────────────────────────────────────────────────────
def get_eth_balance(address: str) -> tuple[float, int]:
    """
    Returns (human_readable_ETH, wei_amount) for a given address.
    """
    w3 = get_web3()
    checksum_addr = Web3.to_checksum_address(address)
    wei = w3.eth.get_balance(checksum_addr)
    eth = float(Web3.from_wei(wei, "ether"))
    return eth, wei


def get_opg_balance(address: str) -> float:
    """
    Returns the $OPG token balance (human-readable) for a given address.
    """
    w3 = get_web3()
    token = w3.eth.contract(
        address=Web3.to_checksum_address(OPG_TOKEN_ADDRESS),
        abi=ERC20_ABI,
    )
    raw      = token.functions.balanceOf(Web3.to_checksum_address(address)).call()
    decimals = token.functions.decimals().call()
    return raw / (10 ** decimals)


def get_opg_permit2_allowance(address: str) -> float:
    """
    Returns the current Permit2 allowance for $OPG spending.
    Used to determine if ensure_opg_approval() needs to send a tx.
    """
    w3 = get_web3()
    token = w3.eth.contract(
        address=Web3.to_checksum_address(OPG_TOKEN_ADDRESS),
        abi=ERC20_ABI,
    )
    raw      = token.functions.allowance(
        Web3.to_checksum_address(address),
        Web3.to_checksum_address(PERMIT2_ADDRESS),
    ).call()
    decimals = token.functions.decimals().call()
    return raw / (10 ** decimals)


def get_erc20_balance(token_address: str, wallet_address: str) -> TokenBalance:
    """
    Returns a TokenBalance for any ERC-20 token.
    """
    w3 = get_web3()
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=ERC20_ABI,
    )
    raw      = contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    decimals = contract.functions.decimals().call()
    symbol   = contract.functions.symbol().call()
    amount   = raw / (10 ** decimals)
    return TokenBalance(
        symbol=symbol,
        address=token_address,
        raw=raw,
        decimals=decimals,
        amount=amount,
    )


def get_full_wallet_info(address: str) -> WalletInfo:
    """
    Returns a complete WalletInfo snapshot for the given address:
      - ETH balance
      - $OPG balance + Permit2 allowance
      - All known ERC-20 token balances
      - Whether the wallet is on the correct chain (Base Sepolia)
    """
    w3 = get_web3()
    chain_id = w3.eth.chain_id

    eth_amount, eth_wei = get_eth_balance(address)

    try:
        opg_bal  = get_opg_balance(address)
        opg_alw  = get_opg_permit2_allowance(address)
    except Exception as e:
        logger.warning(f"Could not fetch $OPG balances: {e}")
        opg_bal = 0.0
        opg_alw = 0.0

    token_balances: list[TokenBalance] = []
    for symbol, info in KNOWN_TOKENS.items():
        if symbol == "OPG":
            # already fetched above
            token_balances.append(TokenBalance(
                symbol="OPG",
                address=OPG_TOKEN_ADDRESS,
                raw=int(opg_bal * 1e18),
                decimals=18,
                amount=opg_bal,
            ))
            continue
        try:
            bal = get_erc20_balance(info["address"], address)
            token_balances.append(bal)
        except Exception as e:
            logger.warning(f"Could not fetch {symbol} balance: {e}")

    return WalletInfo(
        address=address,
        eth_balance=eth_amount,
        eth_balance_wei=eth_wei,
        chain_id=chain_id,
        is_correct_chain=(chain_id == BASE_SEPOLIA_CHAIN_ID),
        opg_balance=opg_bal,
        opg_allowance_permit2=opg_alw,
        token_balances=token_balances,
    )


# ─────────────────────────────────────────────────────────────
#  CHAIN VALIDATION
# ─────────────────────────────────────────────────────────────
def validate_chain() -> dict:
    """
    Confirms the Web3 connection is on Base Sepolia.
    Returns a status dict surfaced by /api/health.
    """
    try:
        w3 = get_web3()
        chain_id    = w3.eth.chain_id
        block       = w3.eth.block_number
        is_correct  = chain_id == BASE_SEPOLIA_CHAIN_ID
        return {
            "connected":       True,
            "chain_id":        chain_id,
            "expected_chain":  BASE_SEPOLIA_CHAIN_ID,
            "correct_chain":   is_correct,
            "latest_block":    block,
            "rpc":             BASE_SEPOLIA_RPC,
        }
    except Exception as e:
        return {
            "connected":  False,
            "error":      str(e),
            "rpc":        BASE_SEPOLIA_RPC,
        }


# ─────────────────────────────────────────────────────────────
#  TX HELPERS
# ─────────────────────────────────────────────────────────────
def build_tx_params(from_address: str, value_wei: int = 0) -> dict:
    """
    Returns a base transaction parameter dict with gas estimate and nonce.
    Used when constructing raw transactions before signing.
    """
    w3 = get_web3()
    return {
        "from":     Web3.to_checksum_address(from_address),
        "nonce":    w3.eth.get_transaction_count(Web3.to_checksum_address(from_address)),
        "gasPrice": w3.eth.gas_price,
        "chainId":  BASE_SEPOLIA_CHAIN_ID,
        "value":    value_wei,
    }


def sign_and_send(tx: dict) -> str:
    """
    Signs a transaction with OG_PRIVATE_KEY and broadcasts it.
    Returns the transaction hash (hex string).

    In production, signing should happen in the user's browser wallet (MetaMask),
    not server-side. This is provided for backend-initiated txs only
    (e.g. $OPG Permit2 approvals, workflow deployments).
    """
    account = get_account()
    if not account:
        raise ValueError("No OG_PRIVATE_KEY configured for server-side signing.")

    w3       = get_web3()
    signed   = account.sign_transaction(tx)
    tx_hash  = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt  = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt.status != 1:
        raise RuntimeError(f"Transaction failed: {tx_hash.hex()}")

    logger.info(f"Transaction confirmed: {tx_hash.hex()} | block={receipt.blockNumber}")
    return tx_hash.hex()


def estimate_gas(tx: dict) -> int:
    """Estimate gas for a transaction."""
    w3 = get_web3()
    return w3.eth.estimate_gas(tx)


def get_gas_price_gwei() -> float:
    """Returns current gas price in Gwei."""
    w3 = get_web3()
    return float(Web3.from_wei(w3.eth.gas_price, "gwei"))


# ─────────────────────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────────────────────
def is_valid_address(address: str) -> bool:
    """Returns True if the string is a valid EVM address."""
    try:
        Web3.to_checksum_address(address)
        return True
    except Exception:
        return False


def short_address(address: str) -> str:
    """Returns a shortened address like 0x3f8a…9a1b."""
    if not address or len(address) < 10:
        return address
    return address[:6] + "…" + address[-4:]
