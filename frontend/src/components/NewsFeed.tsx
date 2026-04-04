import { useEffect, useRef, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { getNews } from '../api/client';
import type { NewsArticle } from '../types';

const SOURCE_COLORS: Record<string, string> = {
  ynet:       'bg-red-900/60 text-red-300',
  ynet_flash: 'bg-red-600/80 text-white',
  reuters:    'bg-orange-900/60 text-orange-300',
  cnn:        'bg-red-800/60 text-red-200',
  nyt:        'bg-blue-900/60 text-blue-300',
  bbc:        'bg-yellow-900/60 text-yellow-300',
  toi:        'bg-green-900/60 text-green-300',
};

const SOURCE_LABEL: Record<string, string> = {
  ynet:       'YNET',
  ynet_flash: 'FLASH',
  reuters:    'REUTERS',
  cnn:        'CNN',
  nyt:        'NYT',
  bbc:        'BBC',
  toi:        'TOI',
};

interface Props {
  subscribe: (type: string, handler: (data: Record<string, unknown>) => void) => () => void;
}

export default function NewsFeed({ subscribe }: Props) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchNews = () => {
    getNews({ limit: 200 }).then(setArticles).catch(console.error);
  };

  // Debounced fetch — waits 2s after the last event before calling API
  const debouncedFetch = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchNews, 2000);
  };

  useEffect(() => { fetchNews(); }, []);

  useEffect(() => {
    return subscribe('new_article', () => debouncedFetch());
  }, [subscribe]);

  // Flashes: deduplicate by title prefix (first 60 chars), newest first
  const flashMap = new Map<string, NewsArticle>();
  articles
    .filter(a => a.source === 'ynet_flash')
    .forEach(a => {
      const key = a.title.slice(0, 60).toLowerCase();
      if (!flashMap.has(key)) flashMap.set(key, a);
    });
  const flashArticles = Array.from(flashMap.values()).slice(0, 40);

  // Headlines: non-flash sources, max 30, scrollable
  const headlines = articles.filter(a => a.source !== 'ynet_flash').slice(0, 30);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 shrink-0">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">War Headlines</h2>
      </div>

      {/* ── FLASH STRIP ── fixed height, independent scroll */}
      {flashArticles.length > 0 && (
        <div className="border-b border-gray-800 shrink-0" style={{ maxHeight: '200px' }}>
          <div className="px-3 pt-2 pb-1 flex items-center gap-1.5 sticky top-0 bg-gray-900 z-10">
            <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse shrink-0" />
            <span className="text-[10px] font-semibold text-red-400 uppercase tracking-wider">
              Breaking / Flash — {flashArticles.length}
            </span>
          </div>
          <div className="overflow-y-auto px-3 pb-2" style={{ maxHeight: '164px' }}>
            {flashArticles.map(a => (
              <a
                key={a.id}
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 py-1 hover:bg-red-950/30 transition-colors rounded"
              >
                <span className="w-1 h-1 bg-red-500/70 rounded-full shrink-0" />
                <span className="text-[11px] text-gray-200 leading-tight flex-1 truncate">
                  {a.title}
                </span>
                {a.published_at && (
                  <span className="text-[10px] text-gray-600 shrink-0 ml-1">
                    {formatDistanceToNow(new Date(a.published_at), { addSuffix: true })}
                  </span>
                )}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ── MAIN HEADLINES ── fixed height on mobile, fills space on desktop */}
      <div className="overflow-y-auto px-3 py-3 max-h-72 lg:max-h-none lg:flex-1">
        <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Main Headlines
        </div>
        <div className="space-y-2">
          {headlines.length === 0 && flashArticles.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">
              No war-related articles yet. Feeds will populate automatically.
            </p>
          )}
          {headlines.map(a => {
            // Strip HTML, take first ~180 chars as a 2-sentence excerpt
            const excerpt = a.description
              ? a.description.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim().slice(0, 180)
              : '';
            return (
              <a
                key={a.id}
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block p-2 rounded-lg hover:bg-gray-800 transition-colors bg-gray-800/50"
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium shrink-0 ${SOURCE_COLORS[a.source] ?? 'bg-gray-700 text-gray-300'}`}>
                    {SOURCE_LABEL[a.source] ?? a.source.toUpperCase()}
                  </span>
                  {a.published_at && (
                    <span className="text-[9px] text-gray-500 ml-auto shrink-0">
                      {formatDistanceToNow(new Date(a.published_at), { addSuffix: true })}
                    </span>
                  )}
                </div>
                <h3 className="text-xs text-gray-200 leading-snug font-medium">{a.title}</h3>
                {excerpt && (
                  <p className="text-[10px] text-gray-500 leading-snug mt-0.5 line-clamp-2">{excerpt}</p>
                )}
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}
