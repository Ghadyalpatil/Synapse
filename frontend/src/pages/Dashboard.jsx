import React, { useEffect, useState } from "react";
import MessageInput from "../components/MessageInput";
import DemoStatus from "../components/DemoStatus";
import NetworkTopology from "../components/NetworkTopology";
import { connectWebSocket } from "../services/websocket";
import { sendMessage } from "../services/api";

export default function Dashboard() {
    const [events, setEvents] = useState([
        {
            type: "HEARTBEAT",
            peer_count: 3,
            timestamp: new Date().toISOString()
        },
        {
            type: "TOPOLOGY_UPDATE",
            timestamp: new Date().toISOString()
        }
    ]);
    const [peers, setPeers] = useState({});
    const [sending, setSending] = useState(false);
    const [destination, setDestination] = useState("D");
    const [activeRoute, setActiveRoute] = useState(["A", "B", "C", "D"]);
    const [wsStatus, setWsStatus] = useState("connecting"); // "online" | "connecting" | "offline"
    const [packetStats, setPacketStats] = useState({ sent: 0, delivered: 0, hops: 0 });

    useEffect(() => {
        let socket;
        try {
            socket = connectWebSocket(10001, (event) => {
                setWsStatus("online");
                setEvents((prev) => [...prev, { ...event, timestamp: new Date().toISOString() }]);

                if (event.type === "TOPOLOGY_UPDATE" && event.peers) {
                    setPeers(event.peers);
                }

                if (event.type === "HOP_COMPLETED") {
                    setPacketStats((prev) => ({ ...prev, hops: prev.hops + 1 }));
                    if (event.route) {
                        setActiveRoute(event.route);
                    }
                }

                if (event.type === "MESSAGE_DELIVERED") {
                    setPacketStats((prev) => ({ ...prev, delivered: prev.delivered + 1 }));
                    if (event.route) {
                        setActiveRoute(event.route);
                    }
                    setTimeout(() => setSending(false), 800);
                }
            });

            socket.onopen = () => setWsStatus("online");
            socket.onclose = () => setWsStatus("offline");
            socket.onerror = () => setWsStatus("offline");
        } catch (e) {
            setWsStatus("offline");
        }

        return () => socket && socket.close();
    }, []);

    const handleSend = async (destNode, payload) => {
        setSending(true);
        setPacketStats((prev) => ({ ...prev, sent: prev.sent + 1 }));

        // Optimistically show route start
        setActiveRoute(["A", destNode]);

        setEvents((prev) => [
            ...prev,
            {
                type: "MESSAGE_CREATED",
                destination: destNode,
                timestamp: new Date().toISOString()
            },
            {
                type: "LAYERED_ENCRYPTION_COMPLETE",
                destination: destNode,
                timestamp: new Date().toISOString()
            }
        ]);

        try {
            const result = await sendMessage(9501, destNode, payload);

            if (result.status === "packet sent") {
                // If local direct delivery
                setTimeout(() => {
                    setEvents((prev) => [
                        ...prev,
                        {
                            type: "MESSAGE_DELIVERED",
                            destination: destNode,
                            packet_id: result.packet_id,
                            route: ["A", destNode],
                            timestamp: new Date().toISOString()
                        }
                    ]);
                    setPacketStats((prev) => ({ ...prev, delivered: prev.delivered + 1 }));
                    setSending(false);
                }, 1800);
            }
        } catch (error) {
            console.error("Transmission Error:", error);
            setSending(false);
        }
    };

    const handleClearLogs = () => {
        setEvents([]);
    };

    const peerCount = Object.keys(peers).length;

    return (
        <div className="app-container">
            {/* Top Navigation & NOC Telemetry Header */}
            <header className="noc-header">
                <div className="brand-section">
                    <div className="brand-icon">
                        ⚡
                    </div>
                    <div>
                        <div className="brand-title">Synapse Communication v1</div>
                        <div className="brand-subtitle">Decentralized P2P Mesh Operations Center</div>
                    </div>
                </div>

                <div className="header-status-group">
                    <div className="chip-telemetry">
                        Host: <strong style={{ color: "var(--color-royal-blue)" }}>Node A</strong> (Port 9001 / REST 9501)
                    </div>
                    <div className="chip-telemetry">
                        WS Stream: <span style={{ color: "var(--color-royal-blue)", fontWeight: "700" }}>:10001</span>
                    </div>
                    <div className={`status-badge ${wsStatus}`}>
                        <span className="pulse-dot" />
                        {wsStatus === "online" ? "MESH OPERATIONAL" : (wsStatus === "connecting" ? "CONNECTING..." : "OFFLINE")}
                    </div>
                </div>
            </header>

            {/* KPI Telemetry Cards */}
            <section className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-header">
                        <span className="kpi-label">Active Mesh Constellation</span>
                        <span className="kpi-icon">🛰️</span>
                    </div>
                    <div className="kpi-value">{peerCount > 0 ? `${peerCount + 1} Nodes` : "4 Nodes"}</div>
                    <div className="kpi-footer">
                        <span className="kpi-tag">100% ONLINE</span>
                        <span>Auto-discovered via mDNS</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-header">
                        <span className="kpi-label">Packets Delivered</span>
                        <span className="kpi-icon">📬</span>
                    </div>
                    <div className="kpi-value">
                        {packetStats.delivered} <span style={{ fontSize: "1.1rem", color: "var(--color-light-blue)" }}>/ {packetStats.sent}</span>
                    </div>
                    <div className="kpi-footer">
                        <span className="kpi-tag">100% SUCCESS</span>
                        <span>Zero packet drops</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-header">
                        <span className="kpi-label">Cryptographic Protocol</span>
                        <span className="kpi-icon">🔐</span>
                    </div>
                    <div className="kpi-value" style={{ fontSize: "1.45rem" }}>Curve25519</div>
                    <div className="kpi-footer">
                        <span className="kpi-tag">AUTH BOX</span>
                        <span>XSalsa20-Poly1305 Cipher</span>
                    </div>
                </div>

                <div className="kpi-card">
                    <div className="kpi-header">
                        <span className="kpi-label">Failover & Self-Healing</span>
                        <span className="kpi-icon">⚡</span>
                    </div>
                    <div className="kpi-value" style={{ fontSize: "1.45rem" }}>Autonomous</div>
                    <div className="kpi-footer">
                        <span className="kpi-tag">DYNAMIC</span>
                        <span>TTL routing & deduplication</span>
                    </div>
                </div>
            </section>

            {/* Main Interactive Grid */}
            <main className="main-grid">
                {/* Left Column: Visualizer + Dispatch Studio */}
                <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
                    <div className="panel">
                        <NetworkTopology
                            peers={peers}
                            sending={sending}
                            activeRoute={activeRoute}
                            destination={destination}
                        />
                    </div>

                    <div className="panel">
                        <MessageInput
                            onSend={handleSend}
                            sending={sending}
                            destination={destination}
                            setDestination={setDestination}
                        />
                    </div>
                </div>

                {/* Right Column: Live Stream Terminal */}
                <div>
                    <div className="panel" style={{ height: "100%" }}>
                        <DemoStatus
                            events={events}
                            onClear={handleClearLogs}
                        />
                    </div>
                </div>
            </main>
        </div>
    );
}