import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  Vibration, StatusBar, Dimensions,
} from 'react-native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import { useKeepAwake } from 'expo-keep-awake';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { sendFrame, clearSession, checkHealth, FrameResult, AgentDecision } from '../services/auraApi';
import { audioPlayer } from '../services/audioPlayer';

const { width: W } = Dimensions.get('window');

const PRIORITY_COLOR: Record<number, string> = {
  1: '#ef4444', 2: '#f97316', 3: '#3b82f6', 4: '#10b981', 5: '#475569',
};
const PRIORITY_LABEL: Record<number, string> = {
  1: 'SAFETY', 2: 'NAV', 3: 'SOCIAL', 4: 'INFO', 5: 'BG',
};
const SESSION_ID = `aura-mobile-${Date.now()}`;
const AGENTS = ['hazard', 'navigation', 'social', 'ocr', 'suggestion'];

export default function HomeScreen({ navigation }: any) {
  useKeepAwake();
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  const [running, setRunning] = useState(false);
  const [facing] = useState<CameraType>('back');
  const [result, setResult] = useState<FrameResult | null>(null);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState<boolean | null>(null);
  const [frameCount, setFrameCount] = useState(0);
  const [spokeCount, setSpokeCount] = useState(0);
  const [latency, setLatency] = useState<number | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const processingRef = useRef(false);

  // Check backend connectivity on mount
  useEffect(() => {
    checkHealth().then(setConnected);
  }, []);

  useEffect(() => {
    audioPlayer.init();
    return () => { audioPlayer.interrupt(); };
  }, []);

  const processFrame = useCallback(async () => {
    if (!cameraRef.current || processingRef.current) return;
    processingRef.current = true;

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.4,
        base64: true,
        skipProcessing: true,
        exif: false,
      });
      if (!photo?.base64) return;

      setFrameCount(c => c + 1);
      const data = await sendFrame(photo.base64, SESSION_ID);
      setLatency(data.latency_ms);
      setResult(data);
      setError('');
      setConnected(true);

      if (data.should_speak) {
        setSpokeCount(c => c + 1);
        if (data.audio_base64) {
          audioPlayer.enqueue(data.audio_base64, data.priority);
        } else if (data.narration) {
          audioPlayer.speak(data.narration, data.priority);
        }
        if (data.priority === 1) {
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
          Vibration.vibrate([0, 200, 100, 200]);
        } else if (data.priority === 2) {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        }
      }
    } catch (err: any) {
      setError(err.message ?? 'Unknown error');
      setConnected(false);
    } finally {
      processingRef.current = false;
    }
  }, []);

  const start = useCallback(() => {
    setRunning(true);
    setError('');
    processFrame();
    timerRef.current = setInterval(processFrame, 2000);
  }, [processFrame]);

  const stop = useCallback(() => {
    setRunning(false);
    if (timerRef.current) clearInterval(timerRef.current);
    audioPlayer.interrupt();
  }, []);

  const reset = useCallback(async () => {
    stop();
    await clearSession(SESSION_ID);
    setResult(null);
    setFrameCount(0);
    setSpokeCount(0);
    setLatency(null);
    setError('');
  }, [stop]);

  if (!permission) return <View style={s.container} />;
  if (!permission.granted) {
    return (
      <View style={[s.container, s.center]}>
        <Text style={s.permTitle}>Camera Access Required</Text>
        <Text style={s.permText}>Aura needs camera access to analyze your surroundings and guide you safely.</Text>
        <TouchableOpacity style={s.permBtn} onPress={requestPermission}>
          <Text style={s.permBtnText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const priority = result?.priority ?? 5;
  const pc = PRIORITY_COLOR[priority] ?? '#475569';
  const decisions: AgentDecision[] = result?.dashboard?.agent_decisions ?? [];

  return (
    <View style={[s.container, { paddingTop: insets.top }]}>
      <StatusBar barStyle="light-content" backgroundColor="#090910" />

      {/* Header */}
      <View style={s.header}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={[s.dot, running && s.dotLive]} />
          <Text style={s.title}>AURA <Text style={{ color: '#7c3aed' }}>2.0</Text></Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <View style={[s.connDot, { backgroundColor: connected === true ? '#10b981' : connected === false ? '#ef4444' : '#475569' }]} />
          <TouchableOpacity onPress={() => navigation.navigate('Settings')} style={s.settingsBtn}>
            <Text style={{ color: '#64748b', fontSize: 18 }}>⚙</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Camera */}
      <View style={s.camWrap}>
        <CameraView ref={cameraRef} style={s.camera} facing={facing} />
        {running && <View style={[s.camBorder, { borderColor: pc }]} />}
        {running && (
          <View style={[s.liveBadge, { backgroundColor: pc + 'cc' }]}>
            <Text style={s.liveTxt}>● {PRIORITY_LABEL[priority]}</Text>
          </View>
        )}
      </View>

      {/* Controls */}
      <View style={s.controls}>
        <TouchableOpacity
          style={[s.mainBtn, { backgroundColor: running ? '#dc2626' : '#7c3aed' }]}
          onPress={running ? stop : start}
          activeOpacity={0.8}
        >
          <Text style={s.mainBtnTxt}>{running ? '■  Stop Aura' : '▶  Start Aura'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.iconBtn} onPress={reset}>
          <Text style={{ color: '#64748b', fontSize: 16 }}>↺</Text>
        </TouchableOpacity>
      </View>

      {/* Error banner */}
      {!!error && (
        <View style={s.errorBanner}>
          <Text style={s.errorTxt} numberOfLines={2}>{error}</Text>
        </View>
      )}

      <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>
        {/* Narration card */}
        {result?.narration ? (
          <View style={[s.narrationCard, { backgroundColor: pc + '18', borderColor: pc + '44' }]}>
            <Text style={[s.narrationLabel, { color: pc }]}>
              {PRIORITY_LABEL[priority]} · {result.winner_agent}
            </Text>
            <Text style={s.narrationText}>{result.narration}</Text>
            {(result.dashboard?.suppressed_elements?.length ?? 0) > 0 && (
              <Text style={s.suppressedTxt}>
                Suppressed: {result.dashboard.suppressed_elements.join(', ')}
              </Text>
            )}
          </View>
        ) : (
          !running && <Text style={s.placeholder}>Press Start Aura to begin.</Text>
        )}

        {/* Stats */}
        <View style={s.statsRow}>
          {[
            { label: 'Frames', val: frameCount },
            { label: 'Spoke', val: spokeCount },
            { label: 'Latency', val: latency ? `${latency}ms` : '—' },
            { label: 'People', val: result?.scene_graph?.people?.length ?? '—' },
          ].map(({ label, val }) => (
            <View key={label} style={s.statCell}>
              <Text style={s.statLabel}>{label}</Text>
              <Text style={s.statVal}>{val}</Text>
            </View>
          ))}
        </View>

        {/* Agent scores */}
        {decisions.length > 0 && (
          <View style={s.agentSection}>
            <Text style={s.sectionTitle}>AGENT SCORES</Text>
            {AGENTS.map(name => {
              const d = decisions.find(x => x.agent === name) ?? { agent: name, score: 0, message: '' };
              const isWinner = d.agent === result?.winner_agent;
              return (
                <View key={name} style={s.agentRow}>
                  <Text style={[s.agentName, isWinner && { color: pc }]}>{name}</Text>
                  <View style={s.barWrap}>
                    <View style={[s.bar, {
                      width: `${d.score * 100}%` as any,
                      backgroundColor: isWinner ? pc : '#334155',
                    }]} />
                  </View>
                  <Text style={s.agentScore}>{d.score > 0 ? d.score.toFixed(2) : '—'}</Text>
                  {isWinner && <View style={[s.winBadge, { backgroundColor: pc }]}><Text style={s.winTxt}>W</Text></View>}
                </View>
              );
            })}
          </View>
        )}

        {/* Scene info */}
        {result?.scene_graph && (
          <View style={s.sceneSection}>
            <Text style={s.sectionTitle}>SCENE</Text>
            <Text style={s.sceneSummary}>{result.scene_graph.spatial_summary}</Text>
            <View style={s.sceneRow}>
              <View style={s.sceneChip}>
                <Text style={s.chipLabel}>ENV</Text>
                <Text style={s.chipVal}>{result.scene_graph.environment}</Text>
              </View>
              <View style={s.sceneChip}>
                <Text style={s.chipLabel}>PATH</Text>
                <Text style={[s.chipVal, { color: result.scene_graph.path_clear ? '#10b981' : '#ef4444' }]}>
                  {result.scene_graph.path_clear ? 'Clear' : 'Blocked'}
                </Text>
              </View>
              <View style={s.sceneChip}>
                <Text style={s.chipLabel}>HAZARDS</Text>
                <Text style={[s.chipVal, { color: result.scene_graph.hazards.length ? '#ef4444' : '#10b981' }]}>
                  {result.scene_graph.hazards.length}
                </Text>
              </View>
            </View>
            {result.scene_graph.text_detected.length > 0 && (
              <Text style={s.textDetected}>
                Text: {result.scene_graph.text_detected.join(' · ')}
              </Text>
            )}
          </View>
        )}

        <View style={{ height: insets.bottom + 20 }} />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#090910' },
  center: { justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1e1e30',
  },
  title: { fontSize: 18, fontWeight: '700', color: '#e2e8f0' },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#475569' },
  dotLive: { backgroundColor: '#ef4444' },
  connDot: { width: 7, height: 7, borderRadius: 3.5 },
  settingsBtn: { padding: 4 },
  camWrap: { position: 'relative', width: W, height: W * 0.65, backgroundColor: '#000' },
  camera: { flex: 1 },
  camBorder: { position: 'absolute', inset: 0, borderWidth: 2 },
  liveBadge: {
    position: 'absolute', top: 8, left: 8,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4,
  },
  liveTxt: { color: '#fff', fontSize: 10, fontWeight: '700' },
  controls: {
    flexDirection: 'row', gap: 8, padding: 12,
    borderBottomWidth: 1, borderBottomColor: '#1e1e30',
  },
  mainBtn: {
    flex: 1, paddingVertical: 12, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center',
  },
  mainBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  iconBtn: {
    width: 44, height: 44, borderRadius: 8, backgroundColor: '#1e1e30',
    alignItems: 'center', justifyContent: 'center',
  },
  errorBanner: {
    backgroundColor: '#2d1b1b', borderBottomWidth: 1, borderBottomColor: '#5a2222',
    paddingHorizontal: 16, paddingVertical: 8,
  },
  errorTxt: { color: '#ef4444', fontSize: 12 },
  narrationCard: {
    margin: 12, padding: 14, borderRadius: 10, borderWidth: 1,
  },
  narrationLabel: { fontSize: 10, fontWeight: '700', marginBottom: 4, letterSpacing: 0.5 },
  narrationText: { fontSize: 17, fontWeight: '500', color: '#e2e8f0', lineHeight: 24 },
  suppressedTxt: { fontSize: 11, color: '#475569', marginTop: 6 },
  placeholder: { textAlign: 'center', color: '#475569', marginTop: 20, fontSize: 14 },
  statsRow: {
    flexDirection: 'row', marginHorizontal: 12, marginBottom: 8, gap: 6,
  },
  statCell: {
    flex: 1, backgroundColor: '#11111a', padding: 8, borderRadius: 6,
    alignItems: 'center',
  },
  statLabel: { fontSize: 9, color: '#64748b', marginBottom: 2 },
  statVal: { fontSize: 16, fontWeight: '700', color: '#e2e8f0', fontVariant: ['tabular-nums'] },
  agentSection: { marginHorizontal: 12, marginBottom: 8 },
  sectionTitle: { fontSize: 9, color: '#475569', fontWeight: '700', letterSpacing: 1, marginBottom: 8 },
  agentRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  agentName: { width: 72, fontSize: 11, fontWeight: '600', color: '#94a3b8' },
  barWrap: { flex: 1, height: 6, backgroundColor: '#1e1e30', borderRadius: 3, overflow: 'hidden' },
  bar: { height: '100%', borderRadius: 3 },
  agentScore: { width: 32, fontSize: 10, color: '#64748b', textAlign: 'right' },
  winBadge: { width: 16, height: 16, borderRadius: 3, alignItems: 'center', justifyContent: 'center' },
  winTxt: { color: '#fff', fontSize: 8, fontWeight: '700' },
  sceneSection: { marginHorizontal: 12, marginBottom: 8 },
  sceneSummary: { fontSize: 13, color: '#94a3b8', lineHeight: 18, marginBottom: 8 },
  sceneRow: { flexDirection: 'row', gap: 6, marginBottom: 6 },
  sceneChip: { flex: 1, backgroundColor: '#11111a', padding: 8, borderRadius: 6 },
  chipLabel: { fontSize: 8, color: '#475569', fontWeight: '700', marginBottom: 2 },
  chipVal: { fontSize: 13, fontWeight: '600', color: '#e2e8f0' },
  textDetected: { fontSize: 12, color: '#64748b', fontStyle: 'italic' },
  permTitle: { fontSize: 20, fontWeight: '700', color: '#e2e8f0', marginBottom: 12, textAlign: 'center' },
  permText: { fontSize: 14, color: '#94a3b8', textAlign: 'center', lineHeight: 22, marginBottom: 24 },
  permBtn: { backgroundColor: '#7c3aed', paddingHorizontal: 32, paddingVertical: 14, borderRadius: 8 },
  permBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  permBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
