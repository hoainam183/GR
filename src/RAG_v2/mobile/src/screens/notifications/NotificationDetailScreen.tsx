import React from 'react';
import {
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { NotificationItem } from '@rag/shared';
import type { NotificationStackParamList } from '../../navigation/NotificationStack';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Props = NativeStackScreenProps<NotificationStackParamList, 'NotificationDetail'>;

type Metadata = NonNullable<NotificationItem['metadata']>;

const formatDateTime = (value?: string) => {
  if (!value) return 'Không rõ thời gian';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatMetaValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return 'Không có';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Có' : 'Không';
  if (Array.isArray(value)) return `${value.length} mục`;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const visibleMetadataEntries = (metadata?: Metadata | null) =>
  Object.entries(metadata ?? {}).filter(([key]) => key !== 'article_links');

const getArticleLinks = (metadata?: Metadata | null) =>
  (metadata?.article_links ?? []).filter((link) => link.url?.trim());

const NotificationDetailScreen = ({ route, navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const { notification } = route.params;
  const links = getArticleLinks(notification.metadata);
  const metadataEntries = visibleMetadataEntries(notification.metadata);

  const openLink = async (url: string) => {
    try {
      const canOpen = await Linking.canOpenURL(url);
      if (!canOpen) {
        Alert.alert('Không mở được liên kết', url);
        return;
      }
      await Linking.openURL(url);
    } catch {
      Alert.alert('Không mở được liên kết', 'Vui lòng thử lại sau.');
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Pressable style={styles.headerButton} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color={colors.mutedForeground} />
        </Pressable>
        <View style={styles.headerText}>
          <Text style={styles.headerTitle} numberOfLines={1}>Chi tiết thông báo</Text>
          <Text style={styles.headerSubtitle}>{formatDateTime(notification.created_at)}</Text>
        </View>
        <View style={styles.readBadge}>
          <Ionicons
            name={notification.read ? 'checkmark-circle-outline' : 'ellipse'}
            size={14}
            color={notification.read ? colors.success : colors.primary}
          />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Ionicons name="notifications-outline" size={22} color={colors.primary} />
          </View>
          <View style={styles.heroBody}>
            <Text style={styles.type}>{notification.type}</Text>
            <Text style={styles.title}>{notification.title}</Text>
            <Text style={styles.body}>{notification.body || 'Không có nội dung.'}</Text>
          </View>
        </View>

        {metadataEntries.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Thông tin cập nhật</Text>
            <View style={styles.metaGrid}>
              {metadataEntries.map(([key, value]) => (
                <View key={key} style={styles.metaItem}>
                  <Text style={styles.metaLabel}>{key}</Text>
                  <Text style={styles.metaValue} numberOfLines={2}>
                    {formatMetaValue(value)}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Liên kết liên quan</Text>
            <Text style={styles.linkCount}>{links.length}</Text>
          </View>
          {links.length ? (
            links.map((link, index) => (
              <Pressable
                key={`${link.url}-${index}`}
                style={({ pressed }) => [styles.linkCard, pressed && styles.pressed]}
                onPress={() => openLink(link.url)}
              >
                <View style={styles.linkIcon}>
                  <Ionicons name="open-outline" size={16} color={colors.primary} />
                </View>
                <View style={styles.linkBody}>
                  <Text style={styles.linkTitle} numberOfLines={2}>
                    {link.title?.trim() || 'Bài viết liên quan'}
                  </Text>
                  <Text style={styles.linkUrl} numberOfLines={1}>{link.url}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.mutedForeground} />
              </Pressable>
            ))
          ) : (
            <Text style={styles.emptyText}>Không có liên kết đính kèm.</Text>
          )}
        </View>

        {notification.related_doc_id ? (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Tài liệu liên quan</Text>
            <Text style={styles.relatedId}>{notification.related_doc_id}</Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 8,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: { flex: 1 },
  headerTitle: { color: colors.foreground, fontSize: 17, fontWeight: '700' },
  headerSubtitle: { color: colors.mutedForeground, fontSize: 12, marginTop: 2 },
  readBadge: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: { padding: 16, gap: 14, paddingBottom: 28 },
  heroCard: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
  },
  heroIcon: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
  },
  heroBody: { flex: 1, gap: 6 },
  type: { color: colors.primary, fontSize: 12, fontWeight: '700' },
  title: { color: colors.foreground, fontSize: 18, fontWeight: '700', lineHeight: 24 },
  body: { color: colors.subtleForeground, fontSize: 14, lineHeight: 21 },
  section: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    gap: 10,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionTitle: { color: colors.foreground, fontSize: 15, fontWeight: '700' },
  linkCount: {
    minWidth: 26,
    textAlign: 'center',
    color: colors.primary,
    backgroundColor: colors.primarySoft,
    borderRadius: 8,
    overflow: 'hidden',
    paddingVertical: 3,
    fontSize: 12,
    fontWeight: '700',
  },
  metaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  metaItem: {
    minWidth: '47%',
    flex: 1,
    backgroundColor: colors.cardMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 10,
    gap: 4,
  },
  metaLabel: { color: colors.mutedForeground, fontSize: 11, fontWeight: '700' },
  metaValue: { color: colors.foreground, fontSize: 14, fontWeight: '700' },
  linkCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: colors.cardMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 10,
  },
  pressed: { opacity: 0.82 },
  linkIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
  },
  linkBody: { flex: 1, gap: 3 },
  linkTitle: { color: colors.foreground, fontSize: 14, fontWeight: '700' },
  linkUrl: { color: colors.mutedForeground, fontSize: 12 },
  emptyText: { color: colors.mutedForeground, fontSize: 13, lineHeight: 19 },
  relatedId: { color: colors.subtleForeground, fontSize: 13, lineHeight: 19 },
});

export default NotificationDetailScreen;
