/**
 * Register screen — full registration form with student profile fields.
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
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { AuthStackParamList } from '../../navigation/AuthStack';
import {
  registerUser,
  loginUser,
  COHORT_OPTIONS,
  MAJOR_OPTIONS,
  type MajorOption,
} from '@rag/shared';
import { apiClient } from '../../services/api';
import { setToken, setUserProfile } from '../../services/secureStorage';
import { useAuthStore } from '../../stores/authStore';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Props = NativeStackScreenProps<AuthStackParamList, 'Register'>;

interface FormData {
  username: string;
  password: string;
  confirmPassword: string;
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
}

interface FormErrors {
  username?: string;
  password?: string;
  confirmPassword?: string;
  full_name?: string;
  student_id?: string;
  cohort?: string;
  major?: string;
  api?: string;
}

const RegisterScreen = ({ navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [form, setForm] = useState<FormData>({
    username: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    student_id: '',
    cohort: '',
    major: '',
    major_code: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [majorPickerOpen, setMajorPickerOpen] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const selectedMajor = MAJOR_OPTIONS.find((option) => option.code === form.major_code);

  const updateField = (key: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    // Clear field error on change
    if (errors[key as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  };

  const selectMajor = (option: MajorOption) => {
    setForm((prev) => ({ ...prev, major: option.name, major_code: option.code }));
    setMajorPickerOpen(false);
    if (errors.major) setErrors((prev) => ({ ...prev, major: undefined }));
  };

  const validate = (): boolean => {
    const next: FormErrors = {};

    if (!form.username.trim() || form.username.trim().length < 3)
      next.username = 'Tên đăng nhập tối thiểu 3 ký tự';
    if (!form.password || form.password.length < 8)
      next.password = 'Mật khẩu tối thiểu 8 ký tự';
    if (form.password !== form.confirmPassword)
      next.confirmPassword = 'Mật khẩu xác nhận không khớp';
    if (!form.full_name.trim())
      next.full_name = 'Họ tên là bắt buộc';
    if (!form.student_id.trim())
      next.student_id = 'MSSV là bắt buộc';
    if (!form.cohort)
      next.cohort = 'Vui lòng chọn khóa';
    if (!selectedMajor || form.major !== selectedMajor.name)
      next.major = 'Vui lòng chọn ngành';

    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    const majorOption = selectedMajor;
    if (!majorOption) return;
    setLoading(true);
    setErrors({});

    try {
      // Register the user
      await registerUser(apiClient, {
        username: form.username.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        student_id: form.student_id.trim(),
        cohort: form.cohort,
        major: majorOption.name,
        major_code: majorOption.code,
      });

      // Auto-login after registration
      const loginResult = await loginUser(apiClient, {
        username: form.username.trim(),
        password: form.password,
        client_type: 'mobile',
      });

      // Persist auth
      await setToken(loginResult.access_token, loginResult.refresh_token ?? undefined);
      await setUserProfile(loginResult.user);
      setAuth(loginResult.access_token, loginResult.user, loginResult.refresh_token ?? null);
      // Auth state change triggers RootNavigator to show MainTab
    } catch (err: unknown) {
      let message = 'Đăng ký thất bại.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (
          err as { response?: { data?: { detail?: string } } }
        ).response?.data?.detail;
        if (typeof detail === 'string') message = detail;
      }
      setErrors({ api: message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.card}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.iconCircle}>
              <Ionicons name="person-add" size={22} color={colors.primaryForeground} />
            </View>
            <Text style={styles.title}>Tạo tài khoản</Text>
            <Text style={styles.subtitle}>
              Đăng ký để sử dụng HUST Assistant
            </Text>
          </View>

          {/* API Error */}
          {errors.api && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={16} color={colors.destructive} />
              <Text style={styles.errorText}>{errors.api}</Text>
            </View>
          )}

          {/* Username */}
          <View style={styles.field}>
            <Text style={styles.label}>Tên đăng nhập *</Text>
            <TextInput
              style={[styles.input, errors.username && styles.inputError]}
              value={form.username}
              onChangeText={(v) => updateField('username', v)}
              placeholder="Nhập tên đăng nhập"
              placeholderTextColor={colors.mutedForeground}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {errors.username && (
              <Text style={styles.fieldError}>{errors.username}</Text>
            )}
          </View>

          {/* Full Name */}
          <View style={styles.field}>
            <Text style={styles.label}>Họ và tên *</Text>
            <TextInput
              style={[styles.input, errors.full_name && styles.inputError]}
              value={form.full_name}
              onChangeText={(v) => updateField('full_name', v)}
              placeholder="Nguyễn Văn A"
              placeholderTextColor={colors.mutedForeground}
            />
            {errors.full_name && (
              <Text style={styles.fieldError}>{errors.full_name}</Text>
            )}
          </View>

          {/* Student ID */}
          <View style={styles.field}>
            <Text style={styles.label}>MSSV *</Text>
            <TextInput
              style={[styles.input, errors.student_id && styles.inputError]}
              value={form.student_id}
              onChangeText={(v) => updateField('student_id', v)}
              placeholder="20210001"
              placeholderTextColor={colors.mutedForeground}
              keyboardType="numeric"
            />
            {errors.student_id && (
              <Text style={styles.fieldError}>{errors.student_id}</Text>
            )}
          </View>

          {/* Password */}
          <View style={styles.field}>
            <Text style={styles.label}>Mật khẩu *</Text>
            <View style={styles.passwordWrapper}>
              <TextInput
                style={[
                  styles.input,
                  styles.passwordInput,
                  errors.password && styles.inputError,
                ]}
                value={form.password}
                onChangeText={(v) => updateField('password', v)}
                placeholder="Tối thiểu 8 ký tự"
                placeholderTextColor={colors.mutedForeground}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
              />
              <Pressable
                style={styles.eyeButton}
                onPress={() => setShowPassword((v) => !v)}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={colors.mutedForeground}
                />
              </Pressable>
            </View>
            {errors.password && (
              <Text style={styles.fieldError}>{errors.password}</Text>
            )}
          </View>

          {/* Confirm Password */}
          <View style={styles.field}>
            <Text style={styles.label}>Xác nhận mật khẩu *</Text>
            <TextInput
              style={[
                styles.input,
                errors.confirmPassword && styles.inputError,
              ]}
              value={form.confirmPassword}
              onChangeText={(v) => updateField('confirmPassword', v)}
              placeholder="Nhập lại mật khẩu"
              placeholderTextColor={colors.mutedForeground}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
            />
            {errors.confirmPassword && (
              <Text style={styles.fieldError}>{errors.confirmPassword}</Text>
            )}
          </View>

          {/* Cohort Picker */}
          <View style={styles.field}>
            <Text style={styles.label}>Khoá *</Text>
            <View style={styles.chipGroup}>
              {COHORT_OPTIONS.map((cohort) => (
                <Pressable
                  key={cohort}
                  style={[
                    styles.chip,
                    form.cohort === cohort && styles.chipActive,
                  ]}
                  onPress={() => updateField('cohort', cohort)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      form.cohort === cohort && styles.chipTextActive,
                    ]}
                  >
                    {cohort}
                  </Text>
                </Pressable>
              ))}
            </View>
            {errors.cohort && (
              <Text style={styles.fieldError}>{errors.cohort}</Text>
            )}
          </View>

          {/* Major Picker */}
          <View style={styles.field}>
            <Text style={styles.label}>Ngành *</Text>
            <Pressable
              style={[styles.selectorButton, errors.major && styles.inputError]}
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
            {errors.major && (
              <Text style={styles.fieldError}>{errors.major}</Text>
            )}
          </View>

          {/* Info banner */}
          <View style={styles.infoBanner}>
            <Ionicons name="information-circle" size={16} color={colors.primary} />
            <Text style={styles.infoText}>
              Thông tin khoá và ngành giúp hệ thống trả lời chính xác hơn cho bạn
            </Text>
          </View>

          {/* Submit */}
          <Pressable
            style={[styles.submitButton, loading && styles.submitDisabled]}
            onPress={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator size="small" color={colors.primaryForeground} />
            ) : (
              <Text style={styles.submitText}>Đăng ký</Text>
            )}
          </Pressable>

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Đã có tài khoản? </Text>
            <Pressable onPress={() => navigation.goBack()}>
              <Text style={styles.footerLink}>Đăng nhập</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const createStyles = (colors: AppColors) => StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.foreground,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: colors.mutedForeground,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.destructiveSoft,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  errorText: {
    color: colors.destructive,
    fontSize: 13,
    flex: 1,
  },
  field: {
    marginBottom: 14,
  },
  label: {
    color: colors.foreground,
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 6,
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
  inputError: {
    borderColor: colors.destructive,
  },
  passwordWrapper: {
    position: 'relative',
  },
  passwordInput: {
    paddingRight: 44,
  },
  eyeButton: {
    position: 'absolute',
    right: 12,
    top: 0,
    bottom: 0,
    justifyContent: 'center',
  },
  fieldError: {
    color: colors.destructive,
    fontSize: 12,
    marginTop: 4,
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
    backgroundColor: 'rgba(0, 0, 0, 0.36)',
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
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: colors.primarySoft,
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
    marginTop: 4,
  },
  infoText: {
    color: colors.mutedForeground,
    fontSize: 12,
    lineHeight: 18,
    flex: 1,
  },
  submitButton: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 4,
  },
  submitDisabled: {
    opacity: 0.7,
  },
  submitText: {
    color: colors.primaryForeground,
    fontSize: 16,
    fontWeight: '600',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 16,
  },
  footerText: {
    color: colors.mutedForeground,
    fontSize: 14,
  },
  footerLink: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '600',
  },
});

export default RegisterScreen;
