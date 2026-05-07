/**
 * Profile screen — full user profile with sections and navigation.
 */

import React from 'react';
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { ProfileStackParamList } from '../../navigation/ProfileStack';
import { useAuth } from '../../hooks/useAuth';
import { useProfile } from '../../hooks/useProfile';

type ProfileNav = NativeStackNavigationProp<ProfileStackParamList, 'Profile'>;

const ProfileScreen = () => {
  const navigation = useNavigation<ProfileNav>();
  const { logout } = useAuth();
  const { user, displayName, subtitle, studentId, majorCode } = useProfile();

  const infoItems = [
    { icon: 'person-outline' as const, label: 'Họ tên', value: user?.full_name },
    { icon: 'card-outline' as const, label: 'MSSV', value: studentId },
    { icon: 'school-outline' as const, label: 'Khoá', value: user?.cohort },
    { icon: 'book-outline' as const, label: 'Ngành', value: user?.major },
    { icon: 'code-outline' as const, label: 'Mã ngành', value: majorCode || '—' },
    { icon: 'at-outline' as const, label: 'Username', value: user?.username || '—' },
    { icon: 'mail-outline' as const, label: 'Email', value: user?.email || '—' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Avatar section */}
        <View style={styles.avatarSection}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {displayName?.charAt(0)?.toUpperCase() ?? '?'}
            </Text>
          </View>
          <Text style={styles.name}>{user?.full_name ?? 'Người dùng'}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          {studentId ? (
            <Text style={styles.studentId}>MSSV: {studentId}</Text>
          ) : null}
        </View>

        {/* Student info section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Thông tin sinh viên</Text>
            <Pressable
              style={styles.editButton}
              onPress={() => navigation.navigate('EditProfile')}
            >
              <Ionicons name="create-outline" size={16} color="#6366f1" />
              <Text style={styles.editButtonText}>Chỉnh sửa</Text>
            </Pressable>
          </View>

          {infoItems.map((item, idx) => (
            <View
              key={item.label}
              style={[
                styles.infoRow,
                idx < infoItems.length - 1 && styles.infoRowBorder,
              ]}
            >
              <View style={styles.infoLeft}>
                <Ionicons name={item.icon} size={18} color="#64748b" />
                <Text style={styles.infoLabel}>{item.label}</Text>
              </View>
              <Text style={styles.infoValue} numberOfLines={1}>
                {item.value ?? '—'}
              </Text>
            </View>
          ))}
        </View>

        {/* Context info banner */}
        <View style={styles.banner}>
          <Ionicons name="sparkles" size={18} color="#6366f1" />
          <Text style={styles.bannerText}>
            Thông tin khoá và ngành giúp hệ thống tư vấn quy chế, CTĐT chính xác hơn cho bạn
          </Text>
        </View>

        {/* Menu section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Hệ thống</Text>

          <MenuItem
            icon="information-circle-outline"
            label="Về ứng dụng"
            subtitle="HUST Assistant v1.0"
            onPress={() => {}}
          />
          <MenuItem
            icon="shield-checkmark-outline"
            label="Bảo mật"
            subtitle="Mật khẩu, phiên đăng nhập"
            onPress={() => {}}
          />
        </View>

        {/* Logout */}
        <Pressable style={styles.logoutButton} onPress={logout}>
          <Ionicons name="log-out-outline" size={20} color="#ef4444" />
          <Text style={styles.logoutText}>Đăng xuất</Text>
        </Pressable>

        {/* Bottom padding */}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

// ─── MenuItem helper ─────────────────────────────────────────────────────────

interface MenuItemProps {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  subtitle?: string;
  onPress: () => void;
}

const MenuItem = ({ icon, label, subtitle, onPress }: MenuItemProps) => (
  <Pressable
    style={({ pressed }) => [
      styles.menuItem,
      pressed && styles.menuItemPressed,
    ]}
    onPress={onPress}
  >
    <View style={styles.menuIcon}>
      <Ionicons name={icon} size={20} color="#94a3b8" />
    </View>
    <View style={styles.menuContent}>
      <Text style={styles.menuLabel}>{label}</Text>
      {subtitle && <Text style={styles.menuSubtitle}>{subtitle}</Text>}
    </View>
    <Ionicons name="chevron-forward" size={18} color="#475569" />
  </Pressable>
);

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  // Avatar
  avatarSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#6366f1',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatarText: {
    fontSize: 32,
    fontWeight: '700',
    color: '#ffffff',
  },
  name: {
    fontSize: 22,
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#94a3b8',
    marginBottom: 2,
  },
  studentId: {
    fontSize: 13,
    color: '#64748b',
  },
  // Section
  section: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#e2e8f0',
    marginBottom: 4,
  },
  editButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  editButtonText: {
    color: '#6366f1',
    fontSize: 13,
    fontWeight: '600',
  },
  // Info rows
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  infoRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  infoLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  infoLabel: {
    fontSize: 14,
    color: '#94a3b8',
  },
  infoValue: {
    fontSize: 14,
    color: '#e2e8f0',
    fontWeight: '500',
    maxWidth: 180,
    textAlign: 'right',
  },
  // Banner
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
  },
  bannerText: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 20,
    flex: 1,
  },
  // Menu items
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  menuItemPressed: {
    opacity: 0.7,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#0f172a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  menuContent: {
    flex: 1,
  },
  menuLabel: {
    fontSize: 15,
    color: '#e2e8f0',
    fontWeight: '500',
  },
  menuSubtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  // Logout
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1e293b',
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  logoutText: {
    color: '#ef4444',
    fontSize: 15,
    fontWeight: '600',
  },
});

export default ProfileScreen;
