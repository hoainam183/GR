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
  COHORT_OPTIONS,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import { useProfile } from '../../hooks/useProfile';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Mode = 'ctdt' | 'regulations' | 'calendar' | 'compare';

const MODES: Array<{ key: Mode; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: 'ctdt', label: 'CTĐT', icon: 'school-outline' },
  { key: 'regulations', label: 'Quy định', icon: 'document-text-outline' },
  { key: 'calendar', label: 'Lịch', icon: 'calendar-outline' },
  { key: 'compare', label: 'So sánh', icon: 'git-compare-outline' },
];

const LookupScreen = () => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { majorCode, user } = useProfile();
  const [mode, setMode] = useState<Mode>('ctdt');
  const [query, setQuery] = useState('');
  const [cohort1, setCohort1] = useState(user?.cohort ?? 'K66');
  const [cohort2, setCohort2] = useState('K68');

  const lookupKey = query.trim();
  const { data = [], isLoading, refetch } = useQuery({
    queryKey: ['lookup', mode, lookupKey, majorCode, user?.cohort, cohort1, cohort2],
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
        cohort1,
        cohort2,
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
        <Ionicons name="search-outline" size={18} color={colors.mutedForeground} />
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          placeholder={placeholder}
          placeholderTextColor={colors.mutedForeground}
          returnKeyType="search"
          onSubmitEditing={() => refetch()}
          accessibilityLabel="Tìm kiếm"
        />
        <Pressable
          style={styles.searchButton}
          onPress={() => refetch()}
          accessibilityLabel="Tìm kiếm"
          accessibilityRole="button"
        >
          <Ionicons name="arrow-forward" size={18} color={colors.primaryForeground} />
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.modeScroller}
        contentContainerStyle={styles.modeRow}
        keyboardShouldPersistTaps="handled"
      >
        {MODES.map((item) => {
          const active = item.key === mode;
          return (
            <Pressable
              key={item.key}
              style={({ pressed }) => [
                styles.modeButton,
                active && styles.modeButtonActive,
                pressed && styles.modeButtonPressed,
              ]}
              onPress={() => setMode(item.key)}
              hitSlop={4}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={item.label}
            >
              <Ionicons
                name={item.icon}
                size={16}
                color={active ? colors.primaryForeground : colors.mutedForeground}
              />
              <Text style={[styles.modeText, active && styles.modeTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {/* Compare mode cohort selectors */}
      {mode === 'compare' && (
        <View style={styles.compareRow}>
          {[
            { label: 'Khóa 1', value: cohort1, onChange: setCohort1 },
            { label: 'Khóa 2', value: cohort2, onChange: setCohort2 },
          ].map(({ label, value, onChange }) => (
            <View key={label} style={styles.cohortSelector}>
              <Text style={styles.cohortLabel}>{label}</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {COHORT_OPTIONS.map((c) => (
                  <Pressable
                    key={c}
                    style={[styles.cohortChip, value === c && styles.cohortChipActive]}
                    onPress={() => onChange(c)}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: value === c }}
                    accessibilityLabel={`${label} ${c}`}
                  >
                    <Text style={[styles.cohortChipText, value === c && styles.cohortChipTextActive]}>
                      {c}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          ))}
        </View>
      )}

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <FlatList
          data={data}
          renderItem={renderItem}
          keyExtractor={(item, index) => `${item.title}-${index}`}
          contentContainerStyle={[
            styles.results,
            data.length === 0 && styles.resultsEmpty,
          ]}
          keyboardShouldPersistTaps="handled"
          ListEmptyComponent={
            <Text style={styles.emptyText}>Không có kết quả phù hợp.</Text>
          }
        />
      )}
    </SafeAreaView>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: { color: colors.foreground, fontSize: 20, fontWeight: '700' },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 12,
    paddingLeft: 14,
    paddingRight: 6,
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  input: { flex: 1, color: colors.foreground, fontSize: 15, paddingVertical: 12 },
  searchButton: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeScroller: {
    flexGrow: 0,
    flexShrink: 0,
    height: 56,
  },
  modeRow: {
    paddingHorizontal: 16,
    gap: 8,
    paddingBottom: 10,
    alignItems: 'center',
  },
  modeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.secondary,
    borderWidth: 1,
    borderColor: colors.border,
    alignSelf: 'flex-start',
  },
  modeButtonActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  modeButtonPressed: { opacity: 0.86 },
  modeText: { color: colors.mutedForeground, fontSize: 13, fontWeight: '600' },
  modeTextActive: { color: colors.primaryForeground },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingBottom: 24 },
  results: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 24,
    gap: 12,
  },
  resultsEmpty: { flexGrow: 1, justifyContent: 'center' },
  resultCard: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 14,
  },
  resultHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  resultTitle: { flex: 1, color: colors.foreground, fontSize: 15, fontWeight: '700' },
  badge: {
    color: colors.primary,
    backgroundColor: colors.primarySoft,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    fontSize: 11,
    overflow: 'hidden',
    flexShrink: 0,
  },
  summary: { color: colors.subtleForeground, fontSize: 13, lineHeight: 19, marginTop: 8 },
  emptyText: { color: colors.mutedForeground, textAlign: 'center', marginTop: 40 },
  compareRow: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
    paddingBottom: 10,
  },
  cohortSelector: { flex: 1, gap: 4 },
  cohortLabel: { color: colors.mutedForeground, fontSize: 12, fontWeight: '600' },
  cohortChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.secondary,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: 6,
  },
  cohortChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  cohortChipText: { color: colors.mutedForeground, fontSize: 13, fontWeight: '600' },
  cohortChipTextActive: { color: colors.primaryForeground },
});

export default LookupScreen;
