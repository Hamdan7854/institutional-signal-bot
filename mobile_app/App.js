import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView } from 'react-native';

export default function App() {
  const [signal, setSignal] = useState({ pair: 'EUR/USD', action: 'CALL', countdown: 60, score: 92 });
  const [timer, setTimer] = useState(60);

  useEffect(() => {
    const interval = setInterval(() => {
      setTimer((prev) => (prev > 1 ? prev - 1 : 60));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.header}>INSTITUTIONAL SIGNAL ENGINE</Text>
      
      <View style={styles.card}>
        <Text style={styles.pairText}>{signal.pair}</Text>
        <Text style={signal.action === 'CALL' ? styles.callText : styles.putText}>
          {signal.action}
        </Text>
        
        <View style={styles.timerContainer}>
          <Text style={styles.timerLabel}>Expiry Countdown:</Text>
          <Text style={styles.timerVal}>{timer}s</Text>
        </View>

        <Text style={styles.scoreText}>Confluence Score: {signal.score}/100</Text>
      </View>

      <TouchableOpacity style={styles.refreshBtn}>
        <Text style={styles.btnText}>MANUAL SCAN PAIRS</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d1117', alignItems: 'center', justifyContent: 'center' },
  header: { fontSize: 18, fontWeight: 'bold', color: '#58a6ff', marginBottom: 20 },
  card: { width: '85%', padding: 25, backgroundColor: '#161b22', borderRadius: 12, alignItems: 'center', borderWidth: 1, borderColor: '#30363d' },
  pairText: { fontSize: 24, fontWeight: 'bold', color: '#ffffff' },
  callText: { fontSize: 36, fontWeight: 'bold', color: '#2ea043', marginVertical: 10 },
  putText: { fontSize: 36, fontWeight: 'bold', color: '#da3633', marginVertical: 10 },
  timerContainer: { flexDirection: 'row', alignItems: 'center', marginVertical: 10 },
  timerLabel: { color: '#8b949e', fontSize: 14, marginRight: 5 },
  timerVal: { color: '#ffa657', fontSize: 18, fontWeight: 'bold' },
  scoreText: { color: '#8b949e', marginTop: 10 },
  refreshBtn: { marginTop: 25, backgroundColor: '#238636', paddingVertical: 12, paddingHorizontal: 30, borderRadius: 8 },
  btnText: { color: '#ffffff', fontWeight: 'bold' }
});
