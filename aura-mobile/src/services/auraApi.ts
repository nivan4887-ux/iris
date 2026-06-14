import AsyncStorage from '@react-native-async-storage/async-storage';

export const DEFAULT_API_URL = 'http://192.168.1.100:8000'; // update to your PC's LAN IP

export async function getApiUrl(): Promise<string> {
  return (await AsyncStorage.getItem('api_url')) ?? DEFAULT_API_URL;
}

export async function setApiUrl(url: string): Promise<void> {
  await AsyncStorage.setItem('api_url', url.replace(/\/$/, ''));
}

export interface FrameResult {
  narration: string;
  should_speak: boolean;
  audio_base64: string | null;
  priority: number;
  winner_agent: string;
  suppressed_count: number;
  latency_ms: number;
  scene_graph: SceneGraph;
  dashboard: DashboardEntry;
}

export interface SceneGraph {
  people: any[];
  hazards: any[];
  objects: any[];
  text_detected: string[];
  path_clear: boolean;
  environment: string;
  movement_detected: boolean;
  spatial_summary: string;
}

export interface AgentDecision {
  agent: string;
  priority: number;
  score: number;
  message: string;
  suppressed: boolean;
}

export interface DashboardEntry {
  timestamp: number;
  session_id: string;
  detected_elements: string[];
  suppressed_elements: string[];
  chosen_narration: string;
  priority_level: number;
  agent_decisions: AgentDecision[];
}

export async function sendFrame(
  frameBase64: string,
  sessionId: string,
  voice = 'nova',
): Promise<FrameResult> {
  const base = await getApiUrl();
  const res = await fetch(`${base}/stream/frame`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      frame_base64: frameBase64,
      session_id: sessionId,
      voice,
      return_audio: true,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`HTTP ${res.status}: ${err.slice(0, 120)}`);
  }
  return res.json();
}

export async function sendVoiceQuery(
  audioBase64: string,
  sessionId: string,
): Promise<{ answer: string; audio_base64: string | null }> {
  const base = await getApiUrl();
  const res = await fetch(`${base}/voice/query-audio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_base64: audioBase64, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function clearSession(sessionId: string): Promise<void> {
  const base = await getApiUrl();
  await fetch(`${base}/dashboard/history?session_id=${sessionId}`, { method: 'DELETE' });
}

export async function checkHealth(): Promise<boolean> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
