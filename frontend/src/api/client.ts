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
