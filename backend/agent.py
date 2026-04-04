"""
agent.py — Core openAgent AI using OpenGradient SDK.

Uses og.LLM.chat() with tool-calling for DeFi actions.
Handles multi-turn conversation, tool execution loop,
and returns structured responses to the FastAPI server.
"""

import asyncio
import json
import os
import logging
from typing import AsyncGenerator

import opengradient as og

from config import (
    OG_PRIVATE_KEY,
    OG_LLM_ENDPOINT,
    OG_MODEL,
    OG_SETTLEMENT,
    OG_APPROVAL_AMOUNT,
    SYSTEM_PROMPT,
    MAX_TOKENS,
    TEMPERATURE,
    MODEL_MAP,
)
from tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  SETTLEMENT MODE MAPPING
# ─────────────────────────────────────────────────────────────
SETTLEMENT_MAP = {
    "BATCH_HASHED":    og.x402SettlementMode.BATCH_HASHED,
    "INDIVIDUAL_FULL": og.x402SettlementMode.INDIVIDUAL_FULL,
    "PRIVATE":         og.x402SettlementMode.PRIVATE,
}

# ─────────────────────────────────────────────────────────────
#  MODEL ENUM MAPPING
# ─────────────────────────────────────────────────────────────
def _resolve_model(model_str: str) -> og.TEE_LLM:
    """Map model string to og.TEE_LLM enum, falling back to claude-sonnet."""
    enum_name = MODEL_MAP.get(model_str, "CLAUDE_SONNET_4_6")
    try:
        return getattr(og.TEE_LLM, enum_name)
    except AttributeError:
        logger.warning(f"Unknown model enum {enum_name}, falling back to CLAUDE_SONNET_4_6")
        return og.TEE_LLM.CLAUDE_SONNET_4_6


# ─────────────────────────────────────────────────────────────
#  AGENT CLASS
# ─────────────────────────────────────────────────────────────
class OpenAgent:
    """
    Wraps the OpenGradient LLM SDK and provides a clean chat() interface
    that handles:
      - Multi-turn conversation history
      - Tool-calling loop (swap, bridge, stake, balance, etc.)
      - Streaming responses
      - TEE proof / payment hash surfacing
    """

    def __init__(self):
        if not OG_PRIVATE_KEY:
            raise ValueError(
                "OG_PRIVATE_KEY is not set. Add it to your .env file. "
                "Your wallet needs $OPG tokens on Base Sepolia."
            )

        self.llm = og.LLM(private_key=OG_PRIVATE_KEY)
        self.model = _resolve_model(OG_MODEL)
        self.settlement = SETTLEMENT_MAP.get(OG_SETTLEMENT, og.x402SettlementMode.BATCH_HASHED)
        self._approved = False
        logger.info(f"OpenAgent initialised | model={OG_MODEL} | settlement={OG_SETTLEMENT}")

    async def ensure_approval(self):
        """Ensure Permit2 $OPG approval — skips silently if it fails."""
        if self._approved:
            return
        try:
            approval = self.llm.ensure_opg_approval(min_allowance=OG_APPROVAL_AMOUNT)
            self._approved = True
            logger.info(
                f"$OPG Permit2 approved | "
                f"before={approval.allowance_before} | "
                f"after={approval.allowance_after} | "
                f"tx={approval.tx_hash}"
            )
        except Exception as e:
            # Don't raise — approval failure should never block inference
            # The OG network may still process requests with existing allowance
            logger.warning(f"$OPG approval skipped: {e}")
            self._approved = True  # mark as done so we don't retry every message

    def _build_messages(self, history: list[dict], wallet_address: str | None = None) -> list[dict]:
        wallet_line = f"\nCONNECTED WALLET: {wallet_address}" if wallet_address and wallet_address != "not_connected" else "\nWALLET: Not connected"
        system = SYSTEM_PROMPT + wallet_line + "\nAlways use this wallet address when calling get_wallet_balance or other wallet tools."
        return [{"role": "system", "content": system}] + history

    async def chat(
        self,
        history: list[dict],
        model_override: str | None = None,
        wallet_address: str | None = None,
    ) -> dict:
        """
        Run one turn of the agent loop.

        Returns:
        {
            "content": str,          # the final text response
            "tool_calls": [...],     # list of tools that were called (may be empty)
            "tool_results": [...],   # results from each tool call
            "payment_hash": str,     # OG payment hash
            "model": str,
            "finish_reason": str,
        }
        """
        await self.ensure_approval()

        model = _resolve_model(model_override) if model_override else self.model

        # Strip internal keys before sending to LLM
        clean_history = [
            {k: v for k, v in m.items() if not k.startswith("_")}
            for m in history
        ]
        messages = self._build_messages(clean_history, wallet_address)
        logger.info(f"Chat | model={OG_MODEL} | messages={len(messages)} | wallet={wallet_address or 'none'}")

        tool_calls_made = []
        tool_results_made = []
        payment_hash = None
        final_content = ""

        logger.info(f"Chat request | model={OG_MODEL} | messages={len(messages)}")

        # ── First LLM call ──────────────────────────────────
        result = await self.llm.chat(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            x402_settlement_mode=self.settlement,
        )

        logger.info(f"OG response received | payment_hash={result.payment_hash}")
        payment_hash = result.payment_hash

        # chat_output may be a dict or an object depending on SDK version
        raw = result.chat_output
        if isinstance(raw, dict):
            output = raw
        else:
            # Convert object to dict
            output = {
                "role":       getattr(raw, "role", "assistant"),
                "content":    getattr(raw, "content", None),
                "tool_calls": getattr(raw, "tool_calls", None),
            }

        logger.info(f"Output content preview: {str(output.get('content',''))[:120]}")
        logger.info(f"Tool calls requested: {bool(output.get('tool_calls'))}")

        # ── Tool-calling loop ────────────────────────────────
        # If the LLM wants to call tools, execute them and send results back
        loop_limit = 4  # prevent infinite loops
        iterations = 0

        while output.get("tool_calls") and iterations < loop_limit:
            iterations += 1
            tool_calls = output["tool_calls"]

            # Add the assistant's tool-call message to the conversation
            messages.append({
                "role": "assistant",
                "content": output.get("content"),
                "tool_calls": tool_calls,
            })

            # Execute each tool call
            tool_result_messages = []
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info(f"Calling tool: {fn_name} args={fn_args}")
                # Inject wallet address for balance tool if available
                if fn_name == "get_wallet_balance" and wallet_address:
                    fn_args.setdefault("wallet_address", wallet_address)
                tool_result = execute_tool(fn_name, fn_args)
                logger.info(f"Tool result: {tool_result}")

                tool_calls_made.append({"name": fn_name, "args": fn_args})
                tool_results_made.append(tool_result)

                tool_result_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result),
                })

            messages.extend(tool_result_messages)

            # Second LLM call with tool results injected
            result = await self.llm.chat(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                x402_settlement_mode=self.settlement,
            )
            payment_hash = result.payment_hash
            raw = result.chat_output
            if isinstance(raw, dict):
                output = raw
            else:
                output = {
                    "role":       getattr(raw, "role", "assistant"),
                    "content":    getattr(raw, "content", None),
                    "tool_calls": getattr(raw, "tool_calls", None),
                }

        final_content = output.get("content") or ""

        # Safety fallback — should never be empty after a successful call
        if not final_content and not tool_calls_made:
            final_content = "I received your message but couldn't generate a response. Please try again."
            logger.warning("Empty content returned from OG LLM with no tool calls")

        return {
            "content":      final_content,
            "tool_calls":   tool_calls_made,
            "tool_results": tool_results_made,
            "payment_hash": payment_hash,
            "model":        OG_MODEL,
            "finish_reason": "stop",
        }

    async def stream_chat(
        self,
        history: list[dict],
        model_override: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming version of chat().
        Yields Server-Sent Event (SSE) strings.

        NOTE: Tool-calling with streaming requires a non-streaming first pass
        to resolve tool calls, then streams the final response.
        We implement a hybrid: tool calls run synchronously, final answer streams.
        """
        await self.ensure_approval()

        model = _resolve_model(model_override) if model_override else self.model
        messages = self._build_messages(history)

        # ── Check if tools will be needed (non-streaming first pass) ──
        probe = await self.llm.chat(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=50,          # short probe to detect tool calls
            temperature=TEMPERATURE,
            x402_settlement_mode=self.settlement,
        )

        output = probe.chat_output

        if output.get("tool_calls"):
            # Run the full tool loop non-streaming
            full = await self.chat(history, model_override)
            # Yield the result as a single SSE payload
            yield f"data: {json.dumps({'type': 'full', **full})}\n\n"
            return

        # ── No tools needed — stream the response ───────────
        payment_hash = probe.payment_hash
        messages_for_stream = self._build_messages(history)

        stream = await self.llm.chat(
            model=model,
            messages=messages_for_stream,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            x402_settlement_mode=self.settlement,
            stream=True,
        )

        full_text = ""
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'payment_hash': payment_hash, 'model': OG_MODEL, 'tool_calls': [], 'tool_results': []})}\n\n"


# ─────────────────────────────────────────────────────────────
#  SINGLETON — reused across all requests
# ─────────────────────────────────────────────────────────────
_agent_instance: OpenAgent | None = None


def get_agent() -> OpenAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = OpenAgent()
    return _agent_instance