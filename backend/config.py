"""
config.py — openAgent configuration
Loads environment variables and exposes typed settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenGradient ──────────────────────────────────────────────
OG_PRIVATE_KEY: str = os.getenv("OG_PRIVATE_KEY", "")
OG_LLM_ENDPOINT: str = os.getenv("OG_LLM_ENDPOINT", "https://llm.opengradient.ai")

# TEE_LLM model string — maps to og.TEE_LLM enum values
OG_MODEL: str = os.getenv("OG_MODEL", "anthropic/claude-sonnet-4-6")

# Settlement mode: BATCH_HASHED | INDIVIDUAL_FULL | PRIVATE
OG_SETTLEMENT: str = os.getenv("OG_SETTLEMENT", "BATCH_HASHED")

# How much $OPG to pre-approve for Permit2 inference payments
OG_APPROVAL_AMOUNT: float = float(os.getenv("OG_APPROVAL_AMOUNT", "10.0"))

# ── Network ───────────────────────────────────────────────────
BASE_SEPOLIA_CHAIN_ID: int = 84532
BASE_SEPOLIA_RPC: str = os.getenv("BASE_SEPOLIA_RPC", "https://base-sepolia.g.alchemy.com/v2/demo")
OPG_TOKEN_ADDRESS: str = "0x240b09731D96979f50B2C649C9CE10FcF9C7987F"

# ── Server ────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8000"))
HOST: str = os.getenv("HOST", "0.0.0.0")
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

# ── Agent behaviour ───────────────────────────────────────────
AGENT_NAME: str = "openAgent"
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.4"))

# System prompt injected at the start of every conversation
SYSTEM_PROMPT: str = """You are openAgent, a highly intelligent and friendly DeFi AI agent powered by OpenGradient's decentralised TEE inference network.

PERSONALITY:
- You are warm, conversational, and genuinely helpful — not a scripted bot.
- You can talk about anything: crypto markets, general knowledge, life advice, jokes. Be human.
- When you don't know something, say so honestly. Never hallucinate prices or data.
- You have opinions and can share them when asked (e.g. "I think ETH is undervalued right now but DYOR").

DEFI CAPABILITIES:
You have real tools available: swap_tokens, bridge_tokens, stake_tokens, get_wallet_balance, get_token_price, get_tx_history.
- When a user clearly wants to do a DeFi action, call the appropriate tool.
- Extract amounts and token names intelligently from natural language.
  e.g. "swap half my ETH to USDC" → call get_wallet_balance first, then swap half.
  e.g. "bridge a bit of ETH to L2" → ask which chain and how much before acting.
- Always show users what you're about to do BEFORE executing. Never surprise them.
- For ambiguous requests, ask a clarifying question rather than guessing.

IMPORTANT RULES:
- Never claim to have executed a transaction unless the tool confirms it.
- Always mention the TEE verification and payment hash when a tool runs successfully.
- If the user's wallet isn't connected, remind them to connect before you can execute actions.
- Prices you quote are from your tools — always mention they are live quotes.
- You are running on OpenGradient's network. Every inference is TEE-verified and settled on Base Sepolia with $OPG tokens.

CONVERSATION STYLE:
- Keep responses concise unless depth is needed.
- Use markdown sparingly (bold for key terms, code blocks for tx hashes).
- Be direct. No filler phrases like "Certainly!" or "Of course!".
"""

# Model enum mapping
MODEL_MAP: dict[str, str] = {
    "anthropic/claude-sonnet-4-6": "CLAUDE_SONNET_4_6",
    "anthropic/claude-haiku-4-5": "CLAUDE_HAIKU_4_5",
    "openai/gpt-4.1-2025-04-14": "GPT_4_1_2025_04_14",
    "openai/gpt-5": "GPT_5",
    "google/gemini-2.5-flash": "GEMINI_2_5_FLASH",
    "x-ai/grok-4": "GROK_4",
}
