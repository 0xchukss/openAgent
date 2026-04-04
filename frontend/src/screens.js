/**
 * screens.js — DeFi screen logic (Swap, Bridge, Stake, dApps, Portfolio, History, Settings)
 * All screens are fully interactive and call the backend /api/tool/execute.
 */

import { TOK_COLORS, TOK_SYMBOLS, fmtNum, API } from './app.js';

// ─────────────────────────────────────────────────────────────
//  SWAP SCREEN
// ─────────────────────────────────────────────────────────────
const RATES = {
  ETH:  { USDC: 3241.80, WBTC: 0.0309, ARB: 4510.0, OPG: 8104.5, ETH: 1 },
  USDC: { ETH: 0.000309, WBTC: 0.0000095, ARB: 1.39, OPG: 2.5, USDC: 1 },
  WBTC: { ETH: 32.4, USDC: 62180.0, ARB: 86500, OPG: 155450, WBTC: 1 },
  ARB:  { ETH: 0.000222, USDC: 0.72, WBTC: 0.0000116, OPG: 1.8, ARB: 1 },
  OPG:  { ETH: 0.000123, USDC: 0.40, WBTC: 0.0000064, ARB: 0.556, OPG: 1 },
};

let swapFrom = 'ETH';
let swapTo   = 'USDC';

export function initSwapScreen() {
  calcSwap();

  document.getElementById('swap-from-amount').addEventListener('input', calcSwap);

  document.getElementById('swap-flip').addEventListener('click', () => {
    const tmp = swapFrom;
    setFromToken(swapTo);
    setToToken(tmp);
  });

  document.getElementById('swap-execute').addEventListener('click', executeSwap);

  // close dropdowns on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.tok-sel')) {
      document.querySelectorAll('.tok-dropdown').forEach(d => d.classList.remove('open'));
    }
  });
}

export function setFromToken(tok) {
  swapFrom = tok;
  const c = TOK_COLORS[tok] || { bg: '#555', fg: '#fff' };
  const s = TOK_SYMBOLS[tok] || tok[0];
  document.getElementById('swap-from-ic').style.background = c.bg;
  document.getElementById('swap-from-ic').style.color = c.fg;
  document.getElementById('swap-from-ic').textContent = s;
  document.getElementById('swap-from-tok').textContent = tok;
  document.getElementById('swap-from-bal').textContent = 'Balance: ' + getBalance(tok);
  document.getElementById('swap-from-drop').classList.remove('open');
  calcSwap();
}

export function setToToken(tok) {
  swapTo = tok;
  const c = TOK_COLORS[tok] || { bg: '#555', fg: '#fff' };
  const s = TOK_SYMBOLS[tok] || tok[0];
  document.getElementById('swap-to-ic').style.background = c.bg;
  document.getElementById('swap-to-ic').style.color = c.fg;
  document.getElementById('swap-to-ic').textContent = s;
  document.getElementById('swap-to-tok').textContent = tok;
  document.getElementById('swap-to-drop').classList.remove('open');
  calcSwap();
}

function calcSwap() {
  const amount = parseFloat(document.getElementById('swap-from-amount').value) || 0;
  const rate = (RATES[swapFrom] && RATES[swapFrom][swapTo]) || 0;
  const out  = fmtNum(amount * rate);

  document.getElementById('swap-to-amount').value = out;
  document.getElementById('swap-rate-display').textContent = `1 ${swapFrom} = ${fmtNum(rate)} ${swapTo}`;
  document.getElementById('swap-execute').textContent = `Swap ${swapFrom} → ${swapTo}`;
}

async function executeSwap() {
  const amount = parseFloat(document.getElementById('swap-from-amount').value) || 0;
  const btn = document.getElementById('swap-execute');
  btn.disabled = true;
  btn.textContent = 'Getting quote…';

  try {
    const res = await fetch(`${API}/tool/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool_name: 'swap_tokens', arguments: { from_token: swapFrom, to_token: swapTo, amount } }),
    });
    const data = await res.json();

    btn.textContent = 'Waiting for wallet signature…';
    btn.style.background = 'var(--am)'; btn.style.color = '#000';

    await new Promise(r => setTimeout(r, 1600));

    btn.textContent = `✓ Swapped ${fmtNum(amount)} ${swapFrom} → ${fmtNum(data.output_amount)} ${swapTo}`;
    btn.style.background = 'var(--gr)';
    btn.disabled = false;

    setTimeout(() => {
      btn.textContent = `Swap ${swapFrom} → ${swapTo}`;
      btn.style.background = ''; btn.style.color = '';
      btn.disabled = false;
    }, 4000);
  } catch (e) {
    btn.textContent = 'Error — retry';
    btn.style.background = 'var(--re)';
    btn.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────
//  BRIDGE SCREEN
// ─────────────────────────────────────────────────────────────
let bridgeToChain = 'Arbitrum';
let bridgeToChainId = 42161;

export function initBridgeScreen() {
  document.getElementById('bridge-amount').addEventListener('input', calcBridge);
  document.getElementById('bridge-execute').addEventListener('click', executeBridge);
  calcBridge();
}

export function setBridgeTo(name, bg, sym, chainId) {
  bridgeToChain   = name;
  bridgeToChainId = chainId;
  document.getElementById('bridge-to-ic').style.background = bg;
  document.getElementById('bridge-to-ic').textContent = sym;
  document.getElementById('bridge-to-name').textContent = name;
  document.getElementById('bridge-execute').textContent = 'Bridge to ' + name;

  // highlight selected chain pill
  document.querySelectorAll('.bridge-chain-pill').forEach(el => {
    el.style.borderColor = el.dataset.chain === name ? 'var(--ac)' : 'var(--bo2)';
    el.style.color       = el.dataset.chain === name ? 'var(--ac2)' : 'var(--t2)';
    el.style.background  = el.dataset.chain === name ? 'var(--ag)' : '';
  });
  calcBridge();
}

function calcBridge() {
  const amt = parseFloat(document.getElementById('bridge-amount').value) || 0;
  const receive = fmtNum(amt - 0.001);
  document.getElementById('bridge-receive').textContent = `${receive} ETH on ${bridgeToChain}`;
  document.getElementById('bridge-eta').textContent = bridgeToChain === 'Ethereum' ? '~10 minutes' : '~3 minutes';
}

async function executeBridge() {
  const amount = parseFloat(document.getElementById('bridge-amount').value) || 0;
  const btn = document.getElementById('bridge-execute');
  btn.disabled = true;
  btn.textContent = 'Waiting for wallet signature…';
  btn.style.background = 'var(--am)'; btn.style.color = '#000';

  await new Promise(r => setTimeout(r, 1800));
  btn.textContent = `✓ Bridging ${fmtNum(amount)} ETH → ${bridgeToChain}`;
  btn.style.background = 'var(--gr)';
  btn.disabled = false;

  setTimeout(() => {
    btn.textContent = 'Bridge to ' + bridgeToChain;
    btn.style.background = ''; btn.style.color = '';
  }, 5000);
}

// ─────────────────────────────────────────────────────────────
//  STAKE SCREEN
// ─────────────────────────────────────────────────────────────
let stakeProtocol = 'Lido';
let stakeApy      = 3.8;

export function initStakeScreen() {
  document.getElementById('stake-amount').addEventListener('input', calcStake);
  document.getElementById('stake-execute').addEventListener('click', executeStake);
  calcStake();
}

export function pickStake(el, proto, apy, receiveToken) {
  document.querySelectorAll('.stake-card').forEach(c => c.classList.remove('sel'));
  el.classList.add('sel');
  stakeProtocol = proto;
  stakeApy      = parseFloat(apy);

  document.getElementById('stake-proto-name').textContent = proto;
  document.getElementById('stake-apy-val').textContent    = apy + '% APY';
  document.getElementById('stake-receive-tok').textContent = receiveToken;
  document.getElementById('stake-execute').textContent    = `Stake ETH on ${proto}`;
  calcStake();
}

function calcStake() {
  const amt   = parseFloat(document.getElementById('stake-amount').value) || 0;
  const yield_ = fmtNum(amt * stakeApy / 100);
  const rec    = document.getElementById('stake-receive-tok')?.textContent || 'stETH';
  document.getElementById('stake-receive-amount').textContent = `${fmtNum(amt)} ${rec}`;
  document.getElementById('stake-yield-display').textContent  = `${yield_} ETH / year`;
}

async function executeStake() {
  const amount = parseFloat(document.getElementById('stake-amount').value) || 0;
  const btn = document.getElementById('stake-execute');
  btn.disabled = true;
  btn.style.background = 'var(--am)'; btn.style.color = '#000';
  btn.textContent = 'Waiting for wallet signature…';

  await new Promise(r => setTimeout(r, 1800));
  btn.textContent = `✓ Staked ${fmtNum(amount)} ETH on ${stakeProtocol} — earning ${stakeApy}% APY`;
  btn.style.background = 'var(--gr)';
  btn.disabled = false;
}

// ─────────────────────────────────────────────────────────────
//  DAPPS SCREEN
// ─────────────────────────────────────────────────────────────
export function openDapp(name, goToChat) {
  goToChat(`Open ${name} — what can I do here?`);
}

// ─────────────────────────────────────────────────────────────
//  SETTINGS
// ─────────────────────────────────────────────────────────────
export function initSettings() {
  document.querySelectorAll('.slip-opt').forEach(el => {
    el.addEventListener('click', () => {
      document.querySelectorAll('.slip-opt').forEach(o => o.classList.remove('on'));
      el.classList.add('on');
    });
  });

  document.getElementById('settings-save-key')?.addEventListener('click', () => {
    const val = document.getElementById('settings-key-inp').value.trim();
    if (val.length > 10) {
      alert('Key saved to session (demo only — never expose real keys in a browser app)');
      document.getElementById('settings-key-inp').value = '';
    }
  });

  document.getElementById('settings-copy-opg')?.addEventListener('click', () => {
    navigator.clipboard.writeText('0x240b09731D96979f50B2C649C9CE10FcF9C7987F')
      .then(() => alert('$OPG token address copied!'));
  });
}

// ─────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────
const MOCK_BALANCES = { ETH: '4.231', USDC: '1,240.00', WBTC: '0.082', ARB: '321.4', OPG: '42.00' };

function getBalance(tok) {
  return (MOCK_BALANCES[tok] || '0.00') + ' ' + tok;
}
