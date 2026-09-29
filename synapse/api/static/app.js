// SYNAPSE Surveillance Dashboard Client
// 100% Zero-Cloud, connects directly to Raspberry Pi local API and WebSocket

let ws = null;

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("val-node-id").innerText = data.node_id;
    document.getElementById("node-badge").innerText = `${data.node_id} (ONLINE)`;
    document.getElementById("val-peers-count").innerText = data.online_peers_count;
    document.getElementById("val-outbox-pending").innerText = data.outbox_pending;
  } catch (e) {
    console.error("Status fetch failed", e);
  }
}

async function fetchTopology() {
  try {
    const res = await fetch("/api/nodes");
    if (!res.ok) return;
    const peers = await res.json();

    const tbody = document.getElementById("peers-table-body");
    if (!peers || peers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No peers registered yet</td></tr>';
      return;
    }

    tbody.innerHTML = peers.map(p => {
      let badgeClass = "badge-offline";
      if (p.status === "ONLINE") badgeClass = "badge-online";
      else if (p.status === "UNRESPONSIVE") badgeClass = "badge-unresponsive";

      const lat = p.latency_ms !== null ? `${p.latency_ms} ms` : "N/A";
      const loss = p.packet_loss !== null ? `${(p.packet_loss * 100).toFixed(1)}%` : "0.0%";

      return `
        <tr>
          <td><strong>${p.node_id}</strong></td>
          <td>${p.ip}:${p.port}</td>
          <td><span class="badge ${badgeClass}">${p.status}</span></td>
          <td style="font-family:var(--font-mono);">${lat}</td>
          <td style="font-family:var(--font-mono);">${loss}</td>
        </tr>
      `;
    }).join("");
  } catch (e) {
    console.error("Topology fetch failed", e);
  }
}

async function fetchEvents() {
  try {
    const res = await fetch("/api/events?limit=20");
    if (!res.ok) return;
    const events = await res.json();
    document.getElementById("val-events-count").innerText = events.length;

    const feed = document.getElementById("event-feed");
    if (!events || events.length === 0) return;

    feed.innerHTML = events.map(e => {
      const pClass = e.priority === "P0" ? "badge-p0" : (e.priority === "P1" ? "badge-p1" : "badge-p2");
      const dateStr = new Date(e.timestamp * 1000).toLocaleTimeString();
      const details = typeof e.details === "object" ? JSON.stringify(e.details) : e.details;

      return `
        <div class="feed-item">
          <div class="feed-header">
            <div>
              <span class="badge ${pClass}">${e.priority}</span>
              <strong>${e.event_type}</strong> from <span style="color:var(--accent-cyan);">${e.source_node}</span>
            </div>
            <span class="feed-time">${dateStr}</span>
          </div>
          <div style="color:var(--text-main); margin-top:0.25rem;">
            ${e.sensor_type ? `<strong>[${e.sensor_type.toUpperCase()}]</strong> ` : ""}${details}
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Events fetch failed", e);
  }
}

async function triggerSensor(type) {
  try {
    const res = await fetch("/api/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sensor_type: type, confidence: 0.95 })
    });
    const result = await res.json();
    console.log("Trigger result:", result);
    fetchEvents();
    fetchStatus();
  } catch (e) {
    alert("Trigger failed: " + e);
  }
}

async function handleSendMessage(event) {
  event.preventDefault();
  const target = document.getElementById("target-node").value.trim();
  const priority = document.getElementById("priority-select").value;
  const text = document.getElementById("msg-text").value.trim();

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        destination_node: target,
        message_type: "ALERT",
        priority: priority,
        payload: { message: text }
      })
    });
    const data = await res.json();
    document.getElementById("msg-text").value = "";
    fetchStatus();
    fetchEvents();
  } catch (e) {
    alert("Send error: " + e);
  }
}

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    document.getElementById("live-indicator").innerText = "LIVE WS";
    document.getElementById("live-indicator").className = "badge badge-online";
  };

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      console.log("[WS Incoming]", msg);
      fetchStatus();
      fetchTopology();
      fetchEvents();
    } catch (e) {
      console.error("WS error parsing", e);
    }
  };

  ws.onclose = () => {
    document.getElementById("live-indicator").innerText = "DISCONNECTED";
    document.getElementById("live-indicator").className = "badge badge-offline";
    setTimeout(initWebSocket, 3000);
  };
}

// Initial Boot
window.onload = () => {
  fetchStatus();
  fetchTopology();
  fetchEvents();
  initWebSocket();
  setInterval(fetchStatus, 4000);
  setInterval(fetchTopology, 6000);
};
