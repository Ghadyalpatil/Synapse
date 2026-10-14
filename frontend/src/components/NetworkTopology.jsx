import React, { useState } from "react";
import { motion } from "framer-motion";

export default function NetworkTopology({ peers = {}, sending = false, activeRoute = ["A", "B", "C", "D"], destination = "D" }) {
    const [selectedNode, setSelectedNode] = useState(null);

    const allNodeIds = ["A", "B", "C", "D"];
    const nodeCoords = {
        A: { cx: 70, cy: 180, label: "Node A (Host)", role: "Origin / Controller", port: 9001 },
        B: { cx: 240, cy: 90, label: "Node B (Relay 1)", role: "Mesh Intermediate", port: 9002 },
        C: { cx: 410, cy: 270, label: "Node C (Relay 2)", role: "Mesh Intermediate", port: 9003 },
        D: { cx: 580, cy: 180, label: "Node D (Target)", role: "Destination Receiver", port: 9004 }
    };

    const totalNodesCount = Object.keys(peers).length > 0 ? Object.keys(peers).length + 1 : 4;

    const links = [
        { from: "A", to: "B", active: peers["B"]?.online ?? true },
        { from: "B", to: "C", active: (peers["B"]?.online && peers["C"]?.online) ?? true },
        { from: "C", to: "D", active: (peers["C"]?.online && peers["D"]?.online) ?? true },
        { from: "A", to: "C", active: peers["C"]?.online ?? true },
        { from: "A", to: "D", active: peers["D"]?.online ?? true },
        { from: "B", to: "D", active: (peers["B"]?.online && peers["D"]?.online) ?? true }
    ];

    const routePoints = (activeRoute.length > 1 ? activeRoute : ["A", destination])
        .filter(id => nodeCoords[id])
        .map(id => nodeCoords[id]);

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div className="panel-header" style={{ marginBottom: 0 }}>
                <div className="panel-title">
                    <span style={{ color: "var(--color-light-blue)" }}>🌐</span>
                    Ad-Hoc Mesh Topology Visualizer
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "0.78rem", color: "var(--color-royal-blue)", fontFamily: "var(--font-mono)", fontWeight: "700" }}>
                        {totalNodesCount} NODES IN CONSTELLATION
                    </span>
                </div>
            </div>

            {/* Interactive SVG Canvas */}
            <div className="topology-stage">
                <div className="topology-grid-overlay" />

                <svg viewBox="0 0 650 360" className="mesh-svg-canvas">
                    <defs>
                        <radialGradient id="nodeGlowBlue" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stopColor="#60A5FA" stopOpacity="0.45" />
                            <stop offset="100%" stopColor="#60A5FA" stopOpacity="0" />
                        </radialGradient>
                        <linearGradient id="linkActiveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#60A5FA" />
                            <stop offset="50%" stopColor="#FFFFFF" />
                            <stop offset="100%" stopColor="#60A5FA" />
                        </linearGradient>
                    </defs>

                    {/* Mesh Interconnect Links */}
                    {links.map((link, idx) => {
                        const start = nodeCoords[link.from];
                        const end = nodeCoords[link.to];
                        const isHopping = sending && activeRoute.includes(link.from) && activeRoute.includes(link.to);

                        return (
                            <line
                                key={idx}
                                x1={start.cx}
                                y1={start.cy}
                                x2={end.cx}
                                y2={end.cy}
                                className={`mesh-link ${isHopping ? "active" : ""}`}
                                stroke={isHopping ? "url(#linkActiveGrad)" : (link.active ? "rgba(96, 165, 250, 0.35)" : "rgba(239, 68, 68, 0.2)")}
                                strokeDasharray={link.active && !isHopping ? "4 4" : "none"}
                            />
                        );
                    })}

                    {/* Animated Packet Flow Particle */}
                    {sending && routePoints.length >= 2 && (
                        <motion.circle
                            r="7"
                            fill="#FFFFFF"
                            filter="drop-shadow(0 0 10px #60A5FA) drop-shadow(0 0 4px #FFFFFF)"
                            initial={{ cx: routePoints[0].cx, cy: routePoints[0].cy }}
                            animate={{
                                cx: routePoints.map(p => p.cx),
                                cy: routePoints.map(p => p.cy)
                            }}
                            transition={{
                                duration: 3.2,
                                ease: "easeInOut",
                                repeat: Infinity
                            }}
                        />
                    )}

                    {/* Nodes */}
                    {allNodeIds.map(nodeId => {
                        const coord = nodeCoords[nodeId];
                        const peerData = peers[nodeId];
                        const isHost = nodeId === "A";
                        const isOnline = isHost ? true : (peerData ? peerData.online !== false : true);
                        const isSelected = selectedNode === nodeId;
                        const isDestination = destination === nodeId;

                        return (
                            <g
                                key={nodeId}
                                className="mesh-node-group"
                                onClick={() => setSelectedNode(nodeId)}
                            >
                                {/* Ambient halo */}
                                <circle
                                    cx={coord.cx}
                                    cy={coord.cy}
                                    r="42"
                                    fill={isOnline ? "url(#nodeGlowBlue)" : "transparent"}
                                />

                                {/* Outer Ring */}
                                <circle
                                    cx={coord.cx}
                                    cy={coord.cy}
                                    r="26"
                                    className={`node-outer-ring ${!isOnline ? "offline" : ""}`}
                                    stroke={isSelected || isDestination ? "#FFFFFF" : (isOnline ? "#60A5FA" : "#EF4444")}
                                    strokeWidth={isSelected || isDestination ? "3.5" : "2.5"}
                                    filter={isSelected || isDestination ? "drop-shadow(0 0 12px #FFFFFF)" : "drop-shadow(0 0 8px rgba(96, 165, 250, 0.7))"}
                                />

                                {/* Inner Ring */}
                                <circle
                                    cx={coord.cx}
                                    cy={coord.cy}
                                    r="22"
                                    fill="#071735"
                                />

                                {/* Node Letter */}
                                <text
                                    x={coord.cx}
                                    y={coord.cy}
                                    className="node-text-id"
                                    fill="#FFFFFF"
                                >
                                    {nodeId}
                                </text>

                                {/* Mini Status Dot */}
                                <circle
                                    cx={coord.cx + 18}
                                    cy={coord.cy - 18}
                                    r="5.5"
                                    fill={isOnline ? "#60A5FA" : "#EF4444"}
                                    filter={`drop-shadow(0 0 6px ${isOnline ? "#60A5FA" : "#EF4444"})`}
                                />

                                {/* Label below node */}
                                <text
                                    x={coord.cx}
                                    y={coord.cy + 42}
                                    className="node-text-label"
                                >
                                    {isHost ? "Node A (Host)" : `Node ${nodeId}`}
                                </text>
                                <text
                                    x={coord.cx}
                                    y={coord.cy + 55}
                                    fill="#93C5FD"
                                    fontSize="8.5"
                                    fontFamily="var(--font-mono)"
                                    textAnchor="middle"
                                    fontWeight="600"
                                >
                                    :{coord.port}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>

            {/* Peer Health / Discovered Nodes Row */}
            <div className="peer-table-container">
                <div style={{ fontSize: "0.8rem", fontWeight: "700", textTransform: "uppercase", color: "var(--color-light-blue)", letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Constellation Nodes (Auto-Discovered via mDNS)
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
                    {allNodeIds.map(nodeId => {
                        const coord = nodeCoords[nodeId];
                        const peerData = peers[nodeId];
                        const isHost = nodeId === "A";
                        const isOnline = isHost ? true : (peerData ? peerData.online !== false : true);
                        const defaultKeys = {
                            A: "9a82a9a5a7b05d59a4d457c4bc4642b3",
                            B: "4d854cc2a2cda34540087cffccff9bd0",
                            C: "480d2e6d89be2dcfc8fba3f9988785d3",
                            D: "e046828b8e875fee18dfd953f3951654"
                        };
                        const pubKey = peerData?.public_key || defaultKeys[nodeId];

                        return (
                            <div key={nodeId} className="peer-card-row">
                                <div className="peer-info-left">
                                    <div className="peer-avatar">
                                        {nodeId}
                                    </div>
                                    <div>
                                        <div className="peer-details-title">
                                            {isHost ? "Node A (Local Controller)" : `Node ${nodeId}`}
                                        </div>
                                        <div className="peer-details-addr">
                                            {peerData?.ip || "127.0.0.1"}:{coord.port}
                                        </div>
                                    </div>
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px" }}>
                                    <span className={`status-badge ${isOnline ? "" : "offline"}`} style={{ padding: "3px 10px", fontSize: "0.72rem" }}>
                                        <span className="pulse-dot" />
                                        {isOnline ? "ONLINE" : "OFFLINE"}
                                    </span>
                                    <span className="peer-key-pill" title={pubKey}>
                                        🔑 {pubKey.slice(0, 10)}...
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}