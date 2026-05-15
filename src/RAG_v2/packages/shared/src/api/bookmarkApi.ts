import type { AxiosInstance } from 'axios';
import type {
  Bookmark,
  BookmarkCreateRequest,
  BookmarkFolder,
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
  folder?: string,
): Promise<Bookmark[]> => {
  const response = await client.get<{ bookmarks: Bookmark[] }>(
    API_PATHS.BOOKMARKS,
    { params: folder ? { folder } : undefined },
  );
  return response.data.bookmarks;
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
