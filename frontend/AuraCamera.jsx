/**
 * AuraCamera — React component for real-time AI-guided camera narration.
 *
 * Usage:
 *   <AuraCamera apiBase="http://localhost:8000" sessionId="user-123" />
 *
 * Captures frames from device camera every `intervalMs` ms, sends to
 * POST /stream/frame, plays returned audio automatically.
 */
'use client';
import { useState, useRef, useEffect, useCallback } from 'react';

const PRIORITY_LABELS = { 1: 'SAFETY', 2: 'NAVIGATION', 3: 'SOCIAL', 4: 'INFO', 5: 'BG' };
const PRIORITY_COLORS = { 1: '#ef4444', 2: '#f97316', 3: '#3b82f6', 4: '#10b981', 5: '#475569' };

class AudioQueueManager {
    constructor() { this.queue = []; this.playing = false; this.current = null; }

    enqueue(b64, priority) {
        if (priority === 1) { this.interrupt(); this.queue.unshift({ b64 }); }
        else { this.queue.push({ b64 }); }
        this._next();
    }

    interrupt() {
        if (this.current) { this.current.pause(); this.current.currentTime = 0; }
        this.queue = []; this.playing = false; this.current = null;
    }

    _next() {
        if (this.playing || !this.queue.length) return;
        this.playing = true;
        const audio = new Audio(`data:audio/mp3;base64,${this.queue.shift().b64}`);
        this.current = audio;
        const done = () => { this.playing = false; this.current = null; this._next(); };
        audio.onended = done; audio.onerror = done;
        audio.play().catch(done);
    }
}

export default function AuraCamera({
    apiBase = 'http://localhost:8000',
    sessionId = 'default',
    intervalMs = 2000,
    voice = 'nova',
}) {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const timerRef = useRef(null);
    const audioRef = useRef(new AudioQueueManager());

    const [running, setRunning] = useState(false);
    const [narration, setNarration] = useState('');
    const [priority, setPriority] = useState(null);
    const [winnerAgent, setWinnerAgent] = useState(null);
    const [agentDecisions, setAgentDecisions] = useState([]);
    const [sceneGraph, setSceneGraph] = useState(null);
    const [latencyMs, setLatencyMs] = useState(null);
    const [frameCount, setFrameCount] = useState(0);
    const [spokeCount, setSpokeCount] = useState(0);
    const [suppressedItems, setSuppressedItems] = useState([]);
    const [error, setError] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);

    const captureAndSend = useCallback(async () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video?.srcObject || video.readyState < 2) return;

        canvas.getContext('2d').drawImage(video, 0, 0, 640, 480);
        const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];

        setFrameCount(c => c + 1);
        const t0 = Date.now();

        try {
            const res = await fetch(`${apiBase}/stream/frame`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ frame_base64: b64, session_id: sessionId, voice, return_audio: true }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            setLatencyMs(Date.now() - t0);
            setNarration(data.narration || '');
            setPriority(data.priority);
            setWinnerAgent(data.winner_agent);
            setAgentDecisions(data.dashboard?.agent_decisions || []);
            setSceneGraph(data.scene_graph);
            setSuppressedItems(data.dashboard?.suppressed_elements || []);
            setError('');

            if (data.should_speak && data.audio_base64) {
                setSpokeCount(c => c + 1);
                setIsSpeaking(true);
                audioRef.current.enqueue(data.audio_base64, data.priority);
                setTimeout(() => setIsSpeaking(false), 3000);
            }
        } catch (err) {
            setError(err.message);
        }
    }, [apiBase, sessionId, voice]);

    const start = useCallback(async () => {
        setError('');
        try {
            const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            streamRef.current = s;
            videoRef.current.srcObject = s;
            setRunning(true);
            captureAndSend();
            timerRef.current = setInterval(captureAndSend, intervalMs);
        } catch (err) {
            setError(`Camera error: ${err.message}`);
        }
    }, [captureAndSend, intervalMs]);

    const stop = useCallback(() => {
        clearInterval(timerRef.current);
        streamRef.current?.getTracks().forEach(t => t.stop());
        videoRef.current.srcObject = null;
        setRunning(false);
        audioRef.current.interrupt();
        setIsSpeaking(false);
    }, []);

    useEffect(() => () => stop(), []);

    const priorityColor = priority ? PRIORITY_COLORS[priority] : '#475569';

    return (
        <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 800, margin: '0 auto', padding: 16 }}>
            {/* Camera preview */}
            <div style={{ position: 'relative', background: '#000', borderRadius: 8, overflow: 'hidden', marginBottom: 12 }}>
                <video ref={videoRef} autoPlay muted playsInline style={{ width: '100%', display: 'block' }} />
                <canvas ref={canvasRef} width={640} height={480} style={{ display: 'none' }} />
                {running && (
                    <span style={{
                        position: 'absolute', top: 8, left: 8,
                        background: 'rgba(239,68,68,0.9)', color: '#fff',
                        padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
                    }}>● LIVE</span>
                )}
                {isSpeaking && (
                    <span style={{
                        position: 'absolute', top: 8, right: 8,
                        background: 'rgba(124,58,237,0.9)', color: '#fff',
                        padding: '2px 8px', borderRadius: 4, fontSize: 11,
                    }}>♪ Speaking</span>
                )}
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <button
                    onClick={running ? stop : start}
                    style={{
                        flex: 1, padding: '10px 16px', borderRadius: 6, border: 'none',
                        background: running ? '#dc2626' : '#7c3aed', color: '#fff',
                        fontWeight: 600, fontSize: 14, cursor: 'pointer',
                    }}
                >
                    {running ? '■ Stop Aura' : '▶ Start Aura'}
                </button>
            </div>

            {/* Narration output */}
            {narration && (
                <div style={{
                    padding: 16, borderRadius: 8,
                    background: `${priorityColor}18`,
                    border: `1px solid ${priorityColor}40`,
                    marginBottom: 12,
                }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: priorityColor, marginBottom: 6 }}>
                        {PRIORITY_LABELS[priority] || '—'} · {winnerAgent}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 500, color: '#e2e8f0' }}>{narration}</div>
                </div>
            )}

            {/* Suppressed items */}
            {suppressedItems.length > 0 && (
                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 12 }}>
                    Suppressed: {suppressedItems.map((s, i) => (
                        <span key={i} style={{ textDecoration: 'line-through', marginRight: 8 }}>{s}</span>
                    ))}
                </div>
            )}

            {/* Agent scores */}
            {agentDecisions.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    {agentDecisions.map(d => (
                        <div key={d.agent} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                            <span style={{ width: 80, fontSize: 12, fontWeight: 600 }}>{d.agent}</span>
                            <div style={{ flex: 1, height: 6, background: '#1e1e30', borderRadius: 3 }}>
                                <div style={{
                                    width: `${d.score * 100}%`, height: '100%', borderRadius: 3,
                                    background: d.agent === winnerAgent ? priorityColor : '#475569',
                                    transition: 'width 0.4s',
                                }} />
                            </div>
                            <span style={{ width: 36, fontSize: 11, textAlign: 'right', color: '#64748b' }}>
                                {d.score > 0 ? d.score.toFixed(2) : '—'}
                            </span>
                            {d.agent === winnerAgent && (
                                <span style={{ fontSize: 9, background: '#7c3aed', color: '#fff', padding: '1px 5px', borderRadius: 3 }}>WIN</span>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Stats row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
                {[
                    { label: 'Frames', value: frameCount },
                    { label: 'Narrations', value: spokeCount },
                    { label: 'Latency', value: latencyMs ? `${latencyMs}ms` : '—' },
                    { label: 'People', value: sceneGraph?.people?.length ?? '—' },
                ].map(({ label, value }) => (
                    <div key={label} style={{ background: '#11111a', padding: '8px 12px', borderRadius: 6 }}>
                        <div style={{ fontSize: 10, color: '#64748b' }}>{label}</div>
                        <div style={{ fontSize: 18, fontWeight: 600, fontFamily: 'monospace' }}>{value}</div>
                    </div>
                ))}
            </div>

            {error && (
                <div style={{ padding: '8px 12px', background: '#2d1b1b', borderRadius: 6, color: '#ef4444', fontSize: 12 }}>
                    {error}
                </div>
            )}
        </div>
    );
}
