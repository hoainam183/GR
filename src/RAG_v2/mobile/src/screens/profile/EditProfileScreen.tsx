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
  Modal,
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
import {
  API_PATHS,
  COHORT_OPTIONS,
  MAJOR_OPTIONS,
  type MajorOption,
} from '@rag/shared';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Nav = NativeStackNavigationProp<ProfileStackParamList, 'EditProfile'>;

const EditProfileScreen = () => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const navigation = useNavigation<Nav>();
  const { user } = useProfile();
  const setUser = useAuthStore((s) => s.setUser);

  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [cohort, setCohort] = useState(user?.cohort ?? '');
  const [major, setMajor] = useState(user?.major ?? '');
  const [majorCode, setMajorCode] = useState(user?.major_code ?? '');
  const [majorPickerOpen, setMajorPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const selectedMajor = MAJOR_OPTIONS.find((option) => option.code === majorCode);

  const selectMajor = (option: MajorOption) => {
    setMajor(option.name);
    setMajorCode(option.code);
    setMajorPickerOpen(false);
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
    if (!selectedMajor || major !== selectedMajor.name) {
      Alert.alert('Lỗi', 'Vui lòng chọn ngành');
      return;
    }
    const majorOption = selectedMajor;

    setLoading(true);
    try {
      const body: Record<string, string> = {};
      if (fullName.trim() !== user?.full_name) body.full_name = fullName.trim();
      if (cohort !== user?.cohort) body.cohort = cohort;
      if (majorOption.name !== user?.major) body.major = majorOption.name;
      if (majorOption.code !== user?.major_code) body.major_code = majorOption.code;

      // Only send if there are changes
      if (Object.keys(body).length === 0) {
        navigation.goBack();
        return;
      }

      const response = await apiClient.patch(API_PATHS.AUTH_ME, body);
      const updatedUser = response.data;

      // Update local state — only the user object; tokens stay untouched.
      setUser(updatedUser);
      await setUserProfile(updatedUser);

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
          <Ionicons name="chevron-back" size={24} color={colors.mutedForeground} />
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
                placeholderTextColor={colors.mutedForeground}
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
              <Pressable
                style={styles.selectorButton}
                onPress={() => setMajorPickerOpen(true)}
              >
                <View style={styles.selectorTextGroup}>
                  <Text
                    style={[
                      styles.selectorText,
                      !selectedMajor && styles.selectorPlaceholder,
                    ]}
                  >
                    {selectedMajor ? selectedMajor.name : 'Chọn ngành học'}
                  </Text>
                  {selectedMajor && (
                    <Text style={styles.selectorMeta}>Mã ngành: {selectedMajor.code}</Text>
                  )}
                </View>
                <Ionicons name="chevron-down" size={18} color={colors.mutedForeground} />
              </Pressable>
              <Modal
                visible={majorPickerOpen}
                transparent
                animationType="fade"
                onRequestClose={() => setMajorPickerOpen(false)}
              >
                <View style={styles.modalBackdrop}>
                  <Pressable
                    style={StyleSheet.absoluteFill}
                    onPress={() => setMajorPickerOpen(false)}
                  />
                  <View style={styles.modalCard}>
                    <View style={styles.modalHeader}>
                      <Text style={styles.modalTitle}>Chọn ngành học</Text>
                      <Pressable
                        style={styles.modalCloseButton}
                        onPress={() => setMajorPickerOpen(false)}
                      >
                        <Ionicons name="close" size={22} color={colors.mutedForeground} />
                      </Pressable>
                    </View>
                    <ScrollView showsVerticalScrollIndicator={false}>
                      {MAJOR_OPTIONS.map((opt) => {
                        const active = selectedMajor?.code === opt.code;
                        return (
                          <Pressable
                            key={opt.code}
                            style={[styles.optionRow, active && styles.optionRowActive]}
                            onPress={() => selectMajor(opt)}
                          >
                            <View style={styles.optionTextGroup}>
                              <Text style={styles.optionCode}>{opt.code}</Text>
                              <Text style={styles.optionName}>{opt.name}</Text>
                            </View>
                            {active && (
                              <Ionicons name="checkmark" size={20} color={colors.primary} />
                            )}
                          </Pressable>
                        );
                      })}
                    </ScrollView>
                  </View>
                </View>
              </Modal>
            </View>
          </View>

          {/* Save button */}
          <Pressable
            style={[styles.saveButton, loading && styles.saveDisabled]}
            onPress={handleSave}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color={colors.primaryForeground} />
            ) : (
              <>
                <Ionicons name="checkmark" size={20} color={colors.primaryForeground} />
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

const createStyles = (colors: AppColors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerBack: {
    padding: 8,
  },
  headerTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: colors.foreground,
    textAlign: 'center',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  section: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.mutedForeground,
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
    borderBottomColor: colors.border,
  },
  readOnlyLabel: {
    fontSize: 14,
    color: colors.mutedForeground,
  },
  readOnlyValue: {
    fontSize: 14,
    color: colors.foreground,
    fontWeight: '500',
  },
  field: {
    marginBottom: 16,
  },
  label: {
    color: colors.foreground,
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.input,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingVertical: 11,
    color: colors.foreground,
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
    borderColor: colors.border,
    backgroundColor: colors.secondary,
  },
  chipActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  chipText: {
    color: colors.mutedForeground,
    fontSize: 13,
    fontWeight: '500',
  },
  chipTextActive: {
    color: colors.primary,
  },
  selectorButton: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    backgroundColor: colors.input,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  selectorTextGroup: {
    flex: 1,
    gap: 3,
  },
  selectorText: {
    color: colors.foreground,
    fontSize: 15,
    lineHeight: 20,
  },
  selectorPlaceholder: {
    color: colors.mutedForeground,
  },
  selectorMeta: {
    color: colors.mutedForeground,
    fontSize: 12,
  },
  modalBackdrop: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 18,
    backgroundColor: colors.overlay,
  },
  modalCard: {
    maxHeight: '76%',
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 14,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  modalTitle: {
    color: colors.foreground,
    fontSize: 17,
    fontWeight: '700',
  },
  modalCloseButton: {
    padding: 6,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 11,
  },
  optionRowActive: {
    backgroundColor: colors.primarySoft,
  },
  optionTextGroup: {
    flex: 1,
    gap: 2,
  },
  optionCode: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  optionName: {
    color: colors.foreground,
    fontSize: 14,
    lineHeight: 19,
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: 12,
  },
  saveDisabled: {
    opacity: 0.7,
  },
  saveText: {
    color: colors.primaryForeground,
    fontSize: 16,
    fontWeight: '600',
  },
});

export default EditProfileScreen;
