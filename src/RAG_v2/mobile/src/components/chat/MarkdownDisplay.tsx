/**
 * Markdown display — wraps react-native-markdown-display with app theme.
 */

import React, { useMemo } from 'react';
import Markdown from 'react-native-markdown-display';
import { StyleSheet } from 'react-native';
import { useAppTheme, type AppColors } from '../../theme/theme';

interface Props {
  content: string;
}

// The LLM sometimes emits broken links (empty/relative/`#`) when it has no real
// URL. Returning false from onLinkPress for those blocks the navigation so a tap
// does nothing instead of opening a garbage destination.
const isSafeExternalUrl = (url: string): boolean =>
  /^(https?:|mailto:)/i.test(url.trim());

const MarkdownDisplay = ({ content }: Props) => {
  const { colors } = useAppTheme();
  const markdownStyles = useMemo(() => createMarkdownStyles(colors), [colors]);

  return (
    <Markdown style={markdownStyles} onLinkPress={isSafeExternalUrl}>
      {content}
    </Markdown>
  );
};

const createMarkdownStyles = (colors: AppColors) => StyleSheet.create({
  body: {
    color: colors.foreground,
    fontSize: 15,
    lineHeight: 22,
  },
  heading1: {
    color: colors.foreground,
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 8,
    marginTop: 16,
  },
  heading2: {
    color: colors.foreground,
    fontSize: 19,
    fontWeight: '700',
    marginBottom: 6,
    marginTop: 14,
  },
  heading3: {
    color: colors.foreground,
    fontSize: 17,
    fontWeight: '600',
    marginBottom: 4,
    marginTop: 12,
  },
  paragraph: {
    marginBottom: 8,
    marginTop: 0,
  },
  strong: {
    fontWeight: '700',
    color: colors.foreground,
  },
  em: {
    fontStyle: 'italic',
  },
  link: {
    color: colors.primary,
    textDecorationLine: 'underline',
  },
  blockquote: {
    backgroundColor: colors.secondary,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginVertical: 8,
    borderRadius: 4,
  },
  code_inline: {
    backgroundColor: colors.secondary,
    color: colors.primary,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontFamily: 'monospace',
    fontSize: 13,
  },
  code_block: {
    backgroundColor: colors.secondary,
    color: colors.primary,
    padding: 12,
    borderRadius: 8,
    fontFamily: 'monospace',
    fontSize: 13,
    marginVertical: 8,
    overflow: 'hidden',
  },
  fence: {
    backgroundColor: colors.secondary,
    color: colors.primary,
    padding: 12,
    borderRadius: 8,
    fontFamily: 'monospace',
    fontSize: 13,
    marginVertical: 8,
  },
  list_item: {
    marginBottom: 4,
  },
  bullet_list: {
    marginBottom: 8,
  },
  ordered_list: {
    marginBottom: 8,
  },
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    marginVertical: 8,
  },
  thead: {
    backgroundColor: colors.secondary,
  },
  th: {
    padding: 8,
    fontWeight: '600',
    color: colors.foreground,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  td: {
    padding: 8,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  tr: {
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  hr: {
    backgroundColor: colors.border,
    height: 1,
    marginVertical: 16,
  },
});

export default React.memo(MarkdownDisplay);
