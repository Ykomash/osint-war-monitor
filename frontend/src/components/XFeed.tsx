import { useEffect, useRef, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { getXPosts, getXAccounts } from '../api/client';
import type { XPost, XAccount } from '../types/index';

interface Props {
  subscribe: (type: string, handler: (data: Record<string, unknown>) => void) => () => void;
}

export default function XFeed({ subscribe }: Props) {
  const [posts, setPosts] = useState<XPost[]>([]);
  const [accounts, setAccounts] = useState<XAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [mediaOnly, setMediaOnly] = useState(false);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [expandedMedia, setExpandedMedia] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPosts = () => {
    const params: Record<string, string | number | boolean> = { limit: 100 };
    if (selectedAccount) params.account_id = selectedAccount;
    if (mediaOnly) params.has_media = true;
    if (flaggedOnly) params.flagged_only = true;
    if (search.trim()) params.search = search.trim();
    getXPosts(params).then(setPosts).catch(console.error);
  };

  const debouncedFetch = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchPosts, 400);
  };

  useEffect(() => {
    getXAccounts().then(setAccounts).catch(console.error);
  }, []);

  useEffect(() => { fetchPosts(); }, [selectedAccount, mediaOnly, flaggedOnly]);
  useEffect(() => { debouncedFetch(); }, [search]);

  useEffect(() => {
    return subscribe('new_x_post', () => fetchPosts());
  }, [subscribe, selectedAccount, mediaOnly, flaggedOnly, search]);

  const activeAccounts = accounts.filter(a => a.is_active);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider flex items-center gap-2">
            <span className="text-gray-500">𝕏</span> X Feed
            <span className="text-[10px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded">{posts.length}</span>
          </h2>
        </div>

        {/* Search */}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search posts..."
          className="w-full bg-gray-800 text-gray-300 text-xs px-2.5 py-1.5 rounded border border-gray-700 focus:outline-none focus:border-gray-500 mb-2"
        />

        {/* Filters row */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setMediaOnly(!mediaOnly)}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${mediaOnly ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
          >
            Media only
          </button>
          <button
            onClick={() => setFlaggedOnly(!flaggedOnly)}
            className={`text-[10px] px-2 py-1 rounded transition-colors ${flaggedOnly ? 'bg-red-800 text-red-200' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
          >
            Flagged only
          </button>
        </div>

        {/* Account chips */}
        {activeAccounts.length > 0 && (
          <div className="flex gap-1.5 flex-wrap mt-2">
            <button
              onClick={() => setSelectedAccount(null)}
              className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${selectedAccount === null ? 'bg-gray-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
            >
              All
            </button>
            {activeAccounts.map(a => (
              <button
                key={a.id}
                onClick={() => setSelectedAccount(selectedAccount === a.id ? null : a.id)}
                className={`text-[10px] px-2 py-0.5 rounded-full transition-colors ${selectedAccount === a.id ? 'bg-sky-800 text-sky-200' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
              >
                @{a.username}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Posts list */}
      <div className="flex-1 overflow-y-auto divide-y divide-gray-800/50">
        {posts.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-gray-500 text-xs">
              {accounts.length === 0
                ? 'No X accounts added yet. Go to Admin → X Accounts.'
                : 'No posts yet. Posts will appear after the next poll (up to 15 min).'}
            </p>
          </div>
        ) : (
          posts.map(post => (
            <div
              key={post.id}
              className={`p-3 hover:bg-gray-800/40 transition-colors ${post.is_flagged ? 'border-l-2 border-red-500/60' : ''}`}
            >
              {/* Author + time */}
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-semibold text-sky-400">@{post.username}</span>
                {post.is_flagged && (
                  <span className="text-[9px] bg-red-900/60 text-red-300 px-1 rounded">flagged</span>
                )}
                <span className="text-[10px] text-gray-600 ml-auto shrink-0">
                  {formatDistanceToNow(new Date(post.timestamp), { addSuffix: true })}
                </span>
              </div>

              {/* Text */}
              <p className="text-xs text-gray-200 leading-relaxed whitespace-pre-wrap break-words mb-1.5">
                {post.text}
              </p>

              {/* Media */}
              {post.has_media && post.media_urls.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-1.5">
                  {post.media_urls.slice(0, 4).map((url, i) => (
                    url.match(/\.(mp4|mov|webm)/i) ? (
                      <video
                        key={i}
                        src={url}
                        controls
                        className="max-h-40 rounded border border-gray-700"
                        style={{ maxWidth: '100%' }}
                      />
                    ) : (
                      <img
                        key={i}
                        src={url}
                        alt=""
                        className={`rounded border border-gray-700 cursor-pointer object-cover transition-all ${expandedMedia === url ? 'max-h-96 max-w-full' : 'max-h-32'}`}
                        onClick={() => setExpandedMedia(expandedMedia === url ? null : url)}
                        onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                    )
                  ))}
                </div>
              )}

              {/* Stats + link */}
              <div className="flex items-center gap-3 mt-1">
                {post.reply_count > 0 && (
                  <span className="text-[10px] text-gray-600">💬 {post.reply_count}</span>
                )}
                {post.retweet_count > 0 && (
                  <span className="text-[10px] text-gray-600">🔁 {post.retweet_count}</span>
                )}
                {post.like_count > 0 && (
                  <span className="text-[10px] text-gray-600">♥ {post.like_count}</span>
                )}
                {post.matched_keywords.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {post.matched_keywords.map(kw => (
                      <span key={kw} className="text-[9px] bg-amber-900/40 text-amber-400 px-1 rounded">{kw}</span>
                    ))}
                  </div>
                )}
                <a
                  href={post.tweet_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] text-gray-600 hover:text-gray-400 ml-auto"
                >
                  View →
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
