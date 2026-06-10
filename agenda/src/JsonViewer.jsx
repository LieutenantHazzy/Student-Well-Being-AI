import { useState, useEffect, useCallback } from 'react'

function JsonNode({ name, value, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)

  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value)
  const isArray = Array.isArray(value)
  const isExpandable = isObject || isArray

  const toggle = useCallback(() => setOpen(o => !o), [])

  if (!isExpandable) {
    const display = typeof value === 'string' ? `"${value}"` : String(value)
    const color =
      typeof value === 'string' ? '#22c55e' :
      typeof value === 'number' ? '#fb923c' :
      typeof value === 'boolean' ? '#a78bfa' :
      '#9ca3af'
    return (
      <div className="json-line" style={{ paddingLeft: 16 }}>
        {name !== null && <span className="json-key">{name}: </span>}
        <span className="json-value" style={{ color }}>{display}</span>
      </div>
    )
  }

  const items = isObject ? Object.entries(value) : value.map((v, i) => [i, v])
  const preview = isObject
    ? `{${items.length} key${items.length !== 1 ? 's' : ''}}`
    : `[${items.length} item${items.length !== 1 ? 's' : ''}]`

  return (
    <div className="json-node">
      <div className="json-line json-toggle" onClick={toggle} style={{ paddingLeft: name !== null ? 16 : 0 }}>
        <span className="json-arrow" style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}>
          ▶
        </span>
        {name !== null && <span className="json-key">{name}: </span>}
        <span className="json-preview">{preview}</span>
      </div>
      {open && (
        <div className="json-children">
          {items.map(([k, v]) => (
            <JsonNode key={k} name={isArray ? null : k} value={v} defaultOpen={defaultOpen} />
          ))}
        </div>
      )}
    </div>
  )
}

function JsonViewer({ url, title }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(true)

  function load() {
    setLoading(true)
    fetch(url)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  useEffect(() => { load() }, [url])

  return (
    <div className="json-viewer">
      <div className="json-viewer-header">
        <span className="json-viewer-title">{title || 'JSON'}</span>
        <button className="json-refresh-btn" onClick={load} title="Refresh">↻</button>
      </div>
      <div className="json-viewer-body">
        {loading && <div className="json-status">Loading...</div>}
        {error && <div className="json-status json-error">Error: {error}</div>}
        {!loading && !error && data !== null && (
          <div className="json-tree">
            <div className="json-line json-toggle" onClick={() => setExpanded(e => !e)} style={{ paddingLeft: 0 }}>
              <span className="json-arrow" style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
              <span className="json-key" style={{ fontWeight: 600 }}>root</span>
              <span className="json-preview">
                {Array.isArray(data) ? `[${data.length} items]` : `{${Object.keys(data).length} keys}`}
              </span>
            </div>
            {expanded && (
              <div className="json-children">
                {Array.isArray(data)
                  ? data.map((v, i) => <JsonNode key={i} name={null} value={v} defaultOpen={false} />)
                  : Object.entries(data).map(([k, v]) => <JsonNode key={k} name={k} value={v} defaultOpen={false} />)
                }
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default JsonViewer