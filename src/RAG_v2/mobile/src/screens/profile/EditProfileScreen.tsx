/**
 * Edit profile screen — allows updating student info.
 * Calls PATCH /auth/me to persist changes.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { ProfileStackParamList } from '../../navigation/ProfileStack';
import { apiClient } from '../../services/api';
import { setUserProfile } from '../../services/secureStorage';
import { useAuthStore } from '../../stores/authStore';
import { useProfile } from '../../hooks/useProfile';
import { API_PATHS } from '@rag/shared';

type Nav = NativeStackNavigationProp<ProfileStackParamList, 'EditProfile'>;

const COHORT_OPTIONS = ['K64', 'K65', 'K66', 'K67', 'K68', 'K69', 'K70'];
const MAJOR_OPTIONS = [
  { label: 'CNTT', code: 'IT1' },
  { label: 'CNTT Việt Nhật', code: 'IT-EP' },
  { label: 'CNTT Global ICT', code: 'IT2' },
  { label: 'Khoa học máy tính', code: 'IT-E7' },
  { label: 'Kỹ thuật máy tính', code: 'CE' },
  { label: 'ĐTVT', code: 'ET1' },
  { label: 'Tự động hóa', code: 'EE' },
  { label: 'Cơ điện tử', code: 'ME' },
  { label: 'Khác', code: '' },
];

const EditProfileScreen = () => {
  const navigation = useNavigation<Nav>();
  const { user } = useProfile();
  const setAuth = useAuthStore((s) => s.setAuth);
  const accessToken = useAuthStore((s) => s.accessToken);

  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [cohort, setCohort] = useState(user?.cohort ?? '');
  const [major, setMajor] = useState(user?.major ?? '');
  const [majorCode, setMajorCode] = useState(user?.major_code ?? '');
  const [loading, setLoading] = useState(false);

  const selectMajor = (label: string, code: string) => {
    setMajor(label);
    setMajorCode(code);
  };

  const handleSave = async () => {
    if (!fullName.trim()) {
      Alert.alert('Lỗi', 'Họ tên không được để trống');
      return;
    }
    if (!cohort) {
      Alert.alert('Lỗi', 'Vui lòng chọn khoá');
      return;
    }
    if (!major) {
      Alert.alert('Lỗi', 'Vui lòng chọn ngành');
      return;
    }

    setLoading(true);
    try {
      const body: Record<string, string> = {};
      if (fullName.trim() !== user?.full_name) body.full_name = fullName.trim();
      if (cohort !== user?.cohort) body.cohort = cohort;
      if (major !== user?.major) body.major = major;

      // Only send if there are changes
      if (Object.keys(body).length === 0) {
        navigation.goBack();
        return;
      }

      const response = await apiClient.patch(API_PATHS.AUTH_ME, body);
      const updatedUser = response.data;

      // Update local state
      if (accessToken) {
        setAuth(accessToken, updatedUser);
        await setUserProfile(updatedUser);
      }

      navigation.goBack();
    } catch (err: unknown) {
      let message = 'Cập nhật thất bại.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (
          err as { response?: { data?: { detail?: string } } }
        ).response?.data?.detail;
        if (typeof detail === 'string') message = detail;
      }
      Alert.alert('Lỗi', message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable style={styles.headerBack} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color="#94a3b8" />
        </Pressable>
        <Text style={styles.headerTitle}>Chỉnh sửa hồ sơ</Text>
        <View style={{ width: 40 }} />
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Read-only fields */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Thông tin không thể thay đổi</Text>

            <View style={styles.readOnlyRow}>
              <Text style={styles.readOnlyLabel}>MSSV</Text>
              <Text style={styles.readOnlyValue}>{user?.student_id ?? '—'}</Text>
            </View>
            <View style={styles.readOnlyRow}>
              <Text style={styles.readOnlyLabel}>Username</Text>
              <Text style={styles.readOnlyValue}>{user?.username ?? '—'}</Text>
            </View>
          </View>

          {/* Editable fields */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Thông tin cá nhân</Text>

            {/* Full name */}
            <View style={styles.field}>
              <Text style={styles.label}>Họ và tên</Text>
              <TextInput
                style={styles.input}
                value={fullName}
                onChangeText={setFullName}
                placeholder="Nguyễn Văn A"
                placeholderTextColor="#64748b"
              />
            </View>

            {/* Cohort */}
            <View style={styles.field}>
              <Text style={styles.label}>Khoá</Text>
              <View style={styles.chipGroup}>
                {COHORT_OPTIONS.map((c) => (
                  <Pressable
                    key={c}
                    style={[styles.chip, cohort === c && styles.chipActive]}
                    onPress={() => setCohort(c)}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        cohort === c && styles.chipTextActive,
                      ]}
                    >
                      {c}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>

            {/* Major */}
            <View style={styles.field}>
              <Text style={styles.label}>Ngành</Text>
              <View style={styles.chipGroup}>
                {MAJOR_OPTIONS.map((opt) => (
                  <Pressable
                    key={opt.label}
                    style={[
                      styles.chip,
                      major === opt.label && styles.chipActive,
                    ]}
                    onPress={() => selectMajor(opt.label, opt.code)}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        major === opt.label && styles.chipTextActive,
                      ]}
                    >
                      {opt.label}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          </View>

          {/* Save button */}
          <Pressable
            style={[styles.saveButton, loading && styles.saveDisabled]}
            onPress={handleSave}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color="#ffffff" />
            ) : (
              <>
                <Ionicons name="checkmark" size={20} color="#ffffff" />
                <Text style={styles.saveText}>Lưu thay đổi</Text>
              </>
            )}
          </Pressable>

          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
  },
  headerBack: {
    padding: 8,
  },
  headerTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: '#f8fafc',
    textAlign: 'center',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  section: {
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#94a3b8',
    marginBottom: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  readOnlyRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  readOnlyLabel: {
    fontSize: 14,
    color: '#64748b',
  },
  readOnlyValue: {
    fontSize: 14,
    color: '#94a3b8',
    fontWeight: '500',
  },
  field: {
    marginBottom: 16,
  },
  label: {
    color: '#e2e8f0',
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#0f172a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#334155',
    paddingHorizontal: 14,
    paddingVertical: 11,
    color: '#f8fafc',
    fontSize: 15,
  },
  chipGroup: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    backgroundColor: '#0f172a',
  },
  chipActive: {
    borderColor: '#6366f1',
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
  },
  chipText: {
    color: '#94a3b8',
    fontSize: 13,
    fontWeight: '500',
  },
  chipTextActive: {
    color: '#a5b4fc',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#6366f1',
    paddingVertical: 14,
    borderRadius: 12,
  },
  saveDisabled: {
    opacity: 0.7,
  },
  saveText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default EditProfileScreen;
