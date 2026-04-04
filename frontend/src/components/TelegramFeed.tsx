import React, { useEffect, useRef, useState, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { getTelegramMessages, getTelegramChannels } from '../api/client';
import type { TelegramMessage, TelegramChannel } from '../types';

interface Props {
  subscribe: (type: string, handler: (data: Record<string, unknown>) => void) => () => void;
}

// Assign consistent colors to channels
const CHANNEL_COLORS = [
  'border-l-blue-500', 'border-l-green-500', 'border-l-purple-500',
  'border-l-orange-500', 'border-l-pink-500', 'border-l-cyan-500',
  'border-l-yellow-500', 'border-l-red-500',
];

const CHANNEL_BG = [
  'bg-blue-900/20', 'bg-green-900/20', 'bg-purple-900/20',
  'bg-orange-900/20', 'bg-pink-900/20', 'bg-cyan-900/20',
  'bg-yellow-900/20', 'bg-red-900/20',
];

export default function TelegramFeed({ subscribe }: Props) {
  const [messages, setMessages] = useState<TelegramMessage[]>([]);
  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [expandedMedia, setExpandedMedia] = useState<string | null>(null);

  // Search/filter state
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [hasMediaOnly, setHasMediaOnly] = useState(false);
  const [hourFrom, setHourFrom] = useState('');
  const [hourTo, setHourTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const channelColorMap = new Map<number, number>();
  channels.forEach((ch, i) => channelColorMap.set(ch.id, i % CHANNEL_COLORS.length));

  // Debounce search text
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => setDebouncedSearch(searchText), 400);
    return () => { if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current); };
  }, [searchText]);

  const buildParams = useCallback((resetOffset = true) => {
    const params: Record<string, string | number | boolean> = {
      limit: 50,
      offset: resetOffset ? 0 : offset,
    };
    if (selectedChannel !== null) params.channel_id = selectedChannel;
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
    if (hasMediaOnly) params.has_media = true;
    if (hourFrom !== '') params.hour_from = parseInt(hourFrom);
    if (hourTo !== '') params.hour_to = parseInt(hourTo);
    return params;
  }, [offset, selectedChannel, debouncedSearch, hasMediaOnly, hourFrom, hourTo]);

  const fetchMessages = useCallback((reset = false) => {
    const params = buildParams(reset);
    getTelegramMessages(params).then(data => {
      if (reset) {
        setMessages(data);
        setOffset(50);
      } else {
        setMessages(prev => [...prev, ...data]);
        setOffset((params.offset as number) + 50);
      }
      setHasMore(data.length === 50);
    }).catch(console.error);
  }, [buildParams]);

  useEffect(() => {
    getTelegramChannels().then(setChannels).catch(console.error);
  }, []);

  // Reset + fetch when any filter changes
  useEffect(() => {
    fetchMessages(true);
  }, [selectedChannel, debouncedSearch, hasMediaOnly, hourFrom, hourTo]);

  useEffect(() => {
    return subscribe('new_telegram_message', () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchMessages(true), 1500);
    });
  }, [subscribe, selectedChannel, debouncedSearch, hasMediaOnly, hourFrom, hourTo]);

  // Auto-refresh every 60 seconds as fallback
  useEffect(() => {
    const timer = setInterval(() => fetchMessages(true), 60_000);
    return () => clearInterval(timer);
  }, [selectedChannel, debouncedSearch, hasMediaOnly, hourFrom, hourTo]);

  const mediaUrl = (filename: string) => `/api/telegram/media/${filename}`;

  const handleDownload = (filename: string) => {
    const a = document.createElement('a');
    a.href = mediaUrl(filename);
    a.download = filename;
    a.click();
  };

  const hasActiveFilters = debouncedSearch || hasMediaOnly || hourFrom !== '' || hourTo !== '';

  const clearFilters = () => {
    setSearchText('');
    setDebouncedSearch('');
    setHasMediaOnly(false);
    setHourFrom('');
    setHourTo('');
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Telegram Feed</h2>
          <button
            onClick={() => setShowFilters(f => !f)}
            className={`text-[10px] px-2 py-1 rounded transition-colors flex items-center gap-1 ${
              showFilters || hasActiveFilters
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
            </svg>
            {hasActiveFilters ? 'Filters active' : 'Filters'}
          </button>
        </div>

        {/* Search bar — always visible */}
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            placeholder="Search messages..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-8 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          {searchText && (
            <button
              onClick={() => setSearchText('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Expandable filter panel */}
        {showFilters && (
          <div className="bg-gray-800/60 rounded-lg p-3 space-y-3 border border-gray-700/50">
            {/* Media filter */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHasMediaOnly(v => !v)}
                className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full border transition-colors ${
                  hasMediaOnly
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Media only
              </button>
            </div>

            {/* Hour range filter */}
            <div>
              <p className="text-[10px] text-gray-500 mb-1.5 uppercase tracking-wider">Hour range (UTC)</p>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <label className="text-[10px] text-gray-400">From</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={hourFrom}
                    onChange={e => setHourFrom(e.target.value)}
                    placeholder="0"
                    className="w-14 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-blue-500 text-center"
                  />
                </div>
                <span className="text-gray-600 text-xs">–</span>
                <div className="flex items-center gap-1">
                  <label className="text-[10px] text-gray-400">To</label>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={hourTo}
                    onChange={e => setHourTo(e.target.value)}
                    placeholder="23"
                    className="w-14 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-blue-500 text-center"
                  />
                </div>
                <span className="text-[10px] text-gray-500">:00</span>
              </div>
            </div>

            {/* Clear filters */}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
              >
                Clear all filters
              </button>
            )}
          </div>
        )}

        {/* Channel filter chips */}
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setSelectedChannel(null)}
            className={`text-[10px] px-2 py-1 rounded-full transition-colors ${
              selectedChannel === null
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            All
          </button>
          {channels.filter(c => c.is_active).map(ch => (
            <button
              key={ch.id}
              onClick={() => setSelectedChannel(ch.id === selectedChannel ? null : ch.id)}
              className={`text-[10px] px-2 py-1 rounded-full transition-colors ${
                selectedChannel === ch.id
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {ch.display_name || ch.channel_identifier}
            </button>
          ))}
        </div>

        {/* Active filter summary */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {debouncedSearch && (
              <span className="text-[10px] bg-blue-900/40 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded-full flex items-center gap-1">
                "{debouncedSearch}"
                <button onClick={() => setSearchText('')} className="ml-0.5 hover:text-white">×</button>
              </span>
            )}
            {hasMediaOnly && (
              <span className="text-[10px] bg-blue-900/40 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded-full flex items-center gap-1">
                Has media
                <button onClick={() => setHasMediaOnly(false)} className="ml-0.5 hover:text-white">×</button>
              </span>
            )}
            {(hourFrom !== '' || hourTo !== '') && (
              <span className="text-[10px] bg-blue-900/40 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded-full flex items-center gap-1">
                {hourFrom || '0'}:00 – {hourTo || '23'}:00 UTC
                <button onClick={() => { setHourFrom(''); setHourTo(''); }} className="ml-0.5 hover:text-white">×</button>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="overflow-y-auto px-3 py-3 space-y-2 max-h-96 lg:max-h-none lg:flex-1">
        {messages.length === 0 && (
          <div className="text-center py-8 space-y-2">
            {hasActiveFilters ? (
              <>
                <p className="text-gray-500 text-sm">No messages match your filters.</p>
                <button onClick={clearFilters} className="text-xs text-blue-400 hover:text-blue-300">Clear filters</button>
              </>
            ) : (
              <>
                <p className="text-gray-500 text-sm">No Telegram messages yet.</p>
                <p className="text-gray-600 text-xs">To enable Telegram monitoring:</p>
                <div className="text-left bg-gray-800/50 rounded-lg p-3 text-xs text-gray-400 space-y-1 max-w-xs mx-auto">
                  <p>1. Set <code className="text-blue-400">TELEGRAM_API_ID</code> in <code className="text-blue-400">backend/.env</code></p>
                  <p>2. Set <code className="text-blue-400">TELEGRAM_API_HASH</code> in <code className="text-blue-400">backend/.env</code></p>
                  <p>3. Add channels via <a href="/admin" className="text-blue-400 underline">Admin panel</a></p>
                </div>
              </>
            )}
          </div>
        )}
        {messages.map(msg => {
          const colorIdx = channelColorMap.get(msg.channel_id) ?? 0;
          return (
            <div
              key={msg.id}
              className={`p-3 rounded-lg text-sm border-l-2 ${CHANNEL_COLORS[colorIdx]} ${
                msg.is_flagged ? 'bg-yellow-900/20 border-r border-r-yellow-800/30' : CHANNEL_BG[colorIdx]
              }`}
            >
              {/* Channel name + time + badges */}
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <span className="text-[10px] font-semibold text-gray-400">
                  {msg.channel_name}
                </span>
                {msg.is_flagged && (
                  <span className="text-[10px] bg-yellow-800/50 text-yellow-300 px-1.5 py-0.5 rounded">FLAGGED</span>
                )}
                {msg.media_type && (
                  <span className="text-[10px] bg-blue-800/50 text-blue-300 px-1.5 py-0.5 rounded">
                    {msg.media_type === 'video' ? 'VIDEO' : 'PHOTO'}
                  </span>
                )}
                <span className="text-[10px] text-gray-500 ml-auto">
                  {msg.timestamp && formatDistanceToNow(new Date(msg.timestamp), { addSuffix: true })}
                </span>
              </div>

              {/* Message text — highlight search matches */}
              {msg.text && (
                <p className="text-gray-300 whitespace-pre-wrap break-words text-xs leading-relaxed">
                  {debouncedSearch
                    ? highlightText(msg.text, debouncedSearch)
                    : msg.text}
                </p>
              )}

              {/* Inline media */}
              {msg.media_file && msg.media_type === 'photo' && (
                <div className="mt-2 relative group">
                  <img
                    src={mediaUrl(msg.media_file)}
                    alt="Telegram media"
                    className={`rounded-lg cursor-pointer transition-all ${
                      expandedMedia === msg.media_file ? 'max-h-[600px]' : 'max-h-48'
                    } object-cover`}
                    onClick={() => setExpandedMedia(expandedMedia === msg.media_file ? null : msg.media_file)}
                  />
                  <button
                    onClick={() => handleDownload(msg.media_file!)}
                    className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Download
                  </button>
                </div>
              )}

              {msg.media_file && msg.media_type === 'video' && (
                <div className="mt-2 relative group">
                  <video
                    src={mediaUrl(msg.media_file)}
                    controls
                    preload="metadata"
                    className="rounded-lg max-h-64 w-full"
                  />
                  <button
                    onClick={() => handleDownload(msg.media_file!)}
                    className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Download
                  </button>
                </div>
              )}

              {/* Keywords */}
              {msg.matched_keywords.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {msg.matched_keywords.map((kw, i) => (
                    <span key={i} className="text-[9px] bg-gray-700 text-gray-400 px-1 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {/* Load more */}
        {hasMore && messages.length > 0 && (
          <button
            onClick={() => fetchMessages(false)}
            className="w-full text-center text-xs text-gray-400 bg-gray-800/50 rounded-lg py-2 hover:bg-gray-800 transition-colors"
          >
            Load more...
          </button>
        )}
      </div>
    </div>
  );
}

/** Highlight search term in text — returns a mix of strings and <mark> spans */
function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part)
      ? <mark key={i} className="bg-yellow-500/40 text-yellow-200 rounded px-0.5">{part}</mark>
      : part
  );
}
