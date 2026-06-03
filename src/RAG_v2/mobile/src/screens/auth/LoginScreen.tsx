import React, { useMemo } from 'react';
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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { AuthStackParamList } from '../../navigation/AuthStack';
import { useAuth } from '../../hooks/useAuth';
import { useAppTheme, type AppColors } from '../../theme/theme';

type Props = NativeStackScreenProps<AuthStackParamList, 'Login'>;

const loginSchema = z.object({
  username: z.string().min(1, 'Tên đăng nhập là bắt buộc.'),
  password: z.string().min(1, 'Mật khẩu là bắt buộc.'),
});
type LoginForm = z.infer<typeof loginSchema>;

const LoginScreen = ({ navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { login } = useAuth();
  const [showPassword, setShowPassword] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [apiError, setApiError] = React.useState<string | undefined>();

  const { control, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '' },
  });

  const onSubmit = async (data: LoginForm) => {
    setLoading(true);
    setApiError(undefined);
    try {
      await login({ username: data.username, password: data.password });
    } catch (err: unknown) {
      let message = 'Đăng nhập thất bại.';
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
      >
        <View style={styles.card}>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.iconCircle}>
              <Ionicons name="chatbubbles" size={24} color={colors.primaryForeground} />
            </View>
            <Text style={styles.brand}>HUST Assistant</Text>
            <Text style={styles.title}>Chào mừng trở lại</Text>
            <Text style={styles.subtitle}>
              Đăng nhập vào tài khoản của bạn
            </Text>
          </View>

          {/* Error */}
          {apiError && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{apiError}</Text>
            </View>
          )}

          {/* Username */}
          <View style={styles.field}>
            <Text style={styles.label}>Tên đăng nhập</Text>
            <Controller
              control={control}
              name="username"
              render={({ field: { onChange, value } }) => (
                <TextInput
                  style={[styles.input, errors.username ? styles.inputError : null]}
                  value={value}
                  onChangeText={(v) => { onChange(v); setApiError(undefined); }}
                  placeholder="Nhập tên đăng nhập"
                  placeholderTextColor={colors.mutedForeground}
                  autoCapitalize="none"
                  autoCorrect={false}
                  accessibilityLabel="Tên đăng nhập"
                />
              )}
            />
            {errors.username && (
              <Text style={styles.fieldError}>{errors.username.message}</Text>
            )}
          </View>

          {/* Password */}
          <View style={styles.field}>
            <Text style={styles.label}>Mật khẩu</Text>
            <View style={styles.passwordWrapper}>
              <Controller
                control={control}
                name="password"
                render={({ field: { onChange, value } }) => (
                  <TextInput
                    style={[
                      styles.input,
                      styles.passwordInput,
                      errors.password ? styles.inputError : null,
                    ]}
                    value={value}
                    onChangeText={(v) => { onChange(v); setApiError(undefined); }}
                    placeholder="••••••••"
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
            {errors.password && (
              <Text style={styles.fieldError}>{errors.password.message}</Text>
            )}
          </View>

          {/* Submit */}
          <Pressable
            style={[styles.submitButton, loading && styles.submitDisabled]}
            onPress={handleSubmit(onSubmit)}
            disabled={loading}
            accessibilityLabel="Đăng nhập"
            accessibilityRole="button"
            accessibilityState={{ disabled: loading }}
          >
            {loading ? (
              <ActivityIndicator size="small" color={colors.primaryForeground} />
            ) : (
              <Text style={styles.submitText}>Đăng nhập</Text>
            )}
          </Pressable>

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              Chưa có tài khoản?{' '}
            </Text>
            <Pressable onPress={() => navigation.navigate('Register')}>
              <Text style={styles.footerLink}>Đăng ký</Text>
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
    padding: 24,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 20,
    padding: 28,
    borderWidth: 1,
    borderColor: colors.border,
  },
  header: {
    alignItems: 'center',
    marginBottom: 28,
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
  brand: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 2,
    color: colors.mutedForeground,
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.foreground,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: colors.mutedForeground,
  },
  oauthButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 13,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.secondary,
    marginBottom: 8,
  },
  microsoftGrid: {
    width: 18,
    height: 18,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 1,
  },
  msBox: {
    width: 8,
    height: 8,
  },
  oauthText: {
    color: colors.foreground,
    fontSize: 14,
    fontWeight: '500',
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginVertical: 20,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    color: colors.mutedForeground,
    fontSize: 12,
  },
  errorBox: {
    backgroundColor: colors.destructiveSoft,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  errorText: {
    color: colors.destructive,
    fontSize: 13,
  },
  field: {
    marginBottom: 16,
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
    paddingVertical: 12,
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
  submitButton: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 8,
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
    marginTop: 20,
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

export default LoginScreen;
