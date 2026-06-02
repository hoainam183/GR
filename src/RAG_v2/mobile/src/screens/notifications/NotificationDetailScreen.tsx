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
type ArticleLink = NonNullable<Metadata['article_links']>[number];
const URL_PATTERN = /https?:\/\/[^\s)]+/g;

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

const normalizeBodyTitle = (line?: string) =>
  (line ?? '').replace(/^[\s•\-]+/, '').trim();

const getArticleLinksFromBody = (body: string): ArticleLink[] => {
  const lines = body.split(/\r?\n/);
  const links: ArticleLink[] = [];
  const seenUrls = new Set<string>();

  lines.forEach((line, index) => {
    const urls = line.match(URL_PATTERN) ?? [];
    urls.forEach((url) => {
      if (seenUrls.has(url)) return;
      seenUrls.add(url);
      const previousTitle = normalizeBodyTitle(lines[index - 1]);
      links.push({
        title: previousTitle || 'Bài viết liên quan',
        url,
      });
    });
  });

  return links;
};

const getArticleLinks = (notification: NotificationItem) => {
  const metadataLinks = (notification.metadata?.article_links ?? []).filter((link) => link.url?.trim());
  return metadataLinks.length ? metadataLinks : getArticleLinksFromBody(notification.body);
};

const getIntroText = (notification: NotificationItem, links: ArticleLink[]) => {
  if (links.length > 0) {
    return `${links.length} bài viết mới đã được thu thập. Mở từng bài để xem nội dung gốc.`;
  }
  return notification.body || 'Lần cập nhật này không có bài viết mới để mở.';
};

const NotificationDetailScreen = ({ route, navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const { notification } = route.params;
  const links = getArticleLinks(notification);
  const introText = getIntroText(notification, links);

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
            <Ionicons name="newspaper-outline" size={22} color={colors.primary} />
          </View>
          <View style={styles.heroBody}>
            <Text style={styles.title}>{notification.title}</Text>
            <Text style={styles.body}>{introText}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Bài viết mới</Text>
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
                  {!!link.summary && (
                    <Text style={styles.linkSummary} numberOfLines={2}>{link.summary}</Text>
                  )}
                  <View style={styles.linkMetaRow}>
                    {!!link.source && <Text style={styles.linkSource}>{link.source}</Text>}
                    <Text style={styles.linkUrl} numberOfLines={1}>{link.url}</Text>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.mutedForeground} />
              </Pressable>
            ))
          ) : (
            <View style={styles.emptyArticles}>
              <Ionicons name="document-text-outline" size={22} color={colors.mutedForeground} />
              <Text style={styles.emptyText}>
                Lần cập nhật này không có bài viết mới để mở. Các thông báo mới sau khi crawl có bài viết sẽ hiển thị danh sách link tại đây.
              </Text>
            </View>
          )}
        </View>
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
  linkCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
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
  linkSummary: { color: colors.subtleForeground, fontSize: 13, lineHeight: 18 },
  linkMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  linkSource: {
    color: colors.primary,
    backgroundColor: colors.primarySoft,
    borderRadius: 6,
    overflow: 'hidden',
    paddingHorizontal: 6,
    paddingVertical: 2,
    fontSize: 11,
    fontWeight: '700',
  },
  linkUrl: { flex: 1, color: colors.mutedForeground, fontSize: 12 },
  emptyArticles: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  emptyText: { color: colors.mutedForeground, fontSize: 13, lineHeight: 19 },
});

export default NotificationDetailScreen;
