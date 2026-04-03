import { useEffect, useRef, useState, useCallback } from 'react';
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
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const channelColorMap = new Map<number, number>();
  channels.forEach((ch, i) => channelColorMap.set(ch.id, i % CHANNEL_COLORS.length));

  const fetchMessages = useCallback((reset = false) => {
    const newOffset = reset ? 0 : offset;
    const params: Record<string, string | number | boolean> = { limit: 50, offset: newOffset };
    if (selectedChannel !== null) params.channel_id = selectedChannel;
    getTelegramMessages(params).then(data => {
      if (reset) {
        setMessages(data);
        setOffset(50);
      } else {
        setMessages(prev => [...prev, ...data]);
        setOffset(newOffset + 50);
      }
      setHasMore(data.length === 50);
    }).catch(console.error);
  }, [offset, selectedChannel]);

  useEffect(() => {
    getTelegramChannels().then(setChannels).catch(console.error);
  }, []);

  useEffect(() => {
    fetchMessages(true);
  }, [selectedChannel]);

  useEffect(() => {
    return subscribe('new_telegram_message', () => {
      // Debounce: wait 1.5s after last event (backfill sends many at once)
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => fetchMessages(true), 1500);
    });
  }, [subscribe, selectedChannel]);

  // Auto-refresh every 60 seconds as fallback (catches gaps in WebSocket)
  useEffect(() => {
    const timer = setInterval(() => fetchMessages(true), 60_000);
    return () => clearInterval(timer);
  }, [selectedChannel]);

  const mediaUrl = (filename: string) => `/api/telegram/media/${filename}`;

  const handleDownload = (filename: string) => {
    const a = document.createElement('a');
    a.href = mediaUrl(filename);
    a.download = filename;
    a.click();
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-2">Telegram Feed</h2>
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
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {messages.length === 0 && (
          <div className="text-center py-8 space-y-2">
            <p className="text-gray-500 text-sm">No Telegram messages yet.</p>
            <p className="text-gray-600 text-xs">To enable Telegram monitoring:</p>
            <div className="text-left bg-gray-800/50 rounded-lg p-3 text-xs text-gray-400 space-y-1 max-w-xs mx-auto">
              <p>1. Set <code className="text-blue-400">TELEGRAM_API_ID</code> in <code className="text-blue-400">backend/.env</code></p>
              <p>2. Set <code className="text-blue-400">TELEGRAM_API_HASH</code> in <code className="text-blue-400">backend/.env</code></p>
              <p>3. Add channels via <a href="/admin" className="text-blue-400 underline">Admin panel</a></p>
            </div>
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

              {/* Message text */}
              {msg.text && (
                <p className="text-gray-300 whitespace-pre-wrap break-words text-xs leading-relaxed">{msg.text}</p>
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
