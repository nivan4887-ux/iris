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

export interface VoiceQueryResult {
  query: string;
  response: string;
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

/**
 * Send a text question to Aura. Uses scene memory from the current session
 * to answer contextually (e.g. "what did I just pass?").
 */
export async function sendTextQuery(
  query: string,
  sessionId: string,
): Promise<VoiceQueryResult> {
  const base = await getApiUrl();
  const res = await fetch(`${base}/voice/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId, return_audio: false }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return { query: data.query ?? query, response: data.response ?? '' };
}

/**
 * Send a recorded audio clip to Aura. The server transcribes it with Whisper,
 * then answers using scene memory. Returns transcribed query + text response.
 */
export async function sendVoiceQuery(
  audioUri: string,
  sessionId: string,
): Promise<VoiceQueryResult> {
  const base = await getApiUrl();
  const formData = new FormData();
  formData.append('file', {
    uri: audioUri,
    name: 'query.m4a',
    type: 'audio/mp4',
  } as any);
  formData.append('session_id', sessionId);
  formData.append('return_audio', 'false');

  const res = await fetch(`${base}/voice/query-audio`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return { query: data.query ?? '', response: data.response ?? '' };
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
