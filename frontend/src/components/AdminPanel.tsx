import { useEffect, useState } from 'react';
import {
  getTelegramChannels, addTelegramChannel, toggleChannel, deleteChannel,
  getConfig, setConfig,
} from '../api/client';
import type { TelegramChannel } from '../types';

export default function AdminPanel() {
  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [newChannel, setNewChannel] = useState('');
  const [newChannelName, setNewChannelName] = useState('');
  const [keywords, setKeywords] = useState('');
  const [nytApiKey, setNytApiKey] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');

  useEffect(() => {
    getTelegramChannels().then(setChannels).catch(console.error);
    getConfig().then(config => {
      if (config.keywords) setKeywords((config.keywords as string[]).join(', '));
      if (config.nyt_api_key) setNytApiKey(config.nyt_api_key as string);
      if (config.openai_api_key) setOpenaiApiKey(config.openai_api_key as string);
    }).catch(console.error);
  }, []);

  const handleAddChannel = async () => {
    if (!newChannel) return;
    try {
      const result = await addTelegramChannel(newChannel, newChannelName);
      setNewChannel('');
      setNewChannelName('');
      getTelegramChannels().then(setChannels);
      alert(`✅ Added: ${(result.data as any)?.display_name || newChannel}. Backfilling messages...`);
    } catch (e: any) {
      const detail = e.response?.data?.detail || 'Failed to add channel';
      alert(`❌ ${detail}`);
    }
  };

  const handleToggle = async (id: number) => {
    await toggleChannel(id);
    getTelegramChannels().then(setChannels);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this channel?')) return;
    await deleteChannel(id);
    getTelegramChannels().then(setChannels);
  };

  const saveKeywords = async () => {
    const kwList = keywords.split(',').map(k => k.trim()).filter(Boolean);
    await setConfig('keywords', kwList);
    alert('Keywords saved');
  };

  const saveNytKey = async () => {
    await setConfig('nyt_api_key', nytApiKey);
    alert('NYT API key saved');
  };

  const saveOpenaiKey = async () => {
    await setConfig('openai_api_key', openaiApiKey);
    alert('OpenAI API key saved');
  };

  return (
    <div className="min-h-screen bg-gray-950 p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Admin Panel</h1>
        <a href="/" className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 px-3 py-1.5 rounded">
          Back to Dashboard
        </a>
      </div>

      {/* Telegram Channels */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Telegram Channels</h2>
        <div className="space-y-2 mb-4">
          {channels.map(ch => (
            <div key={ch.id} className="flex items-center gap-3 bg-gray-900 p-3 rounded-lg border border-gray-800">
              <div className="flex-1">
                <span className="text-sm text-gray-200">{ch.display_name}</span>
                <span className="text-xs text-gray-500 ml-2">{ch.channel_identifier}</span>
              </div>
              <button
                onClick={() => handleToggle(ch.id)}
                className={`text-xs px-2 py-1 rounded ${ch.is_active ? 'bg-green-800 text-green-300' : 'bg-gray-700 text-gray-400'}`}
              >
                {ch.is_active ? 'Active' : 'Paused'}
              </button>
              <button
                onClick={() => handleDelete(ch.id)}
                className="text-xs px-2 py-1 rounded bg-red-900/50 text-red-400 hover:bg-red-900"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={newChannel}
            onChange={e => setNewChannel(e.target.value)}
            placeholder="@channel_name or invite link"
            className="flex-1 bg-gray-800 text-gray-300 text-sm p-2 rounded border border-gray-700"
          />
          <input
            value={newChannelName}
            onChange={e => setNewChannelName(e.target.value)}
            placeholder="Display name (optional)"
            className="w-48 bg-gray-800 text-gray-300 text-sm p-2 rounded border border-gray-700"
          />
          <button
            onClick={handleAddChannel}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 rounded transition-colors"
          >
            Add
          </button>
        </div>
      </section>

      {/* Keywords */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Flagging Keywords</h2>
        <p className="text-xs text-gray-500 mb-2">Comma-separated keywords for flagging Telegram messages</p>
        <textarea
          value={keywords}
          onChange={e => setKeywords(e.target.value)}
          rows={3}
          className="w-full bg-gray-800 text-gray-300 text-sm p-2 rounded border border-gray-700 mb-2"
        />
        <button onClick={saveKeywords} className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded">
          Save Keywords
        </button>
      </section>

      {/* API Keys */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">API Keys</h2>

        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1">OpenAI API Key (for AI Summary)</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={openaiApiKey}
                onChange={e => setOpenaiApiKey(e.target.value)}
                placeholder="sk-..."
                className="flex-1 bg-gray-800 text-gray-300 text-sm p-2 rounded border border-gray-700"
              />
              <button onClick={saveOpenaiKey} className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 rounded">
                Save
              </button>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-400 block mb-1">NYT API Key (optional)</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={nytApiKey}
                onChange={e => setNytApiKey(e.target.value)}
                placeholder="Enter NYT API key"
                className="flex-1 bg-gray-800 text-gray-300 text-sm p-2 rounded border border-gray-700"
              />
              <button onClick={saveNytKey} className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 rounded">
                Save
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
