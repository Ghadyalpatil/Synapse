import React, { useState, useRef, useEffect } from "react";

export default function DemoStatus({ events = [], onClear }) {
    const [filter, setFilter] = useState("all");
    const terminalEndRef = useRef(null);

    // Auto-scroll on new entries
    useEffect(() => {
        terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [events]);

    const filteredEvents = events.filter(e => {
        if (filter === "all") return true;
        if (filter === "packets") return ["MESSAGE_CREATED", "HOP_COMPLETED", "MESSAGE_DELIVERED"].includes(e.type);
        if (filter === "crypto") return ["LAYERED_ENCRYPTION_COMPLETE", "MESSAGE_DECRYPTED", "DECRYPTION_FAILED"].includes(e.type);
        if (filter === "heartbeats") return ["HEARTBEAT", "TOPOLOGY_UPDATE"].includes(e.type);
        return true;
    });

    const getEventConfig = (event) => {
        const timeStr = event.timestamp 
            ? new Date(event.timestamp).toLocaleTimeString() 
            : new Date().toLocaleTimeString();

        switch (event.type) {
            case "MESSAGE_CREATED":
                return {
                    classType: "created",
                    badgeClass: "badge-created",
                    badgeText: "CREATED",
                    icon: "📦",
                    title: `Packet Initialized: ${event.packet_id ? event.packet_id.slice(0, 8) + '...' : 'UUID'}`,
                    time: timeStr
                };
            case "LAYERED_ENCRYPTION_COMPLETE":
                return {
                    classType: "encrypted",
                    badgeClass: "badge-encrypted",
                    badgeText: "ENCRYPTED",
                    icon: "🔐",
                    title: "Curve25519 Box Encrypted (XSalsa20-Poly1305)",
                    time: timeStr
                };
            case "HOP_COMPLETED":
                return {
                    classType: "hopped",
                    badgeClass: "badge-hopped",
                    badgeText: `HOP #${event.hop_count || 1}`,
                    icon: "📡",
                    title: `Packet Relayed Across Mesh Node`,
                    route: event.route,
                    time: timeStr
                };
            case "MESSAGE_DECRYPTED":
                return {
                    classType: "decrypted",
                    badgeClass: "badge-decrypted",
                    badgeText: "DECRYPTED",
                    icon: "🔓",
                    title: `Payload Authenticated & Decrypted: "${event.message || 'Cipher verified'}"`,
                    time: timeStr
                };
            case "MESSAGE_DELIVERED":
                return {
                    classType: "delivered",
                    badgeClass: "badge-delivered",
                    badgeText: "DELIVERED",
                    icon: "✅",
                    title: `End-to-End Delivery Confirmed at Node ${event.destination || 'D'}`,
                    route: event.route,
                    time: timeStr
                };
            case "HEARTBEAT":
                return {
                    classType: "heartbeat",
                    badgeClass: "badge-heartbeat",
                    badgeText: "HEARTBEAT",
                    icon: "💓",
                    title: `Mesh Node Pulse — ${event.peer_count || 3} active peers connected`,
                    time: timeStr
                };
            case "TOPOLOGY_UPDATE":
                return {
                    classType: "heartbeat",
                    badgeClass: "badge-heartbeat",
                    badgeText: "SYNC",
                    icon: "🔄",
                    title: `Routing Table Synced across Constellation`,
                    time: timeStr
                };
            default:
                return {
                    classType: "created",
                    badgeClass: "badge-created",
                    badgeText: event.type || "EVENT",
                    icon: "⚡",
                    title: JSON.stringify(event),
                    time: timeStr
                };
        }
    };

    return (
        <div className="console-panel">
            <div className="panel-header">
                <div className="panel-title">
                    <span style={{ color: "var(--color-light-blue)" }}>📟</span>
                    NOC Live Transmission Stream
                </div>
                {onClear && (
                    <button type="button" className="panel-action-btn" onClick={onClear}>
                        Clear Stream
                    </button>
                )}
            </div>

            {/* Filter Tabs */}
            <div className="feed-filter-bar">
                {[
                    { id: "all", label: `All (${events.length})` },
                    { id: "packets", label: "Packets" },
                    { id: "crypto", label: "Crypto" },
                    { id: "heartbeats", label: "Heartbeats" }
                ].map(tab => (
                    <button
                        key={tab.id}
                        type="button"
                        className={`filter-btn ${filter === tab.id ? "active" : ""}`}
                        onClick={() => setFilter(tab.id)}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Terminal Window */}
            <div className="terminal-window">
                {filteredEvents.length === 0 ? (
                    <div style={{ color: "var(--text-muted)", textAlign: "center", padding: "40px 0" }}>
                        Waiting for mesh network transmissions...
                    </div>
                ) : (
                    filteredEvents.map((event, idx) => {
                        const cfg = getEventConfig(event);
                        return (
                            <div key={idx} className={`terminal-entry ${cfg.classType}`}>
                                <span className="entry-time">{cfg.time}</span>
                                <span className={`entry-badge ${cfg.badgeClass}`}>{cfg.badgeText}</span>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div className="entry-message">
                                        <span style={{ marginRight: "6px" }}>{cfg.icon}</span>
                                        {cfg.title}
                                    </div>
                                    {cfg.route && cfg.route.length > 0 && (
                                        <div className="route-trail">
                                            <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>Route:</span>
                                            {cfg.route.map((node, rIdx) => (
                                                <React.Fragment key={rIdx}>
                                                    <span style={{ fontWeight: "700" }}>Node {node}</span>
                                                    {rIdx < cfg.route.length - 1 && <span className="route-arrow">→</span>}
                                                </React.Fragment>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
                <div ref={terminalEndRef} />
            </div>
        </div>
    );
}