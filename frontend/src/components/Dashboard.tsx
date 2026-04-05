import NewsFeed from './NewsFeed';
import TelegramFeed from './TelegramFeed';
import XFeed from './XFeed';
import AISummary from './AISummary';
import { useWebSocket } from '../hooks/useWebSocket';
import { DashboardProvider } from '../context/DashboardContext';

function DashboardContent() {
  const { connected, subscribe } = useWebSocket();

  return (
    <div className="min-h-screen bg-gray-950 p-4 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-100">OSINT War Monitor</h1>
        <div className="flex items-center gap-3">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-500">{connected ? 'Live' : 'Disconnected'}</span>
          <a href="/admin" className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 px-3 py-1.5 rounded">
            Admin
          </a>
        </div>
      </div>

      {/* AI Summary - top bar */}
      <div className="mb-4">
        <AISummary subscribe={subscribe} />
      </div>

      {/* Three panel layout: News | Telegram | X */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1" style={{ minHeight: 'calc(100vh - 200px)' }}>
        <div className="min-h-0">
          <NewsFeed subscribe={subscribe} />
        </div>
        <div className="min-h-0">
          <TelegramFeed subscribe={subscribe} />
        </div>
        <div className="min-h-0">
          <XFeed subscribe={subscribe} />
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <DashboardProvider>
      <DashboardContent />
    </DashboardProvider>
  );
}
