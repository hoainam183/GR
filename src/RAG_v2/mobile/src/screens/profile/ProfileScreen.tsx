import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { ProfileStackParamList } from '../../navigation/ProfileStack';
import { useAuth } from '../../hooks/useAuth';
import { useProfile } from '../../hooks/useProfile';
import { useAppTheme, type AppColors, type ThemePreference } from '../../theme/theme';

type ProfileNav = NativeStackNavigationProp<ProfileStackParamList, 'Profile'>;
const APPEARANCE_OPTIONS: Array<{ value: ThemePreference; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { value: 'system', label: 'Hệ thống', icon: 'phone-portrait-outline' },
  { value: 'light', label: 'Sáng', icon: 'sunny-outline' },
  { value: 'dark', label: 'Tối', icon: 'moon-outline' },
];

const ProfileScreen = () => {
  const navigation = useNavigation<ProfileNav>();
  const { logout } = useAuth();
  const { user, displayName, subtitle, studentId, majorCode } = useProfile();
  const { colors, preference, setPreference } = useAppTheme();
  const styles = createStyles(colors);
  const infoItems = [
    { icon: 'person-outline' as const, label: 'Họ tên', value: user?.full_name },
    { icon: 'card-outline' as const, label: 'MSSV', value: studentId },
    { icon: 'school-outline' as const, label: 'Khóa', value: user?.cohort },
    { icon: 'book-outline' as const, label: 'Ngành', value: user?.major },
    { icon: 'code-outline' as const, label: 'Mã ngành', value: majorCode || '-' },
    { icon: 'at-outline' as const, label: 'Username', value: user?.username || '-' },
    { icon: 'mail-outline' as const, label: 'Email', value: user?.email || '-' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.avatarSection}>
          <View style={styles.avatar}><Text style={styles.avatarText}>{displayName?.charAt(0)?.toUpperCase() ?? '?'}</Text></View>
          <Text style={styles.name}>{user?.full_name ?? 'Người dùng'}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          {studentId ? <Text style={styles.studentId}>MSSV: {studentId}</Text> : null}
        </View>
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Thông tin sinh viên</Text>
            <Pressable style={styles.editButton} onPress={() => navigation.navigate('EditProfile')}>
              <Ionicons name="create-outline" size={16} color={colors.primary} />
              <Text style={styles.editButtonText}>Chỉnh sửa</Text>
            </Pressable>
          </View>
          {infoItems.map((item, index) => (
            <View key={item.label} style={[styles.infoRow, index < infoItems.length - 1 && styles.infoRowBorder]}>
              <View style={styles.infoLeft}>
                <Ionicons name={item.icon} size={18} color={colors.mutedForeground} />
                <Text style={styles.infoLabel}>{item.label}</Text>
              </View>
              <Text style={styles.infoValue} numberOfLines={1}>{item.value ?? '-'}</Text>
            </View>
          ))}
        </View>
        <View style={styles.banner}>
          <Ionicons name="sparkles" size={18} color={colors.primary} />
          <Text style={styles.bannerText}>Thông tin khóa và ngành giúp hệ thống tư vấn quy chế, CTĐT chính xác hơn cho bạn.</Text>
        </View>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Giao diện</Text>
          <Text style={styles.sectionHint}>Đồng bộ màu với frontend và thiết bị của bạn.</Text>
          <View style={styles.appearanceRow}>
            {APPEARANCE_OPTIONS.map((option) => {
              const active = option.value === preference;
              return (
                <Pressable key={option.value} style={[styles.appearanceButton, active && styles.appearanceButtonActive]} onPress={() => setPreference(option.value)}>
                  <Ionicons name={option.icon} size={16} color={active ? colors.primary : colors.mutedForeground} />
                  <Text style={[styles.appearanceText, active && styles.appearanceTextActive]}>{option.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Hệ thống</Text>
          <MenuRow icon="information-circle-outline" title="Về ứng dụng" subtitle="HUST Assistant v1.0" colors={colors} styles={styles} />
          <MenuRow icon="notifications-outline" title="Thông báo" subtitle="Bật push tại tab Thông báo" colors={colors} styles={styles} last />
        </View>
        <Pressable style={styles.logoutButton} onPress={logout}>
          <Ionicons name="log-out-outline" size={20} color={colors.destructive} />
          <Text style={styles.logoutText}>Đăng xuất</Text>
        </Pressable>
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

const MenuRow = ({ icon, title, subtitle, colors, styles, last = false }: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  colors: AppColors;
  styles: ReturnType<typeof createStyles>;
  last?: boolean;
}) => (
  <View style={[styles.menuItem, last && styles.menuItemLast]}>
    <View style={styles.menuIcon}><Ionicons name={icon} size={20} color={colors.mutedForeground} /></View>
    <View style={styles.menuContent}><Text style={styles.menuLabel}>{title}</Text><Text style={styles.menuSubtitle}>{subtitle}</Text></View>
  </View>
);

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scrollContent: { paddingHorizontal: 20, paddingTop: 20 },
  avatarSection: { alignItems: 'center', marginBottom: 24 },
  avatar: { width: 80, height: 80, borderRadius: 40, backgroundColor: colors.primary, justifyContent: 'center', alignItems: 'center', marginBottom: 12 },
  avatarText: { fontSize: 32, fontWeight: '700', color: colors.primaryForeground },
  name: { fontSize: 22, fontWeight: '700', color: colors.foreground, marginBottom: 4 },
  subtitle: { fontSize: 14, color: colors.mutedForeground, marginBottom: 2 },
  studentId: { fontSize: 13, color: colors.mutedForeground },
  section: { backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 15, fontWeight: '600', color: colors.foreground, marginBottom: 4 },
  sectionHint: { color: colors.mutedForeground, fontSize: 12, marginBottom: 12 },
  editButton: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4, paddingHorizontal: 8 },
  editButtonText: { color: colors.primary, fontSize: 13, fontWeight: '600' },
  infoRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10 },
  infoRowBorder: { borderBottomWidth: 1, borderBottomColor: colors.border },
  infoLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  infoLabel: { fontSize: 14, color: colors.mutedForeground },
  infoValue: { fontSize: 14, color: colors.foreground, fontWeight: '500', maxWidth: 180, textAlign: 'right' },
  banner: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: colors.primarySoft, borderRadius: 12, padding: 14, marginBottom: 16 },
  bannerText: { color: colors.mutedForeground, fontSize: 13, lineHeight: 20, flex: 1 },
  appearanceRow: { flexDirection: 'row', gap: 8 },
  appearanceButton: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6, minHeight: 62, borderRadius: 10, backgroundColor: colors.secondary, borderWidth: 1, borderColor: colors.border },
  appearanceButtonActive: { backgroundColor: colors.primarySoft, borderColor: colors.primary },
  appearanceText: { color: colors.mutedForeground, fontSize: 12, fontWeight: '600' },
  appearanceTextActive: { color: colors.primary },
  menuItem: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  menuItemLast: { borderBottomWidth: 0, paddingBottom: 4 },
  menuIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: colors.secondary, justifyContent: 'center', alignItems: 'center' },
  menuContent: { flex: 1 },
  menuLabel: { fontSize: 15, color: colors.foreground, fontWeight: '500' },
  menuSubtitle: { fontSize: 12, color: colors.mutedForeground, marginTop: 2 },
  logoutButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: colors.card, paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border },
  logoutText: { color: colors.destructive, fontSize: 15, fontWeight: '600' },
});

export default ProfileScreen;
