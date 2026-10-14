import React, { useState } from "react";

export default function MessageInput({ onSend, sending, destination, setDestination }) {
    const [payload, setPayload] = useState("Mesh packet telemetry payload - Curve25519 end-to-end encrypted.");

    const presetPayloads = [
        { label: "⚡ P2P Ping", text: "PING - P2P connectivity test via Zeroconf discovery" },
        { label: "📊 Telemetry Data", text: "TELEMETRY: CPU=2.4%, RAM=66MB, TTL=5, Status=Optimal" },
        { label: "🚨 Emergency Alert", text: "ALERT: Autonomous failover routing verification" },
        { label: "🔐 Curve25519 Box", text: "AUTHENTICATED_PAYLOAD: XSalsa20-Poly1305 multi-hop cipher" }
    ];

    const handleSubmit = (e) => {
        e?.preventDefault();
        if (!destination || !payload.trim() || sending) return;
        onSend(destination, payload.trim());
    };

    return (
        <div className="dispatch-studio">
            <div className="panel-header" style={{ marginBottom: 0 }}>
                <div className="panel-title">
                    <span style={{ color: "var(--color-light-blue)" }}>📤</span>
                    Packet Dispatch Studio
                </div>
                <span style={{ fontSize: "0.72rem", color: "var(--color-light-blue)", fontFamily: "var(--font-mono)" }}>
                    E2E ENCRYPTED (PORT 9501)
                </span>
            </div>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                <div className="form-group">
                    <label className="form-label">
                        <span>Target Destination Node</span>
                        <span style={{ color: "var(--color-royal-blue)", fontFamily: "var(--font-mono)", fontWeight: "700" }}>
                            Selected: Node {destination}
                        </span>
                    </label>
                    <select
                        className="input-select"
                        value={destination}
                        onChange={(e) => setDestination(e.target.value)}
                        disabled={sending}
                    >
                        <option value="D">Node D (Target Receiver — Port 9004 / REST 9504)</option>
                        <option value="B">Node B (Relay Node 1 — Port 9002 / REST 9502)</option>
                        <option value="C">Node C (Relay Node 2 — Port 9003 / REST 9503)</option>
                    </select>
                </div>

                <div className="form-group">
                    <div className="form-label">
                        <span>Quick Preset Telemetry</span>
                    </div>
                    <div className="preset-chips">
                        {presetPayloads.map((preset, idx) => (
                            <button
                                key={idx}
                                type="button"
                                className="preset-chip-btn"
                                onClick={() => setPayload(preset.text)}
                                disabled={sending}
                            >
                                {preset.label}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="form-group">
                    <div className="form-label">
                        <span>Message Payload (Plaintext before Hop Box Encryption)</span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.7rem", color: "var(--text-muted)" }}>
                            {payload.length} bytes
                        </span>
                    </div>
                    <textarea
                        className="input-textarea"
                        rows={3}
                        placeholder="Enter message payload to transmit over mesh..."
                        value={payload}
                        onChange={(e) => setPayload(e.target.value)}
                        disabled={sending}
                    />
                </div>

                <button
                    type="submit"
                    className="send-btn"
                    disabled={sending || !destination || !payload.trim()}
                >
                    {sending ? (
                        <>
                            <span className="pulse-dot" style={{ backgroundColor: "#ffffff" }} />
                            <span>Encrypting & Routing Through Mesh...</span>
                        </>
                    ) : (
                        <>
                            <span>🚀</span>
                            <span>Transmit Authenticated Packet → Node {destination}</span>
                        </>
                    )}
                </button>
            </form>
        </div>
    );
}