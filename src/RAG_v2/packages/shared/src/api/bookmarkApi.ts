import type { AxiosInstance } from 'axios';
import type {
  Bookmark,
  BookmarkCreateRequest,
  BookmarkFolder,
  BookmarkUpdateRequest,
  BookmarkFolderRenameRequest,
} from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const createBookmark = async (
  client: AxiosInstance,
  data: BookmarkCreateRequest,
): Promise<Bookmark> => {
  const response = await client.post<{ bookmark: Bookmark }>(
    API_PATHS.BOOKMARKS,
    data,
  );
  return response.data.bookmark;
};

export const listBookmarks = async (
  client: AxiosInstance,
  params?: {
    folder?: string;
    q?: string;
    session_id?: string;
    turn_id?: number;
    page?: number;
    limit?: number;
  },
): Promise<{ bookmarks: Bookmark[]; total: number; page: number; limit: number }> => {
  const response = await client.get<{
    bookmarks: Bookmark[];
    total: number;
    page: number;
    limit: number;
  }>(API_PATHS.BOOKMARKS, { params });
  return response.data;
};

export const getBookmarkByTurn = async (
  client: AxiosInstance,
  sessionId: string,
  turnId: number,
): Promise<Bookmark | null> => {
  const result = await listBookmarks(client, { session_id: sessionId, turn_id: turnId, limit: 1 });
  return result.bookmarks[0] ?? null;
};

export const updateBookmark = async (
  client: AxiosInstance,
  bookmarkId: string,
  data: BookmarkUpdateRequest,
): Promise<Bookmark> => {
  const response = await client.patch<{ bookmark: Bookmark }>(
    `${API_PATHS.BOOKMARKS}/${bookmarkId}`,
    data,
  );
  return response.data.bookmark;
};

export const deleteBookmark = async (
  client: AxiosInstance,
  bookmarkId: string,
): Promise<void> => {
  await client.delete(`${API_PATHS.BOOKMARKS}/${bookmarkId}`);
};

export const listBookmarkFolders = async (
  client: AxiosInstance,
): Promise<BookmarkFolder[]> => {
  const response = await client.get<{ folders: BookmarkFolder[] }>(
    API_PATHS.BOOKMARK_FOLDERS,
  );
  return response.data.folders;
};

export const createBookmarkFolder = async (
  client: AxiosInstance,
  name: string,
): Promise<BookmarkFolder> => {
  const response = await client.post<{ folder: BookmarkFolder }>(
    API_PATHS.BOOKMARK_FOLDERS,
    { name },
  );
  return response.data.folder;
};

export const renameBookmarkFolder = async (
  client: AxiosInstance,
  currentName: string,
  data: BookmarkFolderRenameRequest,
): Promise<BookmarkFolder> => {
  const response = await client.patch<{ folder: BookmarkFolder }>(
    `${API_PATHS.BOOKMARK_FOLDERS}/${encodeURIComponent(currentName)}`,
    data,
  );
  return response.data.folder;
};

export const deleteBookmarkFolder = async (
  client: AxiosInstance,
  name: string,
  moveTo?: string,
): Promise<{ status: string; moved_count: number }> => {
  const response = await client.delete<{ status: string; moved_count: number }>(
    `${API_PATHS.BOOKMARK_FOLDERS}/${encodeURIComponent(name)}`,
    { params: moveTo ? { move_to: moveTo } : undefined },
  );
  return response.data;
};
