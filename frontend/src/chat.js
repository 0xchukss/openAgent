/**
 * chat.js — Chat UI: rendering messages, action cards, tool results.
 * Imported by app.js
 */

import { TOK_COLORS, TOK_SYMBOLS, fmtNum } from './app.js';

const msgsEl = () => document.getElementById('msgs');

// ── scroll to bottom ──────────────────────────────────────────
function scrollBottom() {
  const el = msgsEl();
  if (el) el.scrollTop = el.scrollHeight;
}

// ── add user message bubble ───────────────────────────────────
export function addUserMsg(text) {
  const area = msgsEl();
  const w = document.createElement('div');
  w.className = 'msg u';
  w.innerHTML = `
    <div class="av u">YOU</div>
    <div class="bwrap">
      <div class="bub u">${escHtml(text)}</div>
    </div>`;
  area.appendChild(w);
  scrollBottom();
}

// ── add AI message bubble (with optional card) ────────────────
export function addAiMsg(html, card = '') {
  const area = msgsEl();
  const w = document.createElement('div');
  w.className = 'msg';
  w.innerHTML = `
    <div class="av ai">OG</div>
    <div class="bwrap">
      <div class="bub ai">${html}</div>
      ${card}
    </div>`;
  area.appendChild(w);
  scrollBottom();
  return w;
}

// ── typing indicator ──────────────────────────────────────────
export function showTyping() {
  const area = msgsEl();
  const w = document.createElement('div');
  w.className = 'msg';
  w.id = 'typing-indicator';
  w.innerHTML = `
    <div class="av ai">OG</div>
    <div class="bwrap">
      <div class="typing">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    </div>`;
  area.appendChild(w);
  scrollBottom();
  document.getElementById('infer-status').style.display = 'flex';
}

export function hideTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
  document.getElementById('infer-status').style.display = 'none';
}

// ── OG proof tag ──────────────────────────────────────────────
function ogProofTag(paymentHash, model) {
  const short = paymentHash
    ? paymentHash.slice(0, 10) + '…' + paymentHash.slice(-6)
    : 'pending';
  return `
    <div class="og-proof">
      <div class="og-proof-dot"></div>
      ⬡ OG TEE · ${model || 'claude-sonnet-4-6'} · payment: <code>${short}</code>
    </div>`;
}

// ── render full API response ──────────────────────────────────
export function renderAgentResponse(resp) {
  const { content, tool_calls, tool_results, payment_hash, model } = resp;

  const proof = ogProofTag(payment_hash, model);

  // If there were tool calls, render cards for each result
  if (tool_calls && tool_calls.length > 0) {
    let card = '';
    tool_calls.forEach((tc, i) => {
      const result = tool_results[i] || {};
      card += buildActionCard(tc.name, tc.args, result);
    });

    const text = content
      ? `${markdownToHtml(content)}<br>${proof}`
      : proof;

    addAiMsg(text, card);
  } else {
    addAiMsg(markdownToHtml(content) + '<br>' + proof);
  }
}

// ── build action card for a tool result ──────────────────────
function buildActionCard(toolName, args, result) {
  if (!result.success) {
    return `<div class="action-card">
      <div class="ac-top"><div class="ac-dot"></div>${toolName}</div>
      <div style="color:var(--re);font-size:12px;">⚠ ${escHtml(result.error || 'Unknown error')}</div>
    </div>`;
  }

  switch (toolName) {
    case 'swap_tokens':    return swapCard(result);
    case 'bridge_tokens':  return bridgeCard(result);
    case 'stake_tokens':   return stakeCard(result);
    case 'get_wallet_balance': return balanceCard(result);
    case 'get_tx_history': return historyCard(result);
    case 'get_token_price': return priceCard(result);
    default: return genericCard(toolName, result);
  }
}

// ── SWAP card ──────────────────────────────────────────────────
function swapCard(r) {
  const id = 'card-' + Date.now();
  const fc = TOK_COLORS[r.from_token] || { bg: '#555', fg: '#fff' };
  const tc = TOK_COLORS[r.to_token]  || { bg: '#555', fg: '#fff' };
  const fs = TOK_SYMBOLS[r.from_token] || r.from_token[0];
  const ts = TOK_SYMBOLS[r.to_token]  || r.to_token[0];

  return `<div class="action-card" id="${id}">
    <div class="ac-top"><div class="ac-dot"></div>Swap Quote · ${r.route || 'Uniswap v3'}</div>
    <div class="tok-row">
      <div class="tok-chip">
        <div class="tok-icon" style="background:${fc.bg};color:${fc.fg}">${fs}</div>
        ${r.from_token}
      </div>
      <div class="ac-arrow">→</div>
      <div class="tok-chip">
        <div class="tok-icon" style="background:${tc.bg};color:${tc.fg}">${ts}</div>
        ${r.to_token}
      </div>
    </div>
    <div class="ac-bignum">${fmtNum(r.input_amount)} ${r.from_token}</div>
    <div class="ac-smallnum">≈ ${fmtNum(r.output_amount)} ${r.to_token} · $${fmtNum(r.from_usd)}</div>
    <div class="ac-meta">
      <div class="ac-meta-item">Rate <b>${fmtNum(r.rate)}</b></div>
      <div class="ac-meta-item">Fee <b>$${r.fee_usd}</b></div>
      <div class="ac-meta-item">Impact <b>${r.price_impact}%</b></div>
      <div class="ac-meta-item">Gas <b>~$${r.gas_usd}</b></div>
    </div>
    <div class="ac-og-tag">⬡ OG TEE Settlement: BATCH_HASHED</div>
    <button class="ac-btn ac-btn-primary" id="btn-${id}"
      onclick="window.confirmTx('${id}','swap_tokens',${escJson(r)})">
      Confirm Swap
    </button>
  </div>`;
}

// ── BRIDGE card ───────────────────────────────────────────────
function bridgeCard(r) {
  const id = 'card-' + Date.now();
  const fc = TOK_COLORS[r.token] || { bg: '#555', fg: '#fff' };
  const fs = TOK_SYMBOLS[r.token] || r.token[0];
  return `<div class="action-card" id="${id}">
    <div class="ac-top"><div class="ac-dot"></div>Bridge · ${r.protocol}</div>
    <div class="tok-row">
      <div class="tok-chip">
        <div class="tok-icon" style="background:${fc.bg};color:${fc.fg}">${fs}</div>
        Base Sepolia
      </div>
      <div class="ac-arrow">→</div>
      <div class="tok-chip">
        <div class="tok-icon" style="background:#28a0f0;color:#fff">→</div>
        ${r.destination_chain}
      </div>
    </div>
    <div class="ac-bignum">${fmtNum(r.amount)} ${r.token}</div>
    <div class="ac-smallnum">You receive: ${fmtNum(r.receive_amount)} ${r.token} on ${r.destination_chain}</div>
    <div class="ac-meta">
      <div class="ac-meta-item">ETA <b>~${r.eta_minutes} min</b></div>
      <div class="ac-meta-item">Bridge fee <b>${fmtNum(r.bridge_fee)} ${r.token}</b></div>
      <div class="ac-meta-item">Gas <b>~$${r.gas_usd}</b></div>
    </div>
    <div class="ac-og-tag">⬡ OG TEE Settlement: BATCH_HASHED</div>
    <button class="ac-btn ac-btn-primary" id="btn-${id}"
      onclick="window.confirmTx('${id}','bridge_tokens',${escJson(r)})">
      Confirm Bridge to ${r.destination_chain}
    </button>
  </div>`;
}

// ── STAKE card ────────────────────────────────────────────────
function stakeCard(r) {
  const id = 'card-' + Date.now();
  return `<div class="action-card" id="${id}">
    <div class="ac-top"><div class="ac-dot"></div>Stake · ${r.protocol}</div>
    <div class="tok-row">
      <div class="tok-chip">
        <div class="tok-icon" style="background:#627eea;color:#fff">Ξ</div>
        ${fmtNum(r.amount)} ${r.token}
      </div>
      <div class="ac-arrow">→</div>
      <div class="tok-chip">
        <div class="tok-icon" style="background:#00a3ff;color:#fff">st</div>
        ${r.receive_token}
      </div>
    </div>
    <div class="ac-bignum">${fmtNum(r.receive_amount)} ${r.receive_token}</div>
    <div class="ac-meta">
      <div class="ac-meta-item">APY <b style="color:var(--gr)">${r.apy}%</b></div>
      <div class="ac-meta-item">Annual yield <b>${fmtNum(r.annual_yield)} ${r.token}</b></div>
      <div class="ac-meta-item">Gas <b>~$${r.gas_usd}</b></div>
    </div>
    <div class="ac-og-tag">⬡ OG TEE Settlement: BATCH_HASHED</div>
    <button class="ac-btn ac-btn-primary" id="btn-${id}"
      onclick="window.confirmTx('${id}','stake_tokens',${escJson(r)})">
      Confirm Stake on ${r.protocol}
    </button>
  </div>`;
}

// ── BALANCE card ──────────────────────────────────────────────
function balanceCard(r) {
  const items = (r.balances || []).map(b => `
    <div class="bal-item">
      <div class="bal-sym">${b.token}</div>
      <div class="bal-amt">${fmtNum(b.amount)}</div>
      <div class="bal-usd">$${fmtNum(b.usd_value)}</div>
    </div>`).join('');

  return `<div class="action-card" style="width:300px">
    <div class="ac-top"><div class="ac-dot"></div>Portfolio · ${r.wallet}</div>
    <div class="bal-grid">${items}</div>
    <div class="bal-total">Total: <b style="color:var(--gr)">$${fmtNum(r.total_usd)}</b></div>
  </div>`;
}

// ── TX HISTORY card ───────────────────────────────────────────
function historyCard(r) {
  const rows = (r.transactions || []).map(tx => `
    <div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--bo)">
      <div style="flex:1">
        <div style="font-size:12px;font-weight:600">${tx.type}</div>
        <div style="font-size:10.5px;color:var(--t3);font-family:'Space Mono',monospace">${tx.description} · ${tx.time}</div>
      </div>
      <div class="tx-badge ${tx.status === 'confirmed' ? 'tx-ok' : 'tx-fail'}">
        ${tx.status === 'confirmed' ? '✓' : '✗'} ${tx.status}
      </div>
    </div>`).join('');

  return `<div class="action-card" style="width:310px">
    <div class="ac-top"><div class="ac-dot"></div>Recent Transactions</div>
    ${rows}
  </div>`;
}

// ── PRICE card ────────────────────────────────────────────────
function priceCard(r) {
  const rows = Object.entries(r.prices_usd || {}).map(([tok, price]) =>
    `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--bo);font-family:'Space Mono',monospace;font-size:12px">
       <span>${tok}</span><span style="color:var(--gr)">$${fmtNum(price)}</span>
     </div>`
  ).join('');

  return `<div class="action-card">
    <div class="ac-top"><div class="ac-dot"></div>Token Prices · OG Oracle</div>
    ${rows}
  </div>`;
}

// ── GENERIC card ──────────────────────────────────────────────
function genericCard(name, r) {
  return `<div class="action-card">
    <div class="ac-top"><div class="ac-dot"></div>${name}</div>
    <pre style="font-size:10px;color:var(--t2);overflow:auto;max-height:120px">${JSON.stringify(r, null, 2)}</pre>
  </div>`;
}

// ── confirm transaction (called from card button) ─────────────
window.confirmTx = async function (cardId, toolName, result) {
  const btn = document.getElementById('btn-' + cardId);
  if (!btn) return;
  btn.className = 'ac-btn ac-btn-wait';
  btn.textContent = 'Waiting for wallet signature…';

  try {
    // In production: sign + broadcast via window.ethereum here
    // For now: call backend /api/tool/execute to simulate
    const res = await fetch('/api/tool/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool_name: toolName, arguments: result }),
    });
    const data = await res.json();
    await new Promise(r => setTimeout(r, 1400));
    const mockTx = '0x' + Array.from({ length: 12 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
    btn.className = 'ac-btn ac-btn-done';
    btn.textContent = `✓ Confirmed · tx: ${mockTx}`;

    // Add OG tx hash below the card
    const card = document.getElementById(cardId);
    if (card) {
      const tag = document.createElement('div');
      tag.style.cssText = 'font-size:10px;color:#c084fc;font-family:"Space Mono",monospace;margin-top:8px';
      tag.textContent = '⬡ OG Proof Tx: ' + mockTx;
      card.appendChild(tag);
    }
  } catch (e) {
    btn.className = 'ac-btn ac-btn-primary';
    btn.textContent = 'Retry — Error: ' + e.message;
  }
};

// ── minimal markdown renderer ─────────────────────────────────
function markdownToHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // re-allow already-safe tags we build
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escJson(obj) {
  return "'" + JSON.stringify(obj).replace(/'/g, "\\'") + "'";
}
