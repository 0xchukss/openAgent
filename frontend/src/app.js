/**
 * app.js — openAgent main entry point.
 *
 * Handles:
 *  - Wallet connection (window.ethereum / MetaMask)
 *  - Screen routing
 *  - Chat message sending (calls backend /api/chat)
 *  - Streaming response rendering
 *  - Exports shared utilities used by chat.js and screens.js
 */

import { addUserMsg, addAiMsg, showTyping, hideTyping, renderAgentResponse } from './chat.js';
import {
  initSwapScreen, setFromToken, setToToken,
  initBridgeScreen, setBridgeTo,
  initStakeScreen, pickStake,
  openDapp,
  initSettings,
} from './screens.js';

// ─────────────────────────────────────────────────────────────
//  SHARED CONSTANTS (exported for chat.js / screens.js)
// ─────────────────────────────────────────────────────────────
export const API = '/api';          // proxies to FastAPI backend

export const TOK_COLORS = {
  ETH:   { bg: '#627eea', fg: '#fff' },
  USDC:  { bg: '#2775ca', fg: '#fff' },
  USDT:  { bg: '#26a17b', fg: '#fff' },
  WBTC:  { bg: '#f7931a', fg: '#fff' },
  ARB:   { bg: '#28a0f0', fg: '#fff' },
  OP:    { bg: '#ff0420', fg: '#fff' },
  MATIC: { bg: '#8247e5', fg: '#fff' },
  OPG:   { bg: '#4f6ef7', fg: '#fff' },
  stETH: { bg: '#00a3ff', fg: '#fff' },
  rETH:  { bg: '#ff6b22', fg: '#fff' },
};

export const TOK_SYMBOLS = {
  ETH: 'Ξ', USDC: '$', USDT: '$', WBTC: '₿',
  ARB: 'A', OP: 'O', MATIC: 'M', OPG: '⬡',
  stETH: 'st', rETH: 'r',
};

export const fmtNum = (n, dp = 4) => {
  const num = parseFloat(n);
  if (isNaN(num)) return '0';
  if (num >= 1000) return num.toLocaleString('en-US', { maximumFractionDigits: 2 });
  if (num < 0.0001 && num > 0) return num.toExponential(4);
  return parseFloat(num.toFixed(dp)).toString();
};

// ─────────────────────────────────────────────────────────────
//  STATE
// ─────────────────────────────────────────────────────────────
let walletAddress = null;
let conversationHistory = [];     // [{role, content}]
let currentScreen = 'chat';
let ogConfig = null;              // fetched from /api/config on startup

// ─────────────────────────────────────────────────────────────
//  INIT
// ─────────────────────────────────────────────────────────────
async function init() {
  buildStarfield();
  setupNav();
  initSwapScreen();
  initBridgeScreen();
  initStakeScreen();
  initSettings();
  setupBridgeChainPills();
  setupStakeCards();
  setupDappCards();
  setupChatInput();

  // Fetch config from backend
  try {
    const res = await fetch(`${API}/config`);
    ogConfig = await res.json();
    console.log('[openAgent] Config loaded:', ogConfig);
  } catch (e) {
    console.warn('[openAgent] Could not reach backend — running in offline mode');
  }

  // Token dropdowns
  setupTokenDropdowns();
}

// ─────────────────────────────────────────────────────────────
//  WALLET CONNECTION
// ─────────────────────────────────────────────────────────────
window.connectWallet = async function () {
  const btn = document.getElementById('lbtn');
  btn.textContent = 'Connecting…'; btn.style.opacity = '0.7';

  // Step 1 — connect MetaMask
  try {
    if (!window.ethereum) throw new Error('No EVM wallet found. Install MetaMask.');
    const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
    walletAddress = accounts[0];
  } catch (e) {
    btn.textContent = 'Connect Wallet'; btn.style.opacity = '1';
    alert(e.message);
    return;
  }

  setStep('st1', 'done', '✓ Wallet connected');
  setStep('st2', 'active', '② Switch to Base Sepolia…');
  btn.textContent = 'Switching network…';

  // Step 2 — switch to Base Sepolia (chain 84532)
  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: '0x14A34' }],   // 84532 hex
    });
  } catch (err) {
    // Chain not added yet — add it
    if (err.code === 4902) {
      await window.ethereum.request({
        method: 'wallet_addEthereumChain',
        params: [{
          chainId: '0x14A34',
          chainName: 'Base Sepolia',
          nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
          rpcUrls: ['https://sepolia.base.org'],
          blockExplorerUrls: ['https://sepolia-explorer.base.org'],
        }],
      });
    }
  }

  setStep('st2', 'done', '✓ Base Sepolia');
  setStep('st3', 'active', '③ Approving $OPG…');
  btn.textContent = 'Approving $OPG for inference…';

  // Step 3 — $OPG approval handled server-side on startup; just show progress
  await new Promise(r => setTimeout(r, 900));
  setStep('st3', 'done', '✓ $OPG approved');
  btn.textContent = 'Launching openAgent…';

  await new Promise(r => setTimeout(r, 500));
  onConnected();
};

function onConnected() {
  document.getElementById('lock').style.display = 'none';
  document.getElementById('og-status').style.display = 'flex';
  document.getElementById('og-tee-pill').style.display = 'flex';
  document.getElementById('og-bar').classList.add('show');
  document.getElementById('addr-box').style.display = 'block';
  document.getElementById('addr-val').textContent = shortAddr(walletAddress);
  document.getElementById('wbtn').textContent = shortAddr(walletAddress);
  document.getElementById('wbtn').className = 'wb wb-on';
  document.getElementById('settings-addr-val').textContent = walletAddress || '0x3f8a…9a1b';

  // Greet the user
  const modelName = ogConfig?.model || 'claude-sonnet-4-6';
  addAiMsg(
    `<strong>Welcome to openAgent</strong> — powered by OpenGradient's decentralised TEE network.<br><br>` +
    `I'm running on <strong>${modelName}</strong>, with every inference cryptographically verified on-chain. ` +
    `I can chat about anything, and I can execute real DeFi actions on your behalf — ` +
    `swaps, bridges, staking, balance checks, and more.<br><br>` +
    `What would you like to do?`
  );
}

window.disconnectWallet = function () {
  walletAddress = null;
  conversationHistory = [];
  document.getElementById('lock').style.display = 'flex';
  document.getElementById('og-status').style.display = 'none';
  document.getElementById('og-tee-pill').style.display = 'none';
  document.getElementById('og-bar').classList.remove('show');
  document.getElementById('addr-box').style.display = 'none';
  document.getElementById('wbtn').textContent = 'Connect Wallet';
  document.getElementById('wbtn').className = 'wb wb-off';
  // reset steps
  ['st1','st2','st3'].forEach((id, i) => setStep(id, i===0 ? 'active' : '', ['① Connect wallet','② Base Sepolia','③ $OPG approved'][i]));
  document.getElementById('lbtn').textContent = 'Connect Wallet';
  document.getElementById('lbtn').style.opacity = '1';
  document.getElementById('msgs').innerHTML = '';
};

// ─────────────────────────────────────────────────────────────
//  NAVIGATION
// ─────────────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll('.nav[data-screen]').forEach(el => {
    el.addEventListener('click', () => {
      if (!walletAddress) return;
      goToScreen(el.dataset.screen, el);
    });
  });
}

function goToScreen(name, navEl) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('on'));
  document.getElementById('s-' + name).classList.add('on');
  document.querySelectorAll('.nav').forEach(n => n.classList.remove('on'));
  if (navEl) navEl.classList.add('on');
  currentScreen = name;
}

// Exposed globally so screens.js can call it
window.goToChat = function (prefill) {
  const nav = document.querySelector('.nav[data-screen="chat"]');
  goToScreen('chat', nav);
  if (prefill) {
    document.getElementById('chat-inp').value = prefill;
    sendMessage();
  }
};

// ─────────────────────────────────────────────────────────────
//  CHAT
// ─────────────────────────────────────────────────────────────
function setupChatInput() {
  const inp = document.getElementById('chat-inp');
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById('chat-send').addEventListener('click', sendMessage);
  document.querySelectorAll('.chip').forEach(el => {
    el.addEventListener('click', () => { inp.value = el.dataset.prompt; sendMessage(); });
  });
}

async function sendMessage() {
  const inp = document.getElementById('chat-inp');
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';

  addUserMsg(text);
  conversationHistory.push({ role: 'user', content: text });

  showTyping();

  try {
    const resp = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: conversationHistory,
        wallet_address: walletAddress || 'not_connected',
      }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Backend error');
    }

    const data = await resp.json();
    hideTyping();

    // Add to history
    conversationHistory.push({ role: 'assistant', content: data.content || '' });

    renderAgentResponse(data);
  } catch (e) {
    hideTyping();
    // Fallback — show error message in chat
    addAiMsg(
      `⚠ <strong>Connection error</strong><br><br>` +
      `Could not reach the OpenGradient backend: <code>${e.message}</code><br><br>` +
      `Make sure the FastAPI server is running at <code>localhost:8000</code> and your ` +
      `<code>OG_PRIVATE_KEY</code> is set in <code>backend/.env</code>.`
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  SETUP DYNAMIC COMPONENTS
// ─────────────────────────────────────────────────────────────
function setupBridgeChainPills() {
  const chains = [
    { name: 'Arbitrum', bg: '#28a0f0', sym: 'A', id: 42161 },
    { name: 'Optimism', bg: '#ff0420', sym: 'O', id: 10 },
    { name: 'Polygon',  bg: '#8247e5', sym: 'P', id: 137 },
    { name: 'zkSync',   bg: '#4e529a', sym: 'Z', id: 324 },
    { name: 'Ethereum', bg: '#627eea', sym: 'E', id: 1 },
    { name: 'Base',     bg: '#0052ff', sym: 'B', id: 8453 },
  ];
  const container = document.getElementById('bridge-chain-pills');
  if (!container) return;
  chains.forEach((c, i) => {
    const el = document.createElement('div');
    el.className = 'chip bridge-chain-pill';
    el.dataset.chain = c.name;
    el.textContent = c.name;
    if (i === 0) { el.style.borderColor = 'var(--ac)'; el.style.color = 'var(--ac2)'; el.style.background = 'var(--ag)'; }
    el.addEventListener('click', () => setBridgeTo(c.name, c.bg, c.sym, c.id));
    container.appendChild(el);
  });
}

function setupStakeCards() {
  const protocols = [
    { name: 'Lido',        apy: '3.8', ic: '🔷', col: '#00a3ff', rec: 'stETH',  sub: 'ETH Liquid Staking', desc: 'Receive stETH — stays liquid across DeFi' },
    { name: 'Rocket Pool', apy: '3.6', ic: '🚀', col: '#ff6b22', rec: 'rETH',   sub: 'Decentralised ETH',   desc: 'Fully decentralised — receive rETH' },
    { name: 'Aave',        apy: '4.9', ic: '👻', col: '#b6509e', rec: 'aUSDC',  sub: 'USDC Lending',        desc: 'Supply USDC, earn lending yield' },
    { name: 'Curve',       apy: '6.2', ic: '〜', col: '#e84142', rec: 'CRV-LP', sub: 'LP Staking',           desc: 'Liquidity pools + CRV rewards' },
  ];
  const container = document.getElementById('stake-cards-container');
  if (!container) return;
  protocols.forEach((p, i) => {
    const el = document.createElement('div');
    el.className = 'stake-card' + (i === 0 ? ' sel' : '');
    el.innerHTML = `
      <div class="stake-card-top">
        <div class="stake-card-ic" style="background:${p.col}22;color:${p.col}">${p.ic}</div>
        <div>
          <div style="font-size:13px;font-weight:700">${p.name}</div>
          <div style="font-size:10.5px;color:var(--t3)">${p.sub}</div>
        </div>
      </div>
      <div class="stake-apy">${p.apy}% APY</div>
      <div class="stake-desc">${p.desc}</div>`;
    el.addEventListener('click', () => pickStake(el, p.name, p.apy, p.rec));
    container.appendChild(el);
  });
}

function setupDappCards() {
  const dapps = [
    { name: 'Uniswap',  ic: '🦄', col: '#ff007a', cat: 'DEX',        desc: 'Swap & liquidity' },
    { name: 'Aave',     ic: '👻', col: '#b6509e', cat: 'Lending',     desc: 'Lend & borrow' },
    { name: 'Curve',    ic: '〜', col: '#e84142', cat: 'Stable DEX',  desc: 'Stable swaps' },
    { name: 'GMX',      ic: '🔵', col: '#4af5a6', cat: 'Perps',       desc: 'Up to 50x leverage' },
    { name: 'Compound', ic: '🌿', col: '#00d395', cat: 'Lending',     desc: 'Earn on deposits' },
    { name: '1inch',    ic: '🪐', col: '#1b8ef7', cat: 'Aggregator',  desc: 'Best rate routing' },
    { name: 'Balancer', ic: '⚖️', col: '#7945f1', cat: 'AMM',         desc: 'Weighted pools' },
    { name: 'dYdX',     ic: '📈', col: '#6966ff', cat: 'Perps',       desc: 'Advanced trading' },
  ];
  const container = document.getElementById('dapp-grid');
  if (!container) return;
  dapps.forEach(d => {
    const el = document.createElement('div');
    el.className = 'dapp-card';
    el.innerHTML = `
      <div class="dapp-ic" style="background:${d.col}22;border:1px solid ${d.col}33">${d.ic}</div>
      <div style="font-size:13.5px;font-weight:700">${d.name}</div>
      <div style="font-size:10px;font-family:'Space Mono',monospace;color:var(--t3)">${d.cat}</div>
      <div style="font-size:11px;color:var(--t3)">${d.desc}</div>
      <div class="dapp-open">Open in agent →</div>`;
    el.addEventListener('click', () => openDapp(d.name, window.goToChat));
    container.appendChild(el);
  });
}

function setupTokenDropdowns() {
  const tokens = [
    { tok: 'ETH',  sym: 'Ξ', bg: '#627eea' },
    { tok: 'USDC', sym: '$', bg: '#2775ca' },
    { tok: 'WBTC', sym: '₿', bg: '#f7931a' },
    { tok: 'ARB',  sym: 'A', bg: '#28a0f0' },
    { tok: 'OPG',  sym: '⬡', bg: '#4f6ef7' },
  ];

  ['swap-from-drop', 'swap-to-drop'].forEach(dropId => {
    const drop = document.getElementById(dropId);
    if (!drop) return;
    drop.innerHTML = '';
    tokens.forEach(t => {
      const el = document.createElement('div');
      el.className = 'tok-opt';
      el.innerHTML = `<div class="tok-sel-ic" style="background:${t.bg};color:#fff;width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700">${t.sym}</div>${t.tok}`;
      el.addEventListener('click', e => {
        e.stopPropagation();
        if (dropId === 'swap-from-drop') setFromToken(t.tok);
        else setToToken(t.tok);
      });
      drop.appendChild(el);
    });
  });

  document.getElementById('swap-from-sel')?.addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('swap-from-drop').classList.toggle('open');
    document.getElementById('swap-to-drop').classList.remove('open');
  });
  document.getElementById('swap-to-sel')?.addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('swap-to-drop').classList.toggle('open');
    document.getElementById('swap-from-drop').classList.remove('open');
  });
  document.addEventListener('click', () => {
    document.querySelectorAll('.tok-dropdown').forEach(d => d.classList.remove('open'));
  });
}

// ─────────────────────────────────────────────────────────────
//  UTILITIES
// ─────────────────────────────────────────────────────────────
function setStep(id, state, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'step ' + state;
  el.textContent = text;
}

function shortAddr(addr) {
  if (!addr) return '';
  return addr.slice(0, 6) + '…' + addr.slice(-4);
}

function buildStarfield() {
  const s = document.getElementById('stars');
  if (!s) return;
  for (let i = 0; i < 70; i++) {
    const d = document.createElement('div');
    d.className = 'star';
    const sz = (Math.random() * 1.8 + 0.4).toFixed(1);
    d.style.cssText = `width:${sz}px;height:${sz}px;top:${(Math.random()*100).toFixed(1)}%;left:${(Math.random()*100).toFixed(1)}%;--d:${(Math.random()*5+2).toFixed(1)}s;--dl:${(Math.random()*5).toFixed(1)}s;--op:${(Math.random()*.28+0.04).toFixed(2)}`;
    s.appendChild(d);
  }
}

// ─────────────────────────────────────────────────────────────
//  BOOT
// ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
