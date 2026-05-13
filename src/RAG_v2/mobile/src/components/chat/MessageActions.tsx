/**
 * Message actions bar — feedback, sources, and copy actions for assistant messages.
 */

import React, { useState } from 'react';
import { View, Pressable, Text, StyleSheet, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { RetrievedDocument } from '@rag/shared';

interface Props {
  content: string;
  sources?: RetrievedDocument[];
  onShowSources?: (sources: RetrievedDocument[]) => void;
}

const MessageActions = ({ content, sources, onShowSources }: Props) => {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await Share.share({ message: content });
    } catch {
      // Ignore share cancellation
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = (type: 'up' | 'down') => {
    setFeedback((prev) => (prev === type ? null : type));
  };

  const handleSources = () => {
    if (sources && sources.length > 0 && onShowSources) {
      onShowSources(sources);
    }
  };

  return (
    <View style={styles.container}>
      {/* Sources button */}
      {sources && sources.length > 0 && (
        <Pressable
          style={({ pressed }) => [
            styles.sourcesButton,
            pressed && styles.buttonPressed,
          ]}
          onPress={handleSources}
        >
          <Ionicons name="document-text-outline" size={13} color="#6366f1" />
          <Text style={styles.sourcesText}>
            {sources.length} nguồn
          </Text>
        </Pressable>
      )}

      {/* Divider */}
      {sources && sources.length > 0 && <View style={styles.divider} />}

      {/* Feedback */}
      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          feedback === 'up' && styles.actionActive,
          pressed && styles.buttonPressed,
        ]}
        onPress={() => handleFeedback('up')}
      >
        <Ionicons
          name={feedback === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
          size={14}
          color={feedback === 'up' ? '#22c55e' : '#64748b'}
        />
      </Pressable>

      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          feedback === 'down' && styles.actionActive,
          pressed && styles.buttonPressed,
        ]}
        onPress={() => handleFeedback('down')}
      >
        <Ionicons
          name={feedback === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
          size={14}
          color={feedback === 'down' ? '#ef4444' : '#64748b'}
        />
      </Pressable>

      {/* Copy */}
      <Pressable
        style={({ pressed }) => [
          styles.actionButton,
          pressed && styles.buttonPressed,
        ]}
        onPress={handleCopy}
      >
        <Ionicons
          name={copied ? 'checkmark' : 'copy-outline'}
          size={14}
          color={copied ? '#22c55e' : '#64748b'}
        />
      </Pressable>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 2,
  },
  sourcesButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(99, 102, 241, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  sourcesText: {
    color: '#6366f1',
    fontSize: 11,
    fontWeight: '600',
  },
  divider: {
    width: 1,
    height: 16,
    backgroundColor: '#334155',
    marginHorizontal: 4,
  },
  actionButton: {
    padding: 6,
    borderRadius: 6,
  },
  actionActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  buttonPressed: {
    opacity: 0.6,
  },
});

export default MessageActions;
