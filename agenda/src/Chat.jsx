import { useState, useRef, useEffect } from 'react'
import './Chat.css'

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [convId, setConvId] = useState(null)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function addToken(content) {
    setMessages(prev => {
      const last = prev[prev.length - 1]
      if (last?.role === 'assistant') {
        const updated = [...prev]
        updated[updated.length - 1] = { ...last, content: last.content + content }
        return updated
      }
      return [...prev, { role: 'assistant', content }]
    })
  }

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    setPendingConfirm(null)

    const cid = convId || crypto.randomUUID().slice(0, 12)
    if (!convId) setConvId(cid)

    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, conversation_id: cid })
    })

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        if (line.startsWith('event: ')) {
          const eventType = line.slice(7).trim()
          const next = lines[i + 1]
          if (next?.startsWith('data: ')) {
            const data = next.slice(6)
            if (eventType === 'token') {
              addToken(data)
            } else if (eventType === 'status') {
              setMessages(prev => [...prev, { role: 'status', content: data }])
            } else if (eventType === 'project_proposal') {
              try {
                const info = JSON.parse(data)
                setPendingConfirm({ convId: cid, ...info })
              } catch {}
            } else if (eventType === 'done') {
              setLoading(false)
            }
          }
        }
      }
    }
    setLoading(false)
  }

  async function handleConfirm(approved) {
    const info = pendingConfirm
    setPendingConfirm(null)
    setMessages(prev => [...prev, {
      role: 'tool',
      content: approved ? 'Approved — saving project and running scheduler...' : 'Declined — changes discarded.'
    }])
    const resp = await fetch(`/api/confirm/${info.convId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    })
    const result = await resp.json()
    if (result.status === 'approved') {
      setMessages(prev => [...prev, {
        role: 'tool',
        content: 'Project saved and tasks scheduled! Check the Schedule tab.'
      }])
    } else if (result.status === 'rejected') {
      setMessages(prev => [...prev, {
        role: 'tool',
        content: 'Changes discarded. Continue chatting to refine.'
      }])
    }
  }

  async function handleNewChat() {
    if (convId) {
      await fetch(`/api/conversation/${convId}`, { method: 'DELETE' })
    }
    setMessages([])
    setConvId(null)
    setInput('')
    setPendingConfirm(null)
  }

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>AI Planner Chat</h1>
        <button className="new-chat-btn" onClick={handleNewChat}>+ New Chat</button>
      </header>

      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <p>Plan your projects with the AI Planner assistant.</p>
            <p className="examples">
              Try: "I have a new project about building a mobile app, deadline next Friday"
            </p>
          </div>
        )}

        {messages.map((msg, i) => {
          if (msg.role === 'status') {
            return <div key={i} className="status-msg">{msg.content}</div>
          }
          if (msg.role === 'tool') {
            return <div key={i} className="tool-msg">{msg.content}</div>
          }
          return (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">{msg.content}</div>
            </div>
          )
        })}

        {loading && !pendingConfirm && (
          <div className="message assistant">
            <div className="bubble typing">
              <span className="dot-pulse"></span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {pendingConfirm && (
        <div className="confirm-overlay">
          <div className="confirm-dialog">
            <h3>Approve Project Plan</h3>
            <p className="confirm-detail">{pendingConfirm.summary}</p>
            {pendingConfirm.diff?.length > 0 && (
              <ul className="diff-list">
                {pendingConfirm.diff.map((d, i) => (
                  <li key={i} className={d.startsWith('+') ? 'diff-add' : d.startsWith('-') ? 'diff-rem' : 'diff-neutral'}>
                    {d}
                  </li>
                ))}
              </ul>
            )}
            <div className="confirm-actions">
              <button className="confirm-btn reject" onClick={() => handleConfirm(false)}>Reject</button>
              <button className="confirm-btn approve" onClick={() => handleConfirm(true)}>Approve & Schedule</button>
            </div>
          </div>
        </div>
      )}

      <form className="input-bar" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Try to describe your project or sum..."
          disabled={loading || pendingConfirm}
        />
        <button type="submit" disabled={loading || !input.trim() || pendingConfirm}>Send</button>
      </form>
    </div>
  )
}
