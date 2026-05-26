import React, { useState, useEffect } from 'react';

const DAYS = [
  { key: '2026-05-25', label: 'Monday 25 May' },
  { key: '2026-05-26', label: 'Tuesday 26 May' },
  { key: '2026-05-27', label: 'Wednesday 27 May' },
  { key: '2026-05-28', label: 'Thursday 28 May' },
  { key: '2026-05-29', label: 'Friday 29 May' }
];

const HOURS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00'];

export default function AgendaView() {
  // 1. Initialize events state as an empty array
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);


  // 2. Fetch the JSON file dynamically when the component mounts
  useEffect(() => {
    // Adjust this path based on where you place the file in your public/ assets folder
    fetch('../JSON/scheduled_tasks.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load schedule data: ${response.statusText}`);
        }
        return response.json();
      })
      .then((data) => {
        setEvents(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error reading scheduled_tasks.json:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []); // Empty dependency array ensures this runs exactly once on load

  const getEventStyle = (item) => {
    if (item.type === 'block') {
      return 'bg-amber-100 border-l-4 border-amber-500 text-amber-800 font-semibold';
    }
    switch (item.phase) {
      case 'concept': return 'bg-purple-100 border-l-4 border-purple-500 text-purple-800';
      case 'planning': return 'bg-blue-100 border-l-4 border-blue-500 text-blue-800';
      case 'execution': return 'bg-emerald-100 border-l-4 border-emerald-500 text-emerald-800';
      default: return 'bg-indigo-100 border-l-4 border-indigo-500 text-indigo-800';
    }
  };

  const getEventsForSlot = (date, hour) => {
    const slotHour = parseInt(hour.split(':')[0], 10);
    
    return events.filter(event => {
      if (event.date !== date) return false;
      const [startH] = event.start_time.split(':').map(Number);
      const [endH, endM] = event.end_time.split(':').map(Number);
      
      const endHourAdjusted = endM > 0 ? endH + 1 : endH;
      return slotHour >= startH && slotHour < endHourAdjusted;
    });
  };

  // Render basic layout states while fetching the asynchronous local file stream
  if (loading) {
    return <div className="p-6 text-center text-gray-500">🔄 Synchronizing AI schedule engine database...</div>;
  }

  if (error) {
    return <div className="p-6 text-center text-red-500">🚨 Error: {error}. Make sure scheduled_tasks.json exists.</div>;
  }

  return (
    <div className="p-6 bg-gray-50 min-h-screen font-sans">
      <div className="max-w-7xl mx-auto bg-white rounded-xl shadow-md overflow-hidden p-6">
        
        {/* Header Dashboard */}
        <div className="flex justify-between items-center border-b pb-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">🗓️ Student Well-Being Smart Sheet</h1>
            <p className="text-sm text-gray-500">Live Production Timetable View • Week of 25 May 2026</p>
          </div>
          <div className="flex gap-3 text-xs">
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-amber-400 rounded"></span> Fixed Classes</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-purple-400 rounded"></span> Concept</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 rounded"></span> Planning</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-emerald-400 rounded"></span> Execution</span>
          </div>
        </div>

        {/* Semantic Spreadsheet Matrix */}
        <div className="overflow-x-auto border border-gray-200 rounded-lg shadow-sm">
          <table className="w-full table-fixed border-collapse bg-white">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                <th className="w-20 p-3 text-xs font-semibold text-gray-500 uppercase tracking-wider border-r border-gray-200 bg-gray-50 text-center">
                  Time
                </th>
                {DAYS.map(day => (
                  <th key={day.key} className="p-3 text-sm font-bold text-gray-700 border-r border-gray-200 last:border-r-0 text-center">
                    {day.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {HOURS.map((hour) => (
                <tr key={hour} className="border-b border-gray-100 hover:bg-gray-50/50 transition-colors last:border-b-0 h-24">
                  <td className="p-2 text-xs font-medium text-gray-400 border-r border-gray-200 bg-gray-50 text-center align-top pt-3 select-none">
                    {hour}
                  </td>
                  {DAYS.map(day => {
                    const slotEvents = getEventsForSlot(day.key, hour);
                    return (
                      <td key={day.key} className="p-1.5 border-r border-gray-200 last:border-r-0 align-top relative">
                        <div className="flex flex-col gap-1 h-full w-full justify-start">
                          {slotEvents.map((event, idx) => {
                            const isStartingSlot = event.start_time.startsWith(hour.split(':')[0]);
                            return (
                              <div
                                key={idx}
                                className={`p-1.5 rounded text-[11px] leading-tight transition-all overflow-hidden ${getEventStyle(event)} ${
                                  !isStartingSlot ? 'opacity-40 border-dashed border-l-2' : 'shadow-sm'
                                }`}
                              >
                                <div className="font-bold truncate">
                                  {isStartingSlot ? event.title : `(Continuation) ${event.title}`}
                                </div>
                                {isStartingSlot && (
                                  <div className="text-[9px] opacity-80 mt-0.5">
                                    🕒 {event.start_time} - {event.end_time}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}