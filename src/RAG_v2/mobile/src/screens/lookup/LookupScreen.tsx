import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';
import type { LookupDocument } from '@rag/shared';
import {
  lookupCalendar,
  lookupCompare,
  lookupCTDT,
  lookupRegulations,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import { useProfile } from '../../hooks/useProfile';

type Mode = 'ctdt' | 'regulations' | 'calendar' | 'compare';

const MODES: Array<{ key: Mode; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: 'ctdt', label: 'CTĐT', icon: 'school-outline' },
  { key: 'regulations', label: 'Quy định', icon: 'document-text-outline' },
  { key: 'calendar', label: 'Lịch', icon: 'calendar-outline' },
  { key: 'compare', label: 'So sánh', icon: 'git-compare-outline' },
];

const LookupScreen = () => {
  const { majorCode, user } = useProfile();
  const [mode, setMode] = useState<Mode>('ctdt');
  const [query, setQuery] = useState('');

  const lookupKey = query.trim();
  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ['lookup', mode, lookupKey, majorCode, user?.cohort],
    queryFn: async () => {
      if (mode === 'ctdt') {
        const result = await lookupCTDT(apiClient, lookupKey || majorCode || 'IT1', user?.cohort);
        return result.documents;
      }
      if (mode === 'regulations') {
        const result = await lookupRegulations(apiClient, {
          category: lookupKey || undefined,
          cohort: user?.cohort,
        });
        return result.regulations;
      }
      if (mode === 'calendar') {
        const result = await lookupCalendar(apiClient, lookupKey || undefined);
        return result.events;
      }
      const compare = await lookupCompare(apiClient, {
        topic: lookupKey || 'ngoại ngữ',
        cohort1: 'K66',
        cohort2: 'K68',
      });
      return [
        {
          title: `So sánh ${compare.comparison.cohort1} và ${compare.comparison.cohort2}`,
          summary: compare.comparison.answer,
          collection: 'quydinh',
          score: 0,
          metadata: {},
        },
      ];
    },
    staleTime: 5 * 60 * 1000,
  });

  const placeholder = useMemo(() => {
    if (mode === 'ctdt') return majorCode || 'IT1';
    if (mode === 'regulations') return 'ngoại ngữ, học bổng, tốt nghiệp...';
    if (mode === 'compare') return 'ngoại ngữ, học bổng, tốt nghiệp...';
    return '20252, đăng ký học phần...';
  }, [majorCode, mode]);

  const renderItem = ({ item }: { item: LookupDocument }) => (
    <View style={styles.resultCard}>
      <View style={styles.resultHeader}>
        <Text style={styles.resultTitle} numberOfLines={2}>
          {item.title}
        </Text>
        {item.collection ? (
          <Text style={styles.badge}>{item.collection}</Text>
        ) : null}
      </View>
      <Text style={styles.summary} numberOfLines={5}>
        {item.summary}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Tra cứu</Text>
      </View>

      <View style={styles.searchBox}>
        <Ionicons name="search-outline" size={18} color="#64748b" />
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          placeholder={placeholder}
          placeholderTextColor="#64748b"
          returnKeyType="search"
          onSubmitEditing={() => refetch()}
        />
        <Pressable style={styles.searchButton} onPress={() => refetch()}>
          <Ionicons name="arrow-forward" size={18} color="#ffffff" />
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.modeRow}
      >
        {MODES.map((item) => {
          const active = item.key === mode;
          return (
            <Pressable
              key={item.key}
              style={[styles.modeButton, active && styles.modeButtonActive]}
              onPress={() => setMode(item.key)}
            >
              <Ionicons
                name={item.icon}
                size={16}
                color={active ? '#ffffff' : '#94a3b8'}
              />
              <Text style={[styles.modeText, active && styles.modeTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#6366f1" />
        </View>
      ) : (
        <FlatList
          data={data}
          renderItem={renderItem}
          keyExtractor={(item, index) => `${item.title}-${index}`}
          contentContainerStyle={styles.results}
          ListEmptyComponent={
            <Text style={styles.emptyText}>Không có kết quả phù hợp.</Text>
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerTitle: { color: '#f8fafc', fontSize: 20, fontWeight: '700' },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    margin: 16,
    paddingLeft: 14,
    paddingRight: 6,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  input: { flex: 1, color: '#f8fafc', fontSize: 15, paddingVertical: 12 },
  searchButton: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#6366f1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeRow: { paddingHorizontal: 16, gap: 8, paddingBottom: 12 },
  modeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 10,
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
  },
  modeButtonActive: { backgroundColor: '#6366f1', borderColor: '#6366f1' },
  modeText: { color: '#94a3b8', fontSize: 13, fontWeight: '600' },
  modeTextActive: { color: '#ffffff' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  results: { padding: 16, gap: 12 },
  resultCard: {
    backgroundColor: '#1e293b',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 12,
    padding: 14,
  },
  resultHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  resultTitle: { flex: 1, color: '#f8fafc', fontSize: 15, fontWeight: '700' },
  badge: {
    color: '#a5b4fc',
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    fontSize: 11,
    overflow: 'hidden',
  },
  summary: { color: '#cbd5e1', fontSize: 13, lineHeight: 19, marginTop: 8 },
  emptyText: { color: '#64748b', textAlign: 'center', marginTop: 40 },
});

export default LookupScreen;
