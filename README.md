# openAgent — Powered by OpenGradient

A full-stack DeFi AI agent that uses the OpenGradient SDK for verifiable LLM inference via TEE (Trusted Execution Environments). The agent can converse naturally, parse DeFi intents (swap, bridge, stake, balance), and execute on-chain actions — all with cryptographic proof of every decision.

---

## Architecture

```
openagent/
├── backend/
│   ├── main.py              # FastAPI server — entry point
│   ├── agent.py             # Core AI agent (OpenGradient LLM + tools)
│   ├── tools.py             # DeFi tool definitions (swap, bridge, stake, etc.)
│   ├── wallet.py            # Wallet & chain utilities (web3)
│   ├── config.py            # Config & environment variables
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── public/
│   │   └── index.html       # App shell
│   └── src/
│       ├── app.js           # Main frontend JS
│       ├── chat.js          # Chat UI & message rendering
│       ├── screens.js       # Swap / Bridge / Stake / Portfolio screens
│       └── style.css        # All styles
└── README.md
```

---

## Setup

### 1. Prerequisites
- Python 3.10+
- Node.js (optional, for a dev server)
- MetaMask or any EVM wallet
- $OPG testnet tokens on Base Sepolia → https://faucet.opengradient.ai

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:
```
OG_PRIVATE_KEY=0x...          # Wallet private key (Base Sepolia, funded with $OPG)
OG_MODEL=anthropic/claude-sonnet-4-6
OG_SETTLEMENT=BATCH_HASHED    # BATCH_HASHED | INDIVIDUAL_FULL | PRIVATE
PORT=8000
```

Start the server:
```bash
python main.py
```

The API will be live at `http://localhost:8000`

### 3. Frontend

Open `frontend/public/index.html` in a browser, or serve it:
```bash
cd frontend/public
python -m http.server 3000
```

Then visit `http://localhost:3000`

---

## How it works

1. **User sends a message** in the chat UI
2. **Frontend** POSTs to `/api/chat` with the message + conversation history
3. **Backend agent** sends the full conversation to OpenGradient's TEE-verified LLM (`og.LLM.chat()`) with DeFi tools attached
4. **LLM decides** whether to respond conversationally or call a DeFi tool (swap, bridge, stake, etc.)
5. If a **tool is called**, the backend executes it (or returns a confirmation card to the frontend)
6. **Response streams back** with TEE proof hash and payment hash
7. **Frontend renders** a chat bubble or an actionable DeFi card

---

## OpenGradient SDK Integration

```python
import opengradient as og

llm = og.LLM(private_key=os.environ["OG_PRIVATE_KEY"])
llm.ensure_opg_approval(opg_amount=5.0)  # approve $OPG for Permit2

result = await llm.chat(
    model=og.TEE_LLM.CLAUDE_SONNET_4_6,
    messages=conversation_history,
    tools=DEFI_TOOLS,             # swap, bridge, stake, balance, etc.
    tool_choice="auto",
    x402_settlement_mode=og.x402SettlementMode.BATCH_HASHED
)
```

Every inference call returns a `payment_hash` — the on-chain record that this exact prompt was processed by the OpenGradient TEE.

---

## Supported DeFi Actions (via tool calling)

| Tool | Description |
|------|-------------|
| `swap_tokens` | Swap any token pair — amount + from + to parsed by LLM |
| `bridge_tokens` | Bridge assets cross-chain via Hop Protocol |
| `stake_tokens` | Stake ETH on Lido, Rocket Pool, Aave, or Curve |
| `get_wallet_balance` | Fetch live token balances for the connected wallet |
| `get_token_price` | Get current price for any supported token |
| `get_tx_history` | Fetch recent transaction history |

---

## Wallet Connection (Frontend)

The frontend uses `window.ethereum` (MetaMask / any EVM wallet injected provider):

1. Connect wallet via MetaMask
2. Switch to **Base Sepolia** (Chain ID: 84532) for $OPG payments
3. All transaction signing is done by the wallet — private key never leaves the user's device

---

## OpenGradient Network Details

| Property | Value |
|----------|-------|
| Payment Network | Base Sepolia |
| Chain ID | 84532 |
| $OPG Token | `0x240b09731D96979f50B2C649C9CE10FcF9C7987F` |
| LLM Endpoint | `https://llm.opengradient.ai` |
| Settlement | BATCH_HASHED (default) |
| Verification | TEE (Intel TDX) |
