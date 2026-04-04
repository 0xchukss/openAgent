"""
main.py — FastAPI server for openAgent.

Endpoints:
  POST /api/chat          — main chat endpoint (full response)
  POST /api/chat/stream   — streaming SSE chat
  GET  /api/health        — health check + OG network status
  GET  /api/config        — frontend config (model, network info)
  POST /api/tool/execute  — frontend calls this after user confirms a tx
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config as cfg
from agent import get_agent
from tools import execute_tool, SUPPORTED_CHAINS, STAKE_PROTOCOLS, MOCK_PRICES_USD
from wallet import (
    validate_chain,
    get_full_wallet_info,
    get_eth_balance,
    get_opg_balance,
    get_opg_permit2_allowance,
    get_gas_price_gwei,
    is_valid_address,
    short_address,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  STARTUP / SHUTDOWN
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("openAgent starting up…")

    # Initialise the agent (validates private key exists)
    try:
        get_agent()
        logger.info("OpenAgent instance created.")
    except ValueError as e:
        logger.error(f"Config error: {e}")

    # $OPG Permit2 approval — runs in background so a slow/offline RPC
    # doesn't block the server from starting. Approval will be retried
    # automatically on the first inference call via ensure_approval().
    async def _approve_in_background():
        try:
            agent = get_agent()
            await agent.ensure_approval()
            logger.info("$OPG Permit2 approval confirmed. Agent fully ready.")
        except Exception as e:
            logger.warning(
                f"$OPG approval deferred: {e}\n"
                "This is usually a network/RPC issue. The server will still start. "
                "Approval will be retried on the first chat request.\n"
                "Fix: add BASE_SEPOLIA_RPC=https://base-sepolia.g.alchemy.com/v2/demo to your .env"
            )

    asyncio.create_task(_approve_in_background())
    yield
    logger.info("openAgent shutting down.")


# ─────────────────────────────────────────────────────────────
#  APP
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="openAgent API",
    description="DeFi AI Agent powered by OpenGradient TEE inference",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
#  REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str               # "user" | "assistant" | "system"
    content: str

class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., description="Full conversation history")
    wallet_address: str | None = Field(None, description="Connected wallet address")
    model: str | None = Field(None, description="Override LLM model")

class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: dict
    wallet_address: str | None = None


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def messages_to_dicts(messages: list[Message]) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


# ─────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check — returns OG network status and chain validation."""
    opg_key_set  = bool(cfg.OG_PRIVATE_KEY)
    chain_status = validate_chain()
    return {
        "status":           "ok",
        "agent":            cfg.AGENT_NAME,
        "og_key_configured": opg_key_set,
        "og_model":         cfg.OG_MODEL,
        "og_settlement":    cfg.OG_SETTLEMENT,
        "og_network": {
            "chain_id":  cfg.BASE_SEPOLIA_CHAIN_ID,
            "rpc":       cfg.BASE_SEPOLIA_RPC,
            "opg_token": cfg.OPG_TOKEN_ADDRESS,
            "endpoint":  cfg.OG_LLM_ENDPOINT,
        },
        "chain":     chain_status,
        "timestamp": int(time.time()),
    }


@app.get("/api/wallet/{address}")
async def wallet_info(address: str):
    """
    Returns full wallet snapshot:
      - ETH balance
      - $OPG balance + Permit2 allowance
      - All known ERC-20 balances
      - Chain validation
    """
    if not is_valid_address(address):
        raise HTTPException(status_code=400, detail=f"Invalid EVM address: {address}")
    try:
        info = get_full_wallet_info(address)
        return {
            "address":              info.address,
            "short_address":        short_address(info.address),
            "eth_balance":          info.eth_balance,
            "chain_id":             info.chain_id,
            "correct_chain":        info.is_correct_chain,
            "opg_balance":          info.opg_balance,
            "opg_permit2_allowance": info.opg_allowance_permit2,
            "token_balances": [
                {
                    "symbol":    b.symbol,
                    "address":   b.address,
                    "amount":    b.amount,
                    "decimals":  b.decimals,
                }
                for b in info.token_balances
            ],
            "gas_price_gwei": get_gas_price_gwei(),
        }
    except Exception as e:
        logger.error(f"Wallet info error for {address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """Returns non-sensitive config for the frontend."""
    return {
        "agent_name": cfg.AGENT_NAME,
        "model": cfg.OG_MODEL,
        "settlement": cfg.OG_SETTLEMENT,
        "network": {
            "name": "OpenGradient / Base Sepolia",
            "chain_id": cfg.BASE_SEPOLIA_CHAIN_ID,
            "opg_token_address": cfg.OPG_TOKEN_ADDRESS,
            "opg_token_symbol": "$OPG",
        },
        "supported_chains": SUPPORTED_CHAINS,
        "stake_protocols": {k: {"apy": v["apy"], "receive_token": v["receive_token"]} for k, v in STAKE_PROTOCOLS.items()},
        "token_prices": MOCK_PRICES_USD,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint. Accepts full conversation history,
    runs the OpenGradient agent, returns the response.
    """
    try:
        agent = get_agent()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    history = messages_to_dicts(req.messages)

    # Pass wallet address as a top-level field the agent can read
    # rather than injecting into message content
    try:
        result = await agent.chat(
            history,
            model_override=req.model,
            wallet_address=req.wallet_address,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "content": f"⚠ Agent error: {str(e)}\n\nCheck the backend terminal for details.",
                "tool_calls": [],
                "tool_results": [],
                "payment_hash": None,
                "model": cfg.OG_MODEL,
                "finish_reason": "error",
            }
        )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming SSE version of /api/chat.
    The frontend should consume this with EventSource or fetch + ReadableStream.
    """
    try:
        agent = get_agent()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    history = messages_to_dicts(req.messages)

    async def event_generator():
        try:
            async for chunk in agent.stream_chat(history, model_override=req.model):
                yield chunk
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/tool/execute")
async def tool_execute(req: ToolExecuteRequest):
    """
    Execute a DeFi tool directly from the frontend (after user confirmation).
    In production this is where you'd sign + broadcast the actual transaction.
    """
    logger.info(f"Direct tool execute: {req.tool_name} | args={req.arguments}")
    try:
        result = execute_tool(req.tool_name, req.arguments)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Tool execute error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prices")
async def get_prices():
    """Return current mock token prices."""
    return {"prices": MOCK_PRICES_USD, "source": "OpenGradient Oracle", "timestamp": int(time.time())}


# ─────────────────────────────────────────────────────────────
#  SERVE FRONTEND (static files)
# ─────────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
    logger.info(f"Serving frontend from {frontend_path}")


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=cfg.HOST,
        port=cfg.PORT,
        reload=True,
        log_level="info",
    )