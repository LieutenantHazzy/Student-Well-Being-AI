import { useState, useEffect, useMemo } from 'react'

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatDayLabel(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  return `${DAY_NAMES[d.getDay()]} ${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`
}

function weekStart(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const mon = new Date(d)
  mon.setDate(d.getDate() + diff)
  return `${mon.getFullYear()}-${String(mon.getMonth() + 1).padStart(2, '0')}-${String(mon.getDate()).padStart(2, '0')}`
}

function weekLabel(weekKey) {
  const start = new Date(weekKey + 'T00:00:00')
  const end = new Date(start)
  end.setDate(start.getDate() + 4)
  const fmt = (d) => `${d.getDate()} ${MONTH_NAMES[d.getMonth()]}`
  return `${fmt(start)} – ${fmt(end)} ${start.getFullYear()}`
}

const PROJECT_COLORS = [
  { bg: 'bg-rose-100', border: 'border-rose-400', text: 'text-rose-800', dot: 'bg-rose-400' },
  { bg: 'bg-cyan-100', border: 'border-cyan-500', text: 'text-cyan-800', dot: 'bg-cyan-500' },
  { bg: 'bg-amber-100', border: 'border-amber-500', text: 'text-amber-800', dot: 'bg-amber-500' },
  { bg: 'bg-lime-100', border: 'border-lime-500', text: 'text-lime-800', dot: 'bg-lime-500' },
  { bg: 'bg-pink-100', border: 'border-pink-400', text: 'text-pink-800', dot: 'bg-pink-400' },
  { bg: 'bg-teal-100', border: 'border-teal-500', text: 'text-teal-800', dot: 'bg-teal-500' },
  { bg: 'bg-orange-100', border: 'border-orange-400', text: 'text-orange-800', dot: 'bg-orange-400' },
  { bg: 'bg-violet-100', border: 'border-violet-400', text: 'text-violet-800', dot: 'bg-violet-400' },
]

function projectColor(projectId) {
  if (!projectId) return null
  let hash = 0
  for (let i = 0; i < projectId.length; i++) {
    hash = ((hash << 5) - hash) + projectId.charCodeAt(i)
  }
  return PROJECT_COLORS[Math.abs(hash) % PROJECT_COLORS.length]
}

export default function ScheduleView() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedWeek, setSelectedWeek] = useState(null)
  const [unscheduled, setUnscheduled] = useState([])
  const [showUnscheduled, setShowUnscheduled] = useState(false)

  function loadSchedule() {
    setLoading(true)
    fetch('/api/schedule/data')
      .then(r => r.json())
      .then(data => {
        setEvents(data.data || [])
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
    fetch('/api/schedule/unscheduled')
      .then(r => r.json())
      .then(data => setUnscheduled(data.data || []))
      .catch(() => {})
  }

  useEffect(() => {
    loadSchedule()
  }, [])

  const weeks = useMemo(() => {
    const map = {}
    events.forEach(event => {
      const wk = weekStart(event.date)
      if (!map[wk]) map[wk] = []
      map[wk].push(event)
    })
    const keys = Object.keys(map).sort()
    return keys.map(k => ({ key: k, label: weekLabel(k), events: map[k] }))
  }, [events])

  useEffect(() => {
    if (weeks.length > 0 && !selectedWeek) {
      setSelectedWeek(weeks[weeks.length - 1].key)
    }
  }, [weeks, selectedWeek])

  const currentWeek = useMemo(() => {
    return weeks.find(w => w.key === selectedWeek) || weeks[weeks.length - 1] || null
  }, [weeks, selectedWeek])

  const days = useMemo(() => {
    if (!currentWeek) return []
    const seen = new Set()
    return currentWeek.events
      .filter(e => !seen.has(e.date) && seen.add(e.date))
      .map(e => ({ key: e.date, label: formatDayLabel(e.date) }))
      .sort((a, b) => a.key.localeCompare(b.key))
  }, [currentWeek])

  const hours = useMemo(() => {
    if (!currentWeek) return []
    let minHour = 23, maxHour = 0
    currentWeek.events.forEach(event => {
      const startH = parseInt(event.start_time.split(':')[0], 10)
      const endH = parseInt(event.end_time.split(':')[0], 10)
      const endM = parseInt(event.end_time.split(':')[1], 10)
      const endAdjusted = endM > 0 ? endH + 1 : endH
      if (startH < minHour) minHour = startH
      if (endAdjusted > maxHour) maxHour = endAdjusted
    })
    const result = []
    for (let h = minHour; h < maxHour; h++) {
      result.push(`${String(h).padStart(2, '0')}:00`)
    }
    return result
  }, [currentWeek])

  const getEventStyle = (item) => {
    if (item.type === 'block') {
      return 'bg-amber-100 border-l-4 border-amber-500 text-amber-800 font-semibold'
    }
    switch (item.phase) {
      case 'concept': return 'bg-purple-100 border-l-4 border-purple-500 text-purple-800'
      case 'planning': return 'bg-blue-100 border-l-4 border-blue-500 text-blue-800'
      case 'execution': return 'bg-emerald-100 border-l-4 border-emerald-500 text-emerald-800'
      default: return 'bg-indigo-100 border-l-4 border-indigo-500 text-indigo-800'
    }
  }

  const projectNames = useMemo(() => {
    const names = new Set()
    events.forEach(e => {
      if (e.project_title) names.add(e.project_title)
    })
    return Array.from(names).sort()
  }, [events])

  const getEventsForSlot = (date, hour) => {
    const slotHour = parseInt(hour.split(':')[0], 10)
    return (currentWeek?.events || []).filter(event => {
      if (event.date !== date) return false
      const [startH] = event.start_time.split(':').map(Number)
      const [endH, endM] = event.end_time.split(':').map(Number)
      const endHourAdjusted = endM > 0 ? endH + 1 : endH
      return slotHour >= startH && slotHour < endHourAdjusted
    })
  }

  if (loading) {
    return <div className="p-6 text-center text-gray-500">Synchronizing AI schedule engine database...</div>
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-red-500">Error: {error}</p>
        <p className="text-sm text-gray-400 mt-2">Run the scheduler first by chatting with the AI Planner and approving a project plan.</p>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="p-6 text-center text-gray-500">
        <p>No scheduled tasks yet.</p>
        <p className="text-sm opacity-70 mt-1">Go to the AI Planner Chat tab, describe your project, and approve a plan.</p>
        <button
          onClick={loadSchedule}
          className="mt-4 px-6 py-2 rounded-lg border border-gray-300 text-sm cursor-pointer hover:bg-gray-100"
        >
          Refresh
        </button>
      </div>
    )
  }

  return (
    <div className="p-6 bg-gray-50 font-sans" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div className="max-w-7xl mx-auto bg-white rounded-xl shadow-md p-6" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        <div className="flex justify-between items-center border-b pb-4 mb-6 flex-shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Student Well-Being Smart Sheet</h1>
            <p className="text-sm text-gray-500">Live Production Timetable View</p>
          </div>
          <div className="flex gap-3 text-xs items-center">
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-amber-400 rounded"></span> Fixed Classes</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-purple-400 rounded"></span> Concept</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 rounded"></span> Planning</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-400 rounded"></span> Execution</span>
            <span className="w-px h-4 bg-gray-300 mx-1"></span>
            {projectNames.map(name => {
              const pColor = projectColor(name)
              if (!pColor) return null
              return (
                <span key={name} className="flex items-center gap-1 text-gray-500">
                  <span className={`w-2.5 h-2.5 rounded-full ${pColor.dot}`}></span>
                  {name}
                </span>
              )
            })}
          </div>
        </div>

        {unscheduled.length > 0 && (
          <div className="mb-4 flex-shrink-0">
            <button
              onClick={() => setShowUnscheduled(!showUnscheduled)}
              className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg border border-amber-300 bg-amber-50 text-amber-800 text-sm font-medium cursor-pointer hover:bg-amber-100 transition-colors"
            >
              <span className="text-amber-600 text-base">⚠️</span>
              <span>{unscheduled.length} task{unscheduled.length > 1 ? 's' : ''} could not be scheduled</span>
              <span className="ml-auto text-amber-500 text-xs">{showUnscheduled ? 'Hide details ▴' : 'Show details ▾'}</span>
            </button>
            {showUnscheduled && (
              <div className="mt-2 border border-amber-200 rounded-lg bg-amber-50/50 p-3 text-sm">
                {unscheduled.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 border-b border-amber-100 last:border-b-0">
                    <span className={`inline-block w-2 h-2 rounded-full ${
                      t.reason === 'deadline_exceeded' ? 'bg-red-400' : 'bg-amber-400'
                    }`} title={t.reason}></span>
                    <span className="font-medium text-gray-800">{t.title}</span>
                    <span className="text-gray-400">· {t.project_title}</span>
                    <span className="text-gray-400">{t.hours}h</span>
                    <span className="ml-auto text-xs text-gray-500 italic">
                      {t.reason === 'deadline_exceeded' ? 'Deadline passed' : 'No free slot'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {weeks.length > 1 && (
          <div className="flex gap-2 mb-4 flex-shrink-0 overflow-x-auto">
            {weeks.map(w => (
              <button
                key={w.key}
                onClick={() => setSelectedWeek(w.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border cursor-pointer whitespace-nowrap ${
                  w.key === selectedWeek
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        )}

        <div className="overflow-auto border border-gray-200 rounded-lg shadow-sm flex-1 min-h-0">
          <table className="w-full table-fixed border-collapse bg-white">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200 sticky top-0 z-10">
                <th className="w-20 p-3 text-xs font-semibold text-gray-500 uppercase tracking-wider border-r border-gray-200 bg-gray-50 text-center">
                  Time
                </th>
                {days.map(day => (
                  <th key={day.key} className="p-3 text-sm font-bold text-gray-700 border-r border-gray-200 last:border-r-0 text-center bg-gray-50">
                    {day.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hours.map((hour) => (
                <tr key={hour} className="border-b border-gray-100 hover:bg-gray-50/50 transition-colors last:border-b-0 h-24">
                  <td className="p-2 text-xs font-medium text-gray-400 border-r border-gray-200 bg-gray-50 text-center align-top pt-3 select-none">
                    {hour}
                  </td>
                  {days.map(day => {
                    const slotEvents = getEventsForSlot(day.key, hour)
                    return (
                      <td key={day.key} className="p-1.5 border-r border-gray-200 last:border-r-0 align-top relative">
                        <div className="flex flex-col gap-1 h-full w-full justify-start">
                          {slotEvents.map((event, idx) => {
                            const isStartingSlot = event.start_time.startsWith(hour.split(':')[0])
                            return (
                              <div
                                key={idx}
                                className={`p-1.5 rounded text-[11px] leading-tight transition-all overflow-hidden ${getEventStyle(event)} ${
                                  !isStartingSlot ? 'opacity-40 border-dashed border-l-2' : 'shadow-sm'
                                }`}
                              >
                                <div className="font-bold truncate flex items-center gap-1">
                                  {event.project_title && isStartingSlot && (
                                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${projectColor(event.project_title)?.dot || 'bg-gray-300'}`} title={event.project_title}></span>
                                  )}
                                  {isStartingSlot ? event.title : `(Continuation) ${event.title}`}
                                </div>
                                {isStartingSlot && (
                                  <div className="text-[9px] opacity-80 mt-0.5">
                                    {event.start_time} - {event.end_time}
                                    {event.project_title && <span className="ml-1 opacity-60">· {event.project_title}</span>}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}