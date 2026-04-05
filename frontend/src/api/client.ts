import axios from 'axios';
import type { AISummary, NewsArticle, TelegramChannel, TelegramMessage } from '../types';

const api = axios.create({ baseURL: '/api' });

// News
export const getNews = (params?: Record<string, string | number>) =>
  api.get<NewsArticle[]>('/news', { params }).then(r => r.data);

// Telegram
export const getTelegramMessages = (params?: Record<string, string | number | boolean>) =>
  api.get<TelegramMessage[]>('/telegram/messages', { params }).then(r => r.data);

export const getTelegramChannels = () =>
  api.get<TelegramChannel[]>('/telegram/channels').then(r => r.data);

export const addTelegramChannel = (channel_identifier: string, display_name?: string) =>
  api.post('/telegram/channels', { channel_identifier, display_name });

export const toggleChannel = (id: number) =>
  api.patch(`/telegram/channels/${id}`);

export const deleteChannel = (id: number) =>
  api.delete(`/telegram/channels/${id}`);

// AI Summary
export const getSummary = () =>
  api.get<AISummary>('/summary').then(r => r.data);

export const generateSummary = () =>
  api.post<{ status?: string; content?: string; error?: string }>('/summary/generate').then(r => r.data);

// Config
export const getConfig = () =>
  api.get<Record<string, unknown>>('/config').then(r => r.data);

export const setConfig = (key: string, value: unknown) =>
  api.put('/config', { key, value: JSON.stringify(value) });

// Health
export const healthCheck = () =>
  api.get('/health').then(r => r.data);

// X (Twitter)
export const getXPosts = (params?: Record<string, string | number | boolean>) =>
  api.get('/x/posts', { params }).then(r => r.data);

export const getXAccounts = () =>
  api.get('/x/accounts').then(r => r.data);

export const addXAccount = (username: string, display_name?: string) =>
  api.post('/x/accounts', { username, display_name });

export const toggleXAccount = (id: number) =>
  api.patch(`/x/accounts/${id}`);

export const deleteXAccount = (id: number) =>
  api.delete(`/x/accounts/${id}`);

export const setXScraperAccount = (creds: { username: string; password: string; email: string; email_password: string }) =>
  api.post('/x/scraper-account', creds);

export const getXScraperAccount = () =>
  api.get('/x/scraper-account').then(r => r.data);
