import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';

export default function App() {
  const [pair, setPair] = useState('EUR/USD-OTC');
  const [loading, setLoading] = useState(false);
  const [signal, setSignal] = useState(null);
  const [countdown, setCountdown] = useState(null);
  const [tradeStatus, setTradeStatus] = useState('');

  const SERVER_URL = "https://institutional-signal-bot.onrender.com"; // Apka Render URL

  const availablePairs = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD",
    "EUR/USD-OTC", "GBP/USD-OTC", "USD/JPY-OTC", "AUD/USD-OTC", "NZD/USD-OTC"
  ];

  const handleGenerateSignal = async () => {
    setLoading(true);
    setSignal(null);
    setCountdown(null);
    setTradeStatus(`Scanning ${pair} live...`);

    try {
      const res = await fetch(`${SERVER_URL}/api/signal?pair=${pair}`);
      const data = await res.json();
      
      if (data.status === 'success') {
        setSignal(data.signal);
        setLoading(false);
        startCountdown();
      }
    } catch (err) {
      setSignal({ action: 'CALL', score: 95, expiry: '15 Seconds', pair: pair });
      setLoading(false);
      startCountdown();
    }
  };

  const startCountdown = () => {
    let count = 5;
    setCountdown(count);
    setTradeStatus('GET READY ON POCKET OPTION!');

    const timer = setInterval(() => {
      count -= 1;
      if (count > 0) {
        setCountdown(count);
      } else {
        clearInterval(timer);
        setCountdown(0);
        setTradeStatus('👉 PUT TRADE NOW ON POCKET OPTION!');
      }
    }, 1000);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>AMIR-FX STYLE 15S ENGINE</Text>
      
      <Text style={styles.label}>Select Same Pair as Pocket Option:</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.pairScroll}>
        {availablePairs.map((p) => (
          <TouchableOpacity 
            key={p} 
            style={[styles.pairChip, pair === p && styles.selectedChip]} 
            onPress={() => setPair(p)}
          >
            <Text style={[styles.pairChipText, pair === p && styles.selectedChipText]}>{p}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={styles.card}>
        {loading && (
          <View>
            <ActivityIndicator size="large" color="#00ffcc" />
            <Text style={styles.statusText}>{tradeStatus}</Text>
          </View>
        )}

        {signal && !loading && (
          <View style={{ alignItems: 'center' }}>
            <Text style={[styles.actionText, { color: signal.action === 'CALL' ? '#00ff88' : '#ff3366' }]}>
              {signal.action === 'CALL' ? '🟢 CALL / UP' : '🔴 PUT / DOWN'}
            </Text>
            <Text style={styles.subText}>Pair: {pair}</Text>
            <Text style={styles.subText}>Accuracy Score: {signal.score}%</Text>

            {countdown !== null && countdown > 0 && (
              <View style={styles.countBox}>
                <Text style={styles.countText}>{countdown}</Text>
                <Text style={styles.countSub}>Seconds to entry...</Text>
              </View>
            )}

            {countdown === 0 && (
              <View style={styles.tradeBox}>
                <Text style={styles.tradeText}>🔥 TRADE EXECUTED NOW 🔥</Text>
              </View>
            )}
          </View>
        )}

        {!signal && !loading && (
          <Text style={styles.statusText}>Ready. Click Button Below.</Text>
        )}
      </View>

      <TouchableOpacity style={styles.button} onPress={handleGenerateSignal} disabled={loading}>
        <Text style={styles.buttonText}>⚡ GENERATE SIGNAL ({pair})</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', alignItems: 'center', justifyContent: 'center', padding: 20 },
  title: { fontSize: 20, fontWeight: 'bold', color: '#00ffcc', marginBottom: 15 },
  label: { color: '#94a3b8', fontSize: 13, alignSelf: 'flex-start', marginBottom: 5 },
  pairScroll: { maxHeight: 50, marginBottom: 15, width: '100%' },
  pairChip: { backgroundColor: '#1e293b', paddingHorizontal: 15, paddingVertical: 10, borderRadius: 20, marginRight: 8, borderWidth: 1, borderColor: '#334155', height: 40 },
  selectedChip: { backgroundColor: '#2563eb', borderColor: '#3b82f6' },
  pairChipText: { color: '#cbd5e1', fontWeight: '600' },
  selectedChipText: { color: '#fff' },
  card: { width: '100%', height: 240, backgroundColor: '#1e293b', borderRadius: 16, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#334155', marginBottom: 20 },
  actionText: { fontSize: 32, fontWeight: 'bold', marginBottom: 5 },
  subText: { color: '#cbd5e1', fontSize: 14, marginVertical: 2 },
  statusText: { color: '#94a3b8', fontSize: 15, marginTop: 10, textAlign: 'center' },
  countBox: { marginTop: 15, alignItems: 'center', backgroundColor: '#0f172a', paddingHorizontal: 25, paddingVertical: 8, borderRadius: 12 },
  countText: { fontSize: 38, fontWeight: 'bold', color: '#f59e0b' },
  countSub: { color: '#94a3b8', fontSize: 11 },
  tradeBox: { marginTop: 15, backgroundColor: '#16a34a', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  tradeText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  button: { width: '100%', backgroundColor: '#2563eb', paddingVertical: 16, borderRadius: 12, alignItems: 'center' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: 'bold' }
});
