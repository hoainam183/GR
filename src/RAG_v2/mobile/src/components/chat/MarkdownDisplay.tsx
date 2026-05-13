/**
 * Markdown display — wraps react-native-markdown-display with app theme.
 */

import React from 'react';
import Markdown from 'react-native-markdown-display';
import { StyleSheet } from 'react-native';

interface Props {
  content: string;
}

const MarkdownDisplay = ({ content }: Props) => (
  <Markdown style={markdownStyles}>{content}</Markdown>
);

const markdownStyles = StyleSheet.create({
  body: {
    color: '#e2e8f0',
    fontSize: 15,
    lineHeight: 22,
  },
  heading1: {
    color: '#f8fafc',
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 8,
    marginTop: 16,
  },
  heading2: {
    color: '#f8fafc',
    fontSize: 19,
    fontWeight: '700',
    marginBottom: 6,
    marginTop: 14,
  },
  heading3: {
    color: '#f8fafc',
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
    color: '#f8fafc',
  },
  em: {
    fontStyle: 'italic',
  },
  link: {
    color: '#818cf8',
    textDecorationLine: 'underline',
  },
  blockquote: {
    backgroundColor: '#1e293b',
    borderLeftWidth: 3,
    borderLeftColor: '#6366f1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginVertical: 8,
    borderRadius: 4,
  },
  code_inline: {
    backgroundColor: '#1e293b',
    color: '#a5b4fc',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontFamily: 'monospace',
    fontSize: 13,
  },
  code_block: {
    backgroundColor: '#1e293b',
    color: '#a5b4fc',
    padding: 12,
    borderRadius: 8,
    fontFamily: 'monospace',
    fontSize: 13,
    marginVertical: 8,
    overflow: 'hidden',
  },
  fence: {
    backgroundColor: '#1e293b',
    color: '#a5b4fc',
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
    borderColor: '#334155',
    borderRadius: 6,
    marginVertical: 8,
  },
  thead: {
    backgroundColor: '#1e293b',
  },
  th: {
    padding: 8,
    fontWeight: '600',
    color: '#f8fafc',
    borderBottomWidth: 1,
    borderColor: '#334155',
  },
  td: {
    padding: 8,
    borderBottomWidth: 1,
    borderColor: '#1e293b',
  },
  tr: {
    borderBottomWidth: 1,
    borderColor: '#1e293b',
  },
  hr: {
    backgroundColor: '#334155',
    height: 1,
    marginVertical: 16,
  },
});

export default MarkdownDisplay;
