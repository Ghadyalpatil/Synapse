/**
 * SYNAPSE TACTICAL COMMAND CENTRE (C2) — REAL-TIME MESH CONTROLLER
 * Zero-cloud, air-gapped web client communicating via WebSockets and REST.
 */

// Global State
const state = {
  activeTab: 'sensors',
  activeNodeFilter: 'ALL',
  latestSensors: new Map(), // key: `${source_node}:${sensor_id}`
  sensorHistory: new Map(), // key -> number[]
  nodes: new Map(),         // key: node_id -> node_info
  packets: [],              // recent wire packets
  alerts: [],
  totalPacketsCount: 0,
  audioEnabled: false,
  ws: null,
  reconnectInterval: 2000,
  audioCtx: null
};

// ============================================================================
// Initialization
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  connectWebSocket();
  fetchAllInitialData();
  setInterval(refreshPeriodicMetrics, 3000);
});

function initClock() {
  function updateTime() {
    const now = new Date();
    const clockEl = document.getElementById('header-clock');
    if (clockEl) {
      clockEl.textContent = now.toTimeString().split(' ')[0] + ' UTC';
    }
  }
  updateTime();
  setInterval(updateTime, 1000);
}

// ============================================================================
// Web Audio Synthesizer (No external audio files needed)
// ============================================================================
function getAudioContext() {
  if (!state.audioCtx) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      state.audioCtx = new AudioCtx();
    }
  }
  if (state.audioCtx && state.audioCtx.state === 'suspended') {
    state.audioCtx.resume();
  }
  return state.audioCtx;
}

function toggleAudioAlerts() {
  state.audioEnabled = !state.audioEnabled;
  const icon = document.getElementById('audio-icon');
  const btn = document.getElementById('btn-audio-toggle');
  if (state.audioEnabled) {
    getAudioContext();
    icon.textContent = '🔊';
    btn.style.borderColor = 'var(--accent-cyan)';
    playTacticalTone(880, 0.08, 'sine');
  } else {
    icon.textContent = '🔇';
    btn.style.borderColor = 'var(--border-dim)';
  }
}

function playTacticalTone(freq = 440, duration = 0.1, type = 'sine') {
  if (!state.audioEnabled) return;
  try {
    const ctx = getAudioContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  } catch (e) {
    // Ignore audio autoplay restrictions
  }
}

function playAlertChime() {
  if (!state.audioEnabled) return;
  playTacticalTone(920, 0.12, 'sawtooth');
  setTimeout(() => playTacticalTone(660, 0.25, 'triangle'), 130);
}

// ============================================================================
// WebSocket Real-time Ingestion Loop
// ============================================================================
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  const dot = document.getElementById('dot-ws');
  const text = document.getElementById('text-ws');

  try {
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      dot.className = 'pulse-dot active';
      text.textContent = 'MESH LINK LIVE';
      logTerminalLine('[LINK] WebSocket connected to Synapse C2 Gateway.', 'green');
    };

    state.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleIncomingMeshMessage(msg);
      } catch (err) {
        console.error('Error parsing incoming WS message:', err);
      }
    };

    state.ws.onclose = () => {
      dot.className = 'pulse-dot';
      text.textContent = 'MESH LINK RECONNECTING';
      setTimeout(connectWebSocket, state.reconnectInterval);
    };

    state.ws.onerror = (err) => {
      console.warn('WS error:', err);
    };
  } catch (e) {
    setTimeout(connectWebSocket, state.reconnectInterval);
  }
}

// ============================================================================
// Incoming Mesh Message Dispatcher
// ============================================================================
function handleIncomingMeshMessage(msg) {
  state.totalPacketsCount++;
  document.getElementById('val-total-packets').textContent = state.totalPacketsCount.toLocaleString();

  // Record into wire packet log
  recordWirePacket(msg);

  const mType = msg.message_type || msg.type;
  const source = msg.source_node || 'UNKNOWN';

  if (mType === 'SENSOR_DATA') {
    handleSensorDataMessage(msg);
    playTacticalTone(1200, 0.03, 'sine');
  } else if (mType === 'TARGET_DETECTED' || mType === 'ALERT') {
    handleAlertMessage(msg);
    playAlertChime();
  } else if (mType === 'ALERT_ACK') {
    handleAlertAckMessage(msg);
  } else if (mType === 'COMMAND') {
    const payload = msg.payload || {};
    logTerminalLine(`[COMMAND INGESTED] ${payload.command || 'UNKNOWN'} from ${source}`, 'cyan');
  }

  // Update telemetry ping timestamp
  const pingEl = document.getElementById('telemetry-ping-time');
  if (pingEl) {
    pingEl.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
  }
}

// ----------------------------------------------------------------------------
// Sensor Data Processing
// ----------------------------------------------------------------------------
function handleSensorDataMessage(msg) {
  const source = msg.source_node || 'UNKNOWN';
  const payload = msg.payload || {};

  let readings = [];
  if (Array.isArray(payload)) {
    readings = payload;
  } else if (payload && Array.isArray(payload.readings)) {
    readings = payload.readings;
  } else if (payload && typeof payload === 'object') {
    readings = [payload];
  }

  readings.forEach((reading) => {
    if (!reading || typeof reading !== 'object') return;
    const sId = reading.sensor_id || `${source}-SENSOR`;
    const sType = reading.sensor_type || 'unknown';
    const key = `${source}:${sId}`;

    reading.source_node = source;
    reading.timestamp = reading.timestamp || msg.timestamp || (Date.now() / 1000);

    state.latestSensors.set(key, reading);

    // Track numerical metric in history for sparklines
    let numVal = 0;
    if (sType === 'thermal') numVal = reading.temperature_celsius || 20;
    else if (sType === 'acoustic') numVal = reading.decibels || 40;
    else if (sType === 'motion') numVal = (reading.intensity || 0) * 100;
    else numVal = reading.confidence ? reading.confidence * 100 : 0;

    if (!state.sensorHistory.has(key)) {
      state.sensorHistory.set(key, []);
    }
    const hist = state.sensorHistory.get(key);
    hist.push(numVal);
    if (hist.length > 25) hist.shift();

    // Append to live telemetry table
    prependTelemetryTableRow(source, sId, sType, reading);
  });

  renderSensorCards();
  updateNodeChips();
}

// ----------------------------------------------------------------------------
// Alert Processing
// ----------------------------------------------------------------------------
function handleAlertMessage(msg) {
  const source = msg.source_node || 'UNKNOWN';
  const payload = msg.payload || {};
  const alertId = msg.event_id || msg.message_id || `ALT-${Date.now()}`;
  const severity = msg.priority === 'P0' ? 'CRITICAL' : 'WARNING';
  const text = payload.message || payload.summary || `Surveillance threat from ${source}`;

  const alertObj = {
    alert_id: alertId,
    event_id: msg.event_id,
    source_node: source,
    severity: severity,
    message: text,
    timestamp: msg.timestamp || (Date.now() / 1000),
    acknowledged: false,
    details: payload
  };

  state.alerts.unshift(alertObj);
  if (state.alerts.length > 100) state.alerts.pop();

  renderAlertsFeed();
  updateAlertMetrics();

  logTerminalLine(`[ALERT ${severity}] ${text} (Source: ${source})`, severity === 'CRITICAL' ? 'red' : 'amber');
}

function handleAlertAckMessage(msg) {
  const alertId = msg.alert_id;
  const a = state.alerts.find(item => item.alert_id === alertId);
  if (a) {
    a.acknowledged = true;
    renderAlertsFeed();
    updateAlertMetrics();
  }
}

function updateAlertMetrics() {
  const activeAlerts = state.alerts.filter(a => !a.acknowledged);
  const countEl = document.getElementById('val-total-alerts');
  const badgeEl = document.getElementById('badge-alert-status');
  if (countEl) countEl.textContent = activeAlerts.length;
  if (badgeEl) {
    if (activeAlerts.length > 0) {
      badgeEl.className = 'm-badge red';
      badgeEl.textContent = `${activeAlerts.length} THREATS`;
    } else {
      badgeEl.className = 'm-badge green';
      badgeEl.textContent = 'PERIMETER NOMINAL';
    }
  }
}

// ============================================================================
// Sensor Card Rendering Engine
// ============================================================================
function renderSensorCards() {
  const container = document.getElementById('sensor-cards-grid');
  if (!container) return;

  const entries = Array.from(state.latestSensors.entries());
  const filtered = entries.filter(([key, reading]) => {
    if (state.activeNodeFilter === 'ALL') return true;
    return reading.source_node === state.activeNodeFilter;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="sensor-empty-state">
        <div class="empty-icon">📡</div>
        <h3>No Sensor Telemetry For Selected Node</h3>
        <p>Awaiting incoming packets from edge module over independent TCP mesh socket.</p>
        <button class="btn-action cyan-btn" onclick="requestGlobalSensorSweep()">Request Sensor Sweep</button>
      </div>
    `;
    return;
  }

  // Update sensor count in strip
  const totalSensorsEl = document.getElementById('val-total-sensors');
  if (totalSensorsEl) {
    totalSensorsEl.textContent = entries.length;
  }

  container.innerHTML = '';

  filtered.forEach(([key, r]) => {
    const card = createSensorCardElement(key, r);
    container.appendChild(card);
    // Draw sparkline canvas
    drawSparkline(key);
  });
}

function createSensorCardElement(key, r) {
  const sType = (r.sensor_type || 'unknown').toLowerCase();
  const sId = r.sensor_id || 'UNKNOWN';
  const node = r.source_node || 'UNKNOWN';

  const card = document.createElement('div');
  card.className = 'sensor-card';
  card.id = `sensor-card-${key.replace(/[:.]/g, '-')}`;

  let icon = '📡';
  let title = 'SURVEILLANCE SENSOR';
  let bodyHTML = '';
  let isBreach = false;

  if (sType === 'thermal') {
    icon = '🔥';
    title = 'FLIR THERMAL IMAGING';
    const temp = Number(r.temperature_celsius || 20).toFixed(1);
    const targetDetected = Boolean(r.target_detected);
    const conf = r.confidence ? (r.confidence * 100).toFixed(0) : '0';
    if (targetDetected || Number(temp) > 35) isBreach = true;

    // SVG arc stroke calculation (range: 15°C to 45°C)
    const minT = 15, maxT = 45;
    const clamped = Math.max(minT, Math.min(maxT, Number(temp)));
    const percent = (clamped - minT) / (maxT - minT);
    const circumference = 283;
    const offset = circumference - (percent * circumference);

    let meterColor = 'var(--accent-cyan)';
    if (Number(temp) > 34) meterColor = 'var(--accent-red)';
    else if (Number(temp) > 28) meterColor = 'var(--accent-amber)';

    bodyHTML = `
      <div class="gauge-container">
        <div class="dial-wrap">
          <svg class="dial-svg" viewBox="0 0 100 100">
            <circle class="dial-bg" cx="50" cy="50" r="45" />
            <circle class="dial-meter" cx="50" cy="50" r="45" style="stroke-dashoffset: ${offset}; stroke: ${meterColor};" />
          </svg>
          <div class="dial-val-center">
            <div class="dial-val-number" style="color:${meterColor};">${temp}</div>
            <div class="dial-val-unit">&deg;C</div>
          </div>
        </div>
        <div class="s-metrics-stack">
          <div class="s-metric-row">
            <span class="s-m-lbl">Target Status:</span>
            <span class="s-m-val ${targetDetected ? 'red-text' : 'green-text'}">
              ${targetDetected ? '🔥 TARGET DETECTED' : 'NOMINAL (CLEAR)'}
            </span>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Confidence:</span>
            <span class="s-m-val cyan-text">${conf}%</span>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Optimal Band:</span>
            <span class="s-m-val">18&deg;C &ndash; 24&deg;C</span>
          </div>
        </div>
      </div>
    `;
  } else if (sType === 'acoustic') {
    icon = '🔊';
    title = 'ACOUSTIC BREACH DETECTOR';
    const db = Number(r.decibels || 40).toFixed(1);
    const signature = r.signature || 'AMBIENT_WIND';
    const anomaly = Boolean(r.anomaly_detected);
    const conf = r.confidence ? (r.confidence * 100).toFixed(0) : '0';
    if (anomaly || Number(db) > 85) isBreach = true;

    // Generate 16 simulated VU bars based on dB
    const barsCount = 16;
    const normalized = Math.min(1, Math.max(0, (Number(db) - 30) / 80));
    let barsHTML = '';
    for (let i = 0; i < barsCount; i++) {
      const active = (i / barsCount) <= normalized;
      let barClass = 'vu-bar';
      if (active) {
        if (i > 12) barClass += ' active-red';
        else if (i > 8) barClass += ' active-amber';
        else barClass += ' active-green';
      }
      const h = active ? Math.max(8, Math.round(((i + 1) / barsCount) * 36)) : 4;
      barsHTML += `<div class="${barClass}" style="height:${h}px;"></div>`;
    }

    bodyHTML = `
      <div class="vu-meter-box">
        <div class="vu-bars-container">${barsHTML}</div>
        <div class="s-metrics-stack">
          <div class="s-metric-row">
            <span class="s-m-lbl">Sound Pressure:</span>
            <span class="s-m-val ${Number(db) > 85 ? 'red-text' : 'cyan-text'}">${db} dB</span>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Signature Class:</span>
            <span class="s-m-val ${anomaly ? 'amber-text' : ''}">${signature}</span>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Breach Anomaly:</span>
            <span class="s-m-val ${anomaly ? 'red-text' : 'green-text'}">
              ${anomaly ? '🚨 ANOMALY' : 'NORMAL'} (${conf}%)
            </span>
          </div>
        </div>
      </div>
    `;
  } else if (sType === 'motion') {
    icon = '🚶';
    title = 'SEISMIC / PIR PERIMETER';
    const detected = Boolean(r.motion_detected);
    const intensity = Number(r.intensity || 0);
    const conf = r.confidence ? (r.confidence * 100).toFixed(0) : '0';
    if (detected || intensity > 0.5) isBreach = true;

    const progressWidth = Math.round(intensity * 100);

    bodyHTML = `
      <div class="motion-sweep-box">
        <div class="motion-radar">
          <div class="motion-radar-inner"></div>
          <div class="motion-radar-dot ${detected ? 'breach' : ''}"></div>
        </div>
        <div class="s-metrics-stack">
          <div class="s-metric-row">
            <span class="s-m-lbl">Perimeter Gate:</span>
            <span class="s-m-val ${detected ? 'red-text' : 'green-text'}">
              ${detected ? '🚨 BREACH INTRUSION' : 'PERIMETER SECURE'}
            </span>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Vibration Intensity:</span>
            <span class="s-m-val">${(intensity).toFixed(2)}</span>
          </div>
          <div class="s-progress-wrap">
            <div class="s-progress-bar" style="width:${progressWidth}%; background:${detected ? 'var(--accent-red)' : 'var(--accent-cyan)'};"></div>
          </div>
          <div class="s-metric-row">
            <span class="s-m-lbl">Confidence:</span>
            <span class="s-m-val cyan-text">${conf}%</span>
          </div>
        </div>
      </div>
    `;
  } else {
    // Generic Sensor fallback
    icon = '🛰️';
    title = `${sType.toUpperCase()} TELEMETRY`;
    bodyHTML = `
      <div class="s-metrics-stack" style="padding:0.75rem 0;">
        <div class="s-metric-row">
          <span class="s-m-lbl">Sensor Key:</span>
          <span class="s-m-val">${sId}</span>
        </div>
        <div class="s-metric-row">
          <span class="s-m-lbl">Raw Reading:</span>
          <span class="s-m-val mono">${JSON.stringify(r).slice(0, 45)}...</span>
        </div>
      </div>
    `;
  }

  if (isBreach) {
    card.classList.add('breach-alert');
  }

  card.innerHTML = `
    <div class="s-card-top">
      <div class="s-node-tag">
        <div class="s-sensor-icon">${icon}</div>
        <div>
          <div class="s-sensor-name">${title}</div>
          <div class="s-node-name">${node} &bull; ${sId}</div>
        </div>
      </div>
      <span class="badge ${isBreach ? 'red' : 'green'}">${isBreach ? 'ALERT' : 'NOMINAL'}</span>
    </div>
    ${bodyHTML}
    <div class="sparkline-box">
      <div class="sparkline-label">
        <span>HISTORY TREND</span>
        <span>${new Date(r.timestamp * 1000).toLocaleTimeString()}</span>
      </div>
      <canvas class="sparkline-canvas" id="canvas-${key.replace(/[:.]/g, '-')}" width="320" height="48"></canvas>
    </div>
  `;

  return card;
}

// ----------------------------------------------------------------------------
// Canvas Sparkline Chart Renderer
// ----------------------------------------------------------------------------
function drawSparkline(key) {
  const canvasId = `canvas-${key.replace(/[:.]/g, '-')}`;
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  const data = state.sensorHistory.get(key) || [];
  ctx.clearRect(0, 0, w, h);

  if (data.length < 2) {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    ctx.setLineDash([]);
    return;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = (max - min) || 1;

  ctx.beginPath();
  data.forEach((val, idx) => {
    const x = (idx / (data.length - 1)) * w;
    const y = h - 6 - (((val - min) / range) * (h - 12));
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  const isAlert = max > 80 || (key.includes('TH') && max > 34);
  const strokeColor = isAlert ? '#ef4444' : '#00f2fe';

  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Gradient area fill under sparkline
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, isAlert ? 'rgba(239, 68, 68, 0.25)' : 'rgba(0, 242, 254, 0.2)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.fillStyle = grad;
  ctx.fill();
}

// ----------------------------------------------------------------------------
// Historical Telemetry Table Row
// ----------------------------------------------------------------------------
function prependTelemetryTableRow(node, sId, sType, reading) {
  const tbody = document.getElementById('telemetry-table-body');
  if (!tbody) return;

  const placeholder = tbody.querySelector('.text-muted');
  if (placeholder) tbody.innerHTML = '';

  const tr = document.createElement('tr');
  const tStr = new Date((reading.timestamp || Date.now() / 1000) * 1000).toISOString().split('T')[1].replace('Z', '');

  let primary = '-';
  let statusBadge = '<span class="badge green">NOMINAL</span>';
  let conf = reading.confidence ? (reading.confidence * 100).toFixed(0) + '%' : 'N/A';

  if (sType === 'thermal') {
    primary = `${reading.temperature_celsius}°C`;
    if (reading.target_detected) statusBadge = '<span class="badge red">🔥 TARGET</span>';
  } else if (sType === 'acoustic') {
    primary = `${reading.decibels} dB`;
    if (reading.anomaly_detected) statusBadge = `<span class="badge amber">${reading.signature || 'BREACH'}</span>`;
  } else if (sType === 'motion') {
    primary = `Int: ${reading.intensity}`;
    if (reading.motion_detected) statusBadge = '<span class="badge red">🚶 BREACH</span>';
  }

  tr.innerHTML = `
    <td class="mono">${tStr}</td>
    <td><span class="badge gray mono">${node}</span></td>
    <td class="mono">${sId}</td>
    <td>${sType.toUpperCase()}</td>
    <td class="mono">${primary}</td>
    <td>${statusBadge}</td>
    <td>${conf}</td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);

  // Keep table bounded
  while (tbody.children.length > 50) {
    tbody.removeChild(tbody.lastChild);
  }

  const countBadge = document.getElementById('telemetry-table-count');
  if (countBadge) countBadge.textContent = `${tbody.children.length} Records`;
}

// ============================================================================
// Wire Packet Inspector Engine
// ============================================================================
function recordWirePacket(msg) {
  state.packets.unshift(msg);
  if (state.packets.length > 80) state.packets.pop();

  const tbody = document.getElementById('packets-table-body');
  if (!tbody) return;

  const placeholder = tbody.querySelector('.text-muted');
  if (placeholder) tbody.innerHTML = '';

  const tr = document.createElement('tr');
  const msgId = msg.message_id || 'MSG-XXXXXX';
  const src = msg.source_node || 'UNKNOWN';
  const dest = msg.destination_node || 'BROADCAST';
  const type = msg.message_type || 'UNKNOWN';
  const prio = msg.priority || 'P2';
  const hops = msg.hop_count || 0;
  const sig = msg.signature ? `${msg.signature.slice(0, 10)}...` : 'None';
  const tStr = new Date((msg.timestamp || Date.now() / 1000) * 1000).toISOString().split('T')[1].replace('Z', '');

  let prioBadge = '<span class="badge gray">P2</span>';
  if (prio === 'P0') prioBadge = '<span class="badge red">P0 (CRIT)</span>';
  else if (prio === 'P1') prioBadge = '<span class="badge amber">P1 (URGENT)</span>';

  tr.innerHTML = `
    <td>${tStr}</td>
    <td class="mono cyan-text">${msgId}</td>
    <td class="mono">${src} &rarr; ${dest}</td>
    <td><span class="badge ${type === 'SENSOR_DATA' ? 'cyan' : (type === 'ALERT' ? 'red' : 'purple')}">${type}</span></td>
    <td>${prioBadge}</td>
    <td><span class="badge green">TCP Framed [4B]</span></td>
    <td title="${msg.signature || ''}">🔒 ${sig}</td>
    <td class="mono">${hops}</td>
    <td><button class="btn-sm ghost-btn" onclick="openPacketModal('${msgId}')">View</button></td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);

  while (tbody.children.length > 50) {
    tbody.removeChild(tbody.lastChild);
  }
}

function openPacketModal(msgId) {
  const pkt = state.packets.find(p => p.message_id === msgId);
  if (!pkt) return;

  document.getElementById('modal-packet-id').textContent = pkt.message_id || 'WIRE PACKET';

  const metaGrid = document.getElementById('modal-packet-meta');
  metaGrid.innerHTML = `
    <div class="meta-card">
      <div class="meta-lbl">SOURCE NODE</div>
      <div class="meta-val">${pkt.source_node || 'UNKNOWN'}</div>
    </div>
    <div class="meta-card">
      <div class="meta-lbl">DESTINATION</div>
      <div class="meta-val">${pkt.destination_node || 'BROADCAST'}</div>
    </div>
    <div class="meta-card">
      <div class="meta-lbl">TRANSPORT PROTOCOL</div>
      <div class="meta-val">TCP Length-Prefixed Binary</div>
    </div>
    <div class="meta-card">
      <div class="meta-lbl">MESSAGE PRIORITY</div>
      <div class="meta-val">${pkt.priority || 'P2'}</div>
    </div>
    <div class="meta-card" style="grid-column: 1 / -1;">
      <div class="meta-lbl">Ed25519 CRYPTOGRAPHIC SIGNATURE</div>
      <div class="meta-val" style="font-size:0.75rem;">${pkt.signature || 'None'}</div>
    </div>
  `;

  document.getElementById('modal-packet-json').textContent = JSON.stringify(pkt, null, 2);
  document.getElementById('packet-modal-overlay').classList.add('active');
}

function closePacketModal(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('close-btn')) return;
  document.getElementById('packet-modal-overlay').classList.remove('active');
}

function clearPacketHistory() {
  state.packets = [];
  const tbody = document.getElementById('packets-table-body');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">Awaiting incoming mesh packets...</td></tr>';
  }
}

function filterPackets(term) {
  const filter = (term || '').toLowerCase();
  const rows = document.querySelectorAll('#packets-table-body tr');
  rows.forEach(r => {
    if (r.textContent.toLowerCase().includes(filter)) {
      r.style.display = '';
    } else {
      r.style.display = 'none';
    }
  });
}

// ============================================================================
// Node Topology Rendering
// ============================================================================
function renderNodesGrid(nodesList) {
  const container = document.getElementById('nodes-grid-cards');
  if (!container) return;

  state.nodes.clear();
  nodesList.forEach(n => state.nodes.set(n.node_id, n));

  const totalEl = document.getElementById('val-total-nodes');
  const onlineEl = document.getElementById('badge-nodes-online');
  const onlineCount = nodesList.filter(n => n.status === 'ONLINE').length;

  if (totalEl) totalEl.textContent = nodesList.length;
  if (onlineEl) onlineEl.textContent = `${onlineCount} ONLINE`;

  if (nodesList.length === 0) {
    container.innerHTML = `
      <div class="sensor-empty-state" style="grid-column: 1 / -1;">
        <div class="empty-icon">🌐</div>
        <h3>No Peer Nodes Discovered Yet</h3>
        <p>SYNAPSE nodes will be automatically discovered via UDP beacons or you can register seed peers manually.</p>
        <button class="btn-action cyan-btn" onclick="openAddPeerModal()">+ Register Edge Node</button>
      </div>
    `;
    return;
  }

  container.innerHTML = '';

  nodesList.forEach(n => {
    const isOnline = n.status === 'ONLINE';
    const lat = n.latency_ms ? `${n.latency_ms} ms` : 'N/A';
    const loss = n.packet_loss ? `${(n.packet_loss * 100).toFixed(1)}%` : '0.0%';
    const lastSeen = n.last_seen ? new Date(n.last_seen * 1000).toLocaleTimeString() : 'Never';

    const card = document.createElement('div');
    card.className = 'node-card';
    card.innerHTML = `
      <div class="node-card-header">
        <span class="node-name">📡 ${n.node_id}</span>
        <span class="badge ${isOnline ? 'green' : 'amber'}">${n.status || 'UNKNOWN'}</span>
      </div>
      <div class="node-stats-grid">
        <div class="node-stat-item">
          <div class="ns-label">ENDPOINT</div>
          <div class="ns-value">${n.ip}:${n.port}</div>
        </div>
        <div class="node-stat-item">
          <div class="ns-label">TCP LATENCY</div>
          <div class="ns-value cyan-text">${lat}</div>
        </div>
        <div class="node-stat-item">
          <div class="ns-label">PACKET LOSS</div>
          <div class="ns-value">${loss}</div>
        </div>
        <div class="node-stat-item">
          <div class="ns-label">LAST SEEN</div>
          <div class="ns-value">${lastSeen}</div>
        </div>
      </div>
      <div class="node-actions-bar">
        <button class="btn-sm cyan-btn" onclick="sendCommandToNode('${n.node_id}', 'SAMPLE_SENSORS')">Poll Sensors</button>
        <button class="btn-sm amber-btn" onclick="sendCommandToNode('${n.node_id}', 'TRIGGER_DETECTION', {sensor_type: 'thermal'})">Trigger Thermal</button>
        <button class="btn-sm ghost-btn" onclick="pingNode('${n.node_id}')">Ping</button>
      </div>
    `;
    container.appendChild(card);
  });

  updateNodeChips();
  updateTerminalTargetSelect();
}

function updateNodeChips() {
  const container = document.getElementById('node-chips-container');
  if (!container) return;

  const nodeSet = new Set(['ALL']);
  state.nodes.forEach((_, id) => nodeSet.add(id));
  state.latestSensors.forEach(r => nodeSet.add(r.source_node));

  container.innerHTML = '';
  nodeSet.forEach(nId => {
    const btn = document.createElement('button');
    btn.className = `chip ${state.activeNodeFilter === nId ? 'active' : ''}`;
    btn.textContent = nId === 'ALL' ? 'ALL NODES' : nId;
    btn.onclick = () => filterSensorNode(nId);
    container.appendChild(btn);
  });
}

function filterSensorNode(nodeId) {
  state.activeNodeFilter = nodeId;
  updateNodeChips();
  renderSensorCards();
}

function updateTerminalTargetSelect() {
  const sel = document.getElementById('term-target-node');
  if (!sel) return;

  const current = sel.value;
  sel.innerHTML = '<option value="BROADCAST">BROADCAST (All Nodes)</option>';
  state.nodes.forEach((_, id) => {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = `${id}`;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

// ============================================================================
// Alerts Feed Rendering
// ============================================================================
function renderAlertsFeed() {
  const container = document.getElementById('alerts-feed-list');
  if (!container) return;

  if (state.alerts.length === 0) {
    container.innerHTML = '<div class="feed-empty">No active security alerts recorded. Perimeter nominal.</div>';
    return;
  }

  container.innerHTML = '';
  state.alerts.forEach(a => {
    const isCrit = a.severity === 'CRITICAL';
    const row = document.createElement('div');
    row.className = `alert-row ${isCrit ? 'critical' : 'warning'}`;
    const tStr = new Date(a.timestamp * 1000).toLocaleTimeString();

    row.innerHTML = `
      <div class="alert-info-left">
        <span class="badge ${isCrit ? 'red' : 'amber'}">${a.severity}</span>
        <div>
          <div class="alert-msg">${a.message}</div>
          <div class="alert-src">Source: <span class="mono">${a.source_node}</span> &bull; Time: <span class="mono">${tStr}</span></div>
        </div>
      </div>
      <div>
        ${a.acknowledged
          ? '<span class="badge gray">ACKNOWLEDGED</span>'
          : `<button class="btn-sm cyan-btn" onclick="acknowledgeAlert('${a.alert_id}')">Acknowledge</button>`
        }
      </div>
    `;
    container.appendChild(row);
  });
}

async function acknowledgeAlert(alertId) {
  try {
    const res = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/ack`, { method: 'POST' });
    if (res.ok) {
      const a = state.alerts.find(item => item.alert_id === alertId);
      if (a) a.acknowledged = true;
      renderAlertsFeed();
      updateAlertMetrics();
      logTerminalLine(`[ACK] Alert ${alertId} acknowledged.`, 'green');
    }
  } catch (err) {
    console.error('Ack error:', err);
  }
}

// ============================================================================
// Mesh Commands & Tactical Operations
// ============================================================================
async function sendCommandToNode(targetNode, command, params = {}) {
  logTerminalLine(`[DISPATCH] ${command} -> ${targetNode}...`, 'cyan');
  try {
    const res = await fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_node: targetNode,
        command: command,
        parameters: params,
        priority: 'P1'
      })
    });
    const data = await res.json();
    if (data.status === 'DELIVERED') {
      logTerminalLine(`[SUCCESS] Command ${command} delivered to ${targetNode} via direct TCP socket!`, 'green');
      playTacticalTone(980, 0.08, 'sine');
    } else {
      logTerminalLine(`[STATUS] Command ${command}: ${data.status} (Queued in Store-and-Forward)`, 'amber');
    }
  } catch (err) {
    logTerminalLine(`[FAIL] Command error: ${err.message}`, 'red');
  }
}

async function requestGlobalSensorSweep() {
  logTerminalLine('[SWEEP] Requesting global sensor sweep across tactical mesh...', 'cyan');
  await sendCommandToNode('BROADCAST', 'SAMPLE_SENSORS');
}

async function pingNode(targetNode) {
  const start = performance.now();
  await sendCommandToNode(targetNode, 'PING');
  const elapsed = Math.round(performance.now() - start);
  logTerminalLine(`[PING] ${targetNode} mesh roundtrip: ${elapsed} ms`, 'green');
}

function dispatchQuickBreach(sensorType) {
  closeSimModal();
  logTerminalLine(`[SIM] Injecting simulated ${sensorType.toUpperCase()} breach over mesh...`, 'amber');
  sendCommandToNode('BROADCAST', 'TRIGGER_DETECTION', {
    sensor_type: sensorType,
    confidence: 0.95,
    details: { simulated: true, injected_by: 'COMMAND-CENTER' }
  });
}

// Terminal Submit
function handleTerminalSubmit(e) {
  e.preventDefault();
  const target = document.getElementById('term-target-node').value;
  const cmdType = document.getElementById('term-command-type').value;
  const customParam = document.getElementById('term-custom-input').value.trim();

  let command = cmdType;
  let params = {};

  if (cmdType.startsWith('TRIGGER_')) {
    command = 'TRIGGER_DETECTION';
    const sType = cmdType.replace('TRIGGER_', '').toLowerCase();
    params = { sensor_type: sType, confidence: 0.95 };
  }

  if (customParam) {
    try {
      params = Object.assign(params, JSON.parse(customParam));
    } catch {
      params.text = customParam;
    }
  }

  sendCommandToNode(target, command, params);
  document.getElementById('term-custom-input').value = '';
}

function handleCommandPresetChange(val) {
  const input = document.getElementById('term-custom-input');
  if (val === 'CUSTOM') {
    input.placeholder = 'Enter command payload JSON, e.g. {"action": "LOCKDOWN"}';
    input.focus();
  } else {
    input.placeholder = 'Optional parameters or custom command...';
  }
}

function logTerminalLine(text, colorClass = 'info') {
  const body = document.getElementById('terminal-body');
  if (!body) return;
  const line = document.createElement('div');
  line.className = `term-line ${colorClass}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

// ============================================================================
// Data Fetching & Sync
// ============================================================================
async function fetchAllInitialData() {
  await Promise.all([
    fetchStatus(),
    fetchTopology(),
    fetchLatestSensors(),
    fetchAlertsAndEvents(),
    fetchMessages()
  ]);
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('header-node-id').textContent = data.node_id || 'COMMAND-CENTER';
    document.getElementById('val-outbox-delivered').textContent = `${data.outbox_delivered || 0} Delivered`;
    document.getElementById('badge-outbox').textContent = `${data.outbox_pending || 0} PENDING`;
  } catch (e) {
    console.warn('Status fetch error:', e);
  }
}

async function fetchTopology() {
  try {
    const res = await fetch('/api/nodes');
    const data = await res.json();
    renderNodesGrid(data);
  } catch (e) {
    console.warn('Topology fetch error:', e);
  }
}

async function fetchLatestSensors() {
  try {
    const res = await fetch('/api/sensors/latest');
    const data = await res.json();
    data.forEach(r => {
      const sId = r.sensor_id || 'UNKNOWN';
      const node = r.source_node || 'SYNAPSE';
      const key = `${node}:${sId}`;
      state.latestSensors.set(key, r);
    });
    renderSensorCards();
  } catch (e) {
    console.warn('Sensors fetch error:', e);
  }
}

async function fetchAlertsAndEvents() {
  try {
    const [alertsRes, eventsRes] = await Promise.all([
      fetch('/api/alerts?limit=50'),
      fetch('/api/events?limit=50')
    ]);
    const alertsData = await alertsRes.json();
    state.alerts = alertsData;
    renderAlertsFeed();
    updateAlertMetrics();
  } catch (e) {
    console.warn('Alerts fetch error:', e);
  }
}

async function fetchMessages() {
  try {
    const res = await fetch('/api/messages?limit=30');
    const data = await res.json();
    data.reverse().forEach(m => recordWirePacket(m));
  } catch (e) {
    console.warn('Messages fetch error:', e);
  }
}

async function refreshPeriodicMetrics() {
  fetchStatus();
  fetchTopology();
}

function refreshAllData() {
  logTerminalLine('[REFRESH] Synchronizing all mesh states...', 'cyan');
  fetchAllInitialData();
}

// ============================================================================
// Modals & Navigation
// ============================================================================
function switchTab(tabId) {
  state.activeTab = tabId;

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
    btn.setAttribute('aria-selected', 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  const activePanel = document.getElementById(`panel-${tabId}`);

  if (activeBtn) {
    activeBtn.classList.add('active');
    activeBtn.setAttribute('aria-selected', 'true');
  }
  if (activePanel) {
    activePanel.classList.add('active');
  }
}

function openSimModal() {
  document.getElementById('sim-modal-overlay').classList.add('active');
}

function closeSimModal(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('close-btn')) return;
  document.getElementById('sim-modal-overlay').classList.remove('active');
}

function openAddPeerModal() {
  document.getElementById('peer-modal-overlay').classList.add('active');
}

function closePeerModal(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('close-btn') && !e.target.classList.contains('ghost-btn')) return;
  document.getElementById('peer-modal-overlay').classList.remove('active');
}

async function handleRegisterPeerSubmit(e) {
  e.preventDefault();
  const nId = document.getElementById('input-peer-node-id').value.trim();
  const ip = document.getElementById('input-peer-ip').value.trim();
  const port = parseInt(document.getElementById('input-peer-port').value.trim(), 10);
  const vkey = document.getElementById('input-peer-vkey').value.trim() || null;

  try {
    const res = await fetch('/api/register_peer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nId, ip: ip, port: port, verify_key: vkey })
    });
    const data = await res.json();
    closePeerModal();
    logTerminalLine(`[PEER] Registered ${nId} (${ip}:${port}). Initiating store-and-forward sync.`, 'green');
    fetchTopology();
  } catch (err) {
    logTerminalLine(`[FAIL] Peer registration error: ${err.message}`, 'red');
  }
}

function exportTelemetryJSON() {
  window.open('/api/export', '_blank');
}
