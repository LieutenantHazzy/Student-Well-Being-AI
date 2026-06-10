import { useState } from 'react'
import Chat from './Chat.jsx'
import ScheduleView from './ScheduleView.jsx'
import JsonViewer from './JsonViewer.jsx'

export default function App() {
  const [tab, setTab] = useState('chat')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <nav style={{
        display: 'flex', alignItems: 'center', gap: 0,
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg)', padding: '0 24px',
        flexShrink: 0
      }}>
        <h1 style={{
          fontSize: 18, fontWeight: 700, marginRight: 32, whiteSpace: 'nowrap',
          color: 'var(--text-h)'
        }}>
          Student Well-being AI
        </h1>
        <button
          onClick={() => setTab('chat')}
          style={{
            padding: '14px 20px', border: 'none', cursor: 'pointer',
            background: tab === 'chat' ? 'var(--accent-bg)' : 'transparent',
            color: tab === 'chat' ? 'var(--accent)' : 'var(--text)',
            borderBottom: tab === 'chat' ? '2px solid var(--accent)' : '2px solid transparent',
            fontWeight: tab === 'chat' ? 600 : 400, fontSize: 14
          }}
        >
          AI Planner Chat
        </button>
        <button
          onClick={() => setTab('schedule')}
          style={{
            padding: '14px 20px', border: 'none', cursor: 'pointer',
            background: tab === 'schedule' ? 'var(--accent-bg)' : 'transparent',
            color: tab === 'schedule' ? 'var(--accent)' : 'var(--text)',
            borderBottom: tab === 'schedule' ? '2px solid var(--accent)' : '2px solid transparent',
            fontWeight: tab === 'schedule' ? 600 : 400, fontSize: 14
          }}
        >
          Schedule View
        </button>
      </nav>
      <main style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        <div style={{ flex: 1, minWidth: 0, display: tab === 'chat' ? 'flex' : 'none' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <JsonViewer url="/api/projects" title="Projects JSON" />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Chat />
          </div>
        </div>
        <div style={{ flex: 1, display: tab === 'schedule' ? 'flex' : 'none' }}>
          <ScheduleView />
        </div>
      </main>
    </div>
  )
}
