import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { getSummary, generateSummary } from '../api/client';
import type { AISummary as AISummaryType } from '../types';

interface Props {
  subscribe: (type: string, handler: (data: Record<string, unknown>) => void) => () => void;
}

export default function AISummary({ subscribe }: Props) {
  const [summary, setSummary] = useState<AISummaryType | null>(null);
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchSummary = () => {
    getSummary().then(setSummary).catch(console.error);
  };

  useEffect(() => { fetchSummary(); }, []);

  useEffect(() => {
    return subscribe('new_summary', () => fetchSummary());
  }, [subscribe]);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const result = await generateSummary();
      if (result.error) {
        alert(result.error);
      } else {
        fetchSummary();
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to generate summary');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!summary?.content) return;
    await navigator.clipboard.writeText(summary.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Render inline bold (**text**) within a string
  const renderInline = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i} className="text-gray-100 font-semibold">{part.slice(2, -2)}</strong>
        : <span key={i}>{part}</span>
    );
  };

  const renderMarkdown = (text: string) => {
    return text.split('\n').map((line, i) => {
      if (line.startsWith('## ')) {
        return <h3 key={i} className="text-sm font-semibold text-blue-400 mt-4 mb-1 border-b border-gray-800 pb-0.5">{line.slice(3)}</h3>;
      }
      if (/^\d+\.\s/.test(line)) {
        // Numbered list item
        const content = line.replace(/^\d+\.\s/, '');
        return <li key={i} className="text-xs text-gray-300 ml-4 list-decimal mb-0.5">{renderInline(content)}</li>;
      }
      if (line.startsWith('- ')) {
        return <li key={i} className="text-xs text-gray-300 ml-4 list-disc mb-0.5">{renderInline(line.slice(2))}</li>;
      }
      if (line.trim() === '') return <div key={i} className="h-1.5" />;
      return <p key={i} className="text-xs text-gray-300 leading-relaxed">{renderInline(line)}</p>;
    });
  };

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-900/80 border-b border-gray-800">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2"
        >
          <span className="text-xs text-gray-500">{collapsed ? '\u25B6' : '\u25BC'}</span>
          <h2 className="text-sm font-medium text-amber-400 uppercase tracking-wider">Daily Intelligence Brief</h2>
        </button>
        <div className="flex items-center gap-2">
          {summary?.generated_at && (
            <span className="text-[10px] text-gray-500">
              Updated {formatDistanceToNow(new Date(summary.generated_at), { addSuffix: true })}
            </span>
          )}
          <button
            onClick={handleCopy}
            disabled={!summary?.content}
            className="text-[10px] px-2 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="text-[10px] px-2 py-1 rounded bg-blue-900/50 text-blue-300 hover:bg-blue-900 disabled:opacity-50"
          >
            {loading ? 'Generating...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="px-4 py-3 max-h-[400px] overflow-y-auto">
          {!summary?.content ? (
            <p className="text-gray-500 text-xs text-center py-4">
              No briefing generated yet. Click "Refresh" to generate, or set OPENAI_API_KEY in .env
            </p>
          ) : (
            <div className="space-y-0.5">
              {renderMarkdown(summary.content)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
