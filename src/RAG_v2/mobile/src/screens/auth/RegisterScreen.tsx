/**
 * Register screen — full registration form with student profile fields.
 */

import React, { useMemo, useState } from 'react';
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
import { Ionicons } from '@expo/vector-icons';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
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

const registerSchema = z.object({
  username: z.string().min(3, 'Tên đăng nhập tối thiểu 3 ký tự'),
  password: z.string().min(8, 'Mật khẩu tối thiểu 8 ký tự'),
  confirmPassword: z.string().min(1, 'Vui lòng xác nhận mật khẩu'),
  full_name: z.string().min(1, 'Họ tên là bắt buộc'),
  student_id: z.string().min(1, 'MSSV là bắt buộc'),
  cohort: z.string().min(1, 'Vui lòng chọn khóa'),
  major_code: z.string().min(1, 'Vui lòng chọn ngành'),
}).refine((d) => d.password === d.confirmPassword, {
  message: 'Mật khẩu xác nhận không khớp',
  path: ['confirmPassword'],
});

type RegisterForm = z.infer<typeof registerSchema>;

const RegisterScreen = ({ navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [showPassword, setShowPassword] = useState(false);
  const [majorPickerOpen, setMajorPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | undefined>();

  const { control, handleSubmit, watch, setValue, formState: { errors } } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: '', password: '', confirmPassword: '',
      full_name: '', student_id: '', cohort: '', major_code: '',
    },
  });

  const selectedMajorCode = watch('major_code');
  const selectedCohort = watch('cohort');
  const selectedMajor = MAJOR_OPTIONS.find((o) => o.code === selectedMajorCode);

  const selectMajor = (option: MajorOption) => {
    setValue('major_code', option.code, { shouldValidate: true });
    setMajorPickerOpen(false);
  };

  const onSubmit = async (data: RegisterForm) => {
    const majorOption = MAJOR_OPTIONS.find((o) => o.code === data.major_code);
    if (!majorOption) return;
    setLoading(true);
    setApiError(undefined);
    let registrationSucceeded = false;

    try {
      await registerUser(apiClient, {
        username: data.username.trim(),
        password: data.password,
        full_name: data.full_name.trim(),
        student_id: data.student_id.trim(),
        cohort: data.cohort,
        major: majorOption.name,
        major_code: majorOption.code,
      });
      registrationSucceeded = true;

      // Auto-login after registration
      const loginResult = await loginUser(apiClient, {
        username: data.username.trim(),
        password: data.password,
        client_type: 'mobile',
      });

      await setToken(loginResult.access_token, loginResult.refresh_token ?? undefined);
      await setUserProfile(loginResult.user);
      setAuth(loginResult.access_token, loginResult.user, loginResult.refresh_token ?? null);
    } catch (err: unknown) {
      if (registrationSucceeded) {
        Alert.alert(
          'Đăng ký thành công',
          'Tài khoản đã được tạo. Vui lòng đăng nhập.',
          [{ text: 'Đăng nhập', onPress: () => navigation.goBack() }],
        );
        return;
      }
      let message = 'Đăng ký thất bại.';
      if (err && typeof err === 'object' && 'response' in err) {
        const detail = (
          err as { response?: { data?: { detail?: string } } }
        ).response?.data?.detail;
        if (typeof detail === 'string') message = detail;
      }
      setApiError(message);
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
          {apiError && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={16} color={colors.destructive} />
              <Text style={styles.errorText}>{apiError}</Text>
            </View>
          )}

          {/* Username */}
          <View style={styles.field}>
            <Text style={styles.label}>Tên đăng nhập *</Text>
            <Controller
              control={control}
              name="username"
              render={({ field: { onChange, value } }) => (
                <TextInput
                  style={[styles.input, errors.username && styles.inputError]}
                  value={value}
                  onChangeText={onChange}
                  placeholder="Nhập tên đăng nhập"
                  placeholderTextColor={colors.mutedForeground}
                  autoCapitalize="none"
                  autoCorrect={false}
                  accessibilityLabel="Tên đăng nhập"
                />
              )}
            />
            {errors.username && <Text style={styles.fieldError}>{errors.username.message}</Text>}
          </View>

          {/* Full Name */}
          <View style={styles.field}>
            <Text style={styles.label}>Họ và tên *</Text>
            <Controller
              control={control}
              name="full_name"
              render={({ field: { onChange, value } }) => (
                <TextInput
                  style={[styles.input, errors.full_name && styles.inputError]}
                  value={value}
                  onChangeText={onChange}
                  placeholder="Nguyễn Văn A"
                  placeholderTextColor={colors.mutedForeground}
                  accessibilityLabel="Họ và tên"
                />
              )}
            />
            {errors.full_name && <Text style={styles.fieldError}>{errors.full_name.message}</Text>}
          </View>

          {/* Student ID */}
          <View style={styles.field}>
            <Text style={styles.label}>MSSV *</Text>
            <Controller
              control={control}
              name="student_id"
              render={({ field: { onChange, value } }) => (
                <TextInput
                  style={[styles.input, errors.student_id && styles.inputError]}
                  value={value}
                  onChangeText={onChange}
                  placeholder="20210001"
                  placeholderTextColor={colors.mutedForeground}
                  keyboardType="numeric"
                  accessibilityLabel="Mã số sinh viên"
                />
              )}
            />
            {errors.student_id && <Text style={styles.fieldError}>{errors.student_id.message}</Text>}
          </View>

          {/* Password */}
          <View style={styles.field}>
            <Text style={styles.label}>Mật khẩu *</Text>
            <View style={styles.passwordWrapper}>
              <Controller
                control={control}
                name="password"
                render={({ field: { onChange, value } }) => (
                  <TextInput
                    style={[styles.input, styles.passwordInput, errors.password && styles.inputError]}
                    value={value}
                    onChangeText={onChange}
                    placeholder="Tối thiểu 8 ký tự"
                    placeholderTextColor={colors.mutedForeground}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    accessibilityLabel="Mật khẩu"
                  />
                )}
              />
              <Pressable
                style={styles.eyeButton}
                onPress={() => setShowPassword((v) => !v)}
                accessibilityLabel={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                accessibilityRole="button"
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={colors.mutedForeground}
                />
              </Pressable>
            </View>
            {errors.password && <Text style={styles.fieldError}>{errors.password.message}</Text>}
          </View>

          {/* Confirm Password */}
          <View style={styles.field}>
            <Text style={styles.label}>Xác nhận mật khẩu *</Text>
            <Controller
              control={control}
              name="confirmPassword"
              render={({ field: { onChange, value } }) => (
                <TextInput
                  style={[styles.input, errors.confirmPassword && styles.inputError]}
                  value={value}
                  onChangeText={onChange}
                  placeholder="Nhập lại mật khẩu"
                  placeholderTextColor={colors.mutedForeground}
                  secureTextEntry={!showPassword}
                  autoCapitalize="none"
                  accessibilityLabel="Xác nhận mật khẩu"
                />
              )}
            />
            {errors.confirmPassword && <Text style={styles.fieldError}>{errors.confirmPassword.message}</Text>}
          </View>

          {/* Cohort Picker */}
          <View style={styles.field}>
            <Text style={styles.label}>Khoá *</Text>
            <View style={styles.chipGroup}>
              {COHORT_OPTIONS.map((cohort) => (
                <Pressable
                  key={cohort}
                  style={[styles.chip, selectedCohort === cohort && styles.chipActive]}
                  onPress={() => setValue('cohort', cohort, { shouldValidate: true })}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: selectedCohort === cohort }}
                  accessibilityLabel={`Khóa ${cohort}`}
                >
                  <Text style={[styles.chipText, selectedCohort === cohort && styles.chipTextActive]}>
                    {cohort}
                  </Text>
                </Pressable>
              ))}
            </View>
            {errors.cohort && <Text style={styles.fieldError}>{errors.cohort.message}</Text>}
          </View>

          {/* Major Picker */}
          <View style={styles.field}>
            <Text style={styles.label}>Ngành *</Text>
            <Pressable
              style={[styles.selectorButton, errors.major_code && styles.inputError]}
              onPress={() => setMajorPickerOpen(true)}
              accessibilityLabel={selectedMajor ? selectedMajor.name : 'Chọn ngành học'}
              accessibilityHint="Mở danh sách ngành"
              accessibilityRole="button"
            >
              <View style={styles.selectorTextGroup}>
                <Text style={[styles.selectorText, !selectedMajor && styles.selectorPlaceholder]}>
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
              accessibilityViewIsModal
            >
              <View style={styles.modalBackdrop}>
                <Pressable style={StyleSheet.absoluteFill} onPress={() => setMajorPickerOpen(false)} />
                <View style={styles.modalCard}>
                  <View style={styles.modalHeader}>
                    <Text style={styles.modalTitle} accessibilityRole="header">Chọn ngành học</Text>
                    <Pressable
                      style={styles.modalCloseButton}
                      onPress={() => setMajorPickerOpen(false)}
                      accessibilityLabel="Đóng"
                      accessibilityRole="button"
                    >
                      <Ionicons name="close" size={22} color={colors.mutedForeground} />
                    </Pressable>
                  </View>
                  <ScrollView showsVerticalScrollIndicator={false}>
                    {MAJOR_OPTIONS.map((opt) => {
                      const active = selectedMajorCode === opt.code;
                      return (
                        <Pressable
                          key={opt.code}
                          style={[styles.optionRow, active && styles.optionRowActive]}
                          onPress={() => selectMajor(opt)}
                          accessibilityRole="radio"
                          accessibilityState={{ selected: active }}
                          accessibilityLabel={`${opt.name} - ${opt.code}`}
                        >
                          <View style={styles.optionTextGroup}>
                            <Text style={styles.optionCode}>{opt.code}</Text>
                            <Text style={styles.optionName}>{opt.name}</Text>
                          </View>
                          {active && <Ionicons name="checkmark" size={20} color={colors.primary} />}
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                </View>
              </View>
            </Modal>
            {errors.major_code && <Text style={styles.fieldError}>{errors.major_code.message}</Text>}
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
            onPress={handleSubmit(onSubmit)}
            disabled={loading}
            accessibilityLabel="Đăng ký"
            accessibilityRole="button"
            accessibilityState={{ disabled: loading }}
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
