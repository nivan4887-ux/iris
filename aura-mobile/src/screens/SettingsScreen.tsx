import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, StyleSheet, TouchableOpacity,
  ScrollView, Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getApiUrl, setApiUrl, checkHealth, DEFAULT_API_URL } from '../services/auraApi';

export default function SettingsScreen({ navigation }: any) {
  const insets = useSafeAreaInsets();
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    getApiUrl().then(setUrl);
  }, []);

  const save = async () => {
    if (!url.startsWith('http')) {
      Alert.alert('Invalid URL', 'URL must start with http:// or https://');
      return;
    }
    await setApiUrl(url);
    Alert.alert('Saved', 'API URL updated. Restart scanning to apply.');
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    const ok = await checkHealth();
    setTestResult(ok ? '✓ Backend is reachable and healthy' : '✗ Cannot reach backend — check IP and that the server is running');
    setTesting(false);
  };

  const reset = async () => {
    setUrl(DEFAULT_API_URL);
    await setApiUrl(DEFAULT_API_URL);
  };

  return (
    <View style={[s.container, { paddingTop: insets.top }]}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtn}>
          <Text style={s.backTxt}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={s.title}>Settings</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 20 }}>
        {/* API URL */}
        <Text style={s.sectionLabel}>BACKEND API URL</Text>
        <Text style={s.hint}>
          Enter your computer's local IP address where the Aura backend is running.
          {'\n'}Example: http://192.168.1.42:8000
        </Text>
        <TextInput
          style={s.input}
          value={url}
          onChangeText={setUrl}
          placeholder="http://192.168.x.x:8000"
          placeholderTextColor="#475569"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          <TouchableOpacity style={[s.btn, { flex: 1, backgroundColor: '#7c3aed' }]} onPress={save}>
            <Text style={s.btnTxt}>Save</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.btn, { flex: 1, backgroundColor: '#1e1e30' }]} onPress={test} disabled={testing}>
            <Text style={s.btnTxt}>{testing ? 'Testing…' : 'Test Connection'}</Text>
          </TouchableOpacity>
        </View>
        {testResult && (
          <View style={[s.resultBanner, { backgroundColor: testResult.startsWith('✓') ? '#0d2b1e' : '#2d1b1b' }]}>
            <Text style={[s.resultTxt, { color: testResult.startsWith('✓') ? '#10b981' : '#ef4444' }]}>
              {testResult}
            </Text>
          </View>
        )}
        <TouchableOpacity style={[s.btn, { backgroundColor: '#1e1e30', marginTop: 8 }]} onPress={reset}>
          <Text style={[s.btnTxt, { color: '#64748b' }]}>Reset to Default</Text>
        </TouchableOpacity>

        {/* How to find IP */}
        <Text style={[s.sectionLabel, { marginTop: 32 }]}>HOW TO FIND YOUR PC'S IP</Text>
        <View style={s.infoCard}>
          {[
            'On Windows: open Command Prompt → type ipconfig → look for IPv4 Address',
            'The phone and PC must be on the same Wi-Fi network',
            'Start the backend: python run.py (in the Aura Backend folder)',
            'Default port is 8000 — do not change unless you modified the server',
          ].map((tip, i) => (
            <Text key={i} style={s.tip}>• {tip}</Text>
          ))}
        </View>

        {/* Priority legend */}
        <Text style={[s.sectionLabel, { marginTop: 32 }]}>PRIORITY LEVELS</Text>
        <View style={s.infoCard}>
          {[
            ['#ef4444', '1 · SAFETY', 'Stairs, vehicles, curbs — immediate warning'],
            ['#f97316', '2 · NAVIGATION', 'Path blocked, guidance needed'],
            ['#3b82f6', '3 · SOCIAL', 'People present nearby'],
            ['#10b981', '4 · INFO', 'Text, menus, signs'],
            ['#475569', '5 · BACKGROUND', 'Furniture, general objects'],
          ].map(([color, label, desc]) => (
            <View key={label} style={{ flexDirection: 'row', gap: 10, marginBottom: 8 }}>
              <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: color, marginTop: 3 }} />
              <View style={{ flex: 1 }}>
                <Text style={{ color: '#e2e8f0', fontSize: 12, fontWeight: '600' }}>{label}</Text>
                <Text style={{ color: '#64748b', fontSize: 11 }}>{desc}</Text>
              </View>
            </View>
          ))}
        </View>

        <View style={{ height: insets.bottom + 32 }} />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#090910' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#1e1e30',
  },
  backBtn: { padding: 4 },
  backTxt: { color: '#7c3aed', fontSize: 16 },
  title: { fontSize: 16, fontWeight: '700', color: '#e2e8f0' },
  sectionLabel: { fontSize: 10, color: '#475569', fontWeight: '700', letterSpacing: 1, marginBottom: 8 },
  hint: { fontSize: 13, color: '#64748b', lineHeight: 18, marginBottom: 12 },
  input: {
    backgroundColor: '#11111a', color: '#e2e8f0', fontSize: 14,
    borderWidth: 1, borderColor: '#1e1e30', borderRadius: 8,
    paddingHorizontal: 14, paddingVertical: 12,
  },
  btn: { paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  btnTxt: { color: '#fff', fontWeight: '600', fontSize: 14 },
  resultBanner: { marginTop: 10, padding: 12, borderRadius: 8 },
  resultTxt: { fontSize: 13, fontWeight: '500' },
  infoCard: { backgroundColor: '#11111a', padding: 14, borderRadius: 8 },
  tip: { color: '#94a3b8', fontSize: 12, lineHeight: 20, marginBottom: 4 },
});
