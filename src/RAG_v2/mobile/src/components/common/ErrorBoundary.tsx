/**
 * Error boundary - catches React render crashes and shows a themed fallback.
 */

import React, { Component, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} onRetry={this.handleRetry} />;
    }

    return this.props.children;
  }
}

const ErrorFallback = ({
  error,
  onRetry,
}: {
  error: Error | null;
  onRetry: () => void;
}) => {
  const { colors } = useAppTheme();
  const styles = createStyles(colors);

  return (
    <View style={styles.container}>
      <View style={styles.iconCircle}>
        <Ionicons name="alert-circle-outline" size={34} color={colors.destructive} />
      </View>
      <Text style={styles.title}>Đã xảy ra lỗi</Text>
      <Text style={styles.message}>{error?.message ?? 'Lỗi không xác định'}</Text>
      <Pressable style={styles.retryButton} onPress={onRetry}>
        <Text style={styles.retryText}>Thử lại</Text>
      </Pressable>
    </View>
  );
};

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    container: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: colors.background,
      padding: 32,
    },
    iconCircle: {
      width: 72,
      height: 72,
      borderRadius: 36,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.destructiveSoft,
      marginBottom: 16,
    },
    title: {
      fontSize: 20,
      fontWeight: '700',
      color: colors.foreground,
      marginBottom: 8,
    },
    message: {
      fontSize: 13,
      color: colors.mutedForeground,
      textAlign: 'center',
      marginBottom: 24,
      lineHeight: 20,
    },
    retryButton: {
      backgroundColor: colors.primary,
      paddingVertical: 12,
      paddingHorizontal: 32,
      borderRadius: 10,
    },
    retryText: {
      color: colors.primaryForeground,
      fontSize: 15,
      fontWeight: '600',
    },
  });

export default ErrorBoundary;
