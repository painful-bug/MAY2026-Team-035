import React from 'react';
import { useApp } from '../../store/useApp';
import { Calendar } from 'lucide-react';

export default function Notices() {
  const { notices } = useApp();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Society Notice Board</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Official circulars, facility maintenance updates, and celebration plans.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {notices.map((notice) => {
          const isHigh = notice.urgency === 'High';
          const isMedium = notice.urgency === 'Medium';

          return (
            <div 
              key={notice.id} 
              className={`bg-white border rounded-2xl p-6 shadow-sm flex flex-col justify-between gap-4 transition-all hover:shadow-md ${
                isHigh ? 'border-l-4 border-l-rose-500' : isMedium ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-blue-500'
              }`}
            >
              <div className="space-y-3">
                <div className="flex justify-between items-start gap-4">
                  <div className="space-y-0.5">
                    <span className="text-[9px] font-extrabold px-2 py-0.5 bg-slate-50 border border-slate-100 rounded text-slate-400 uppercase tracking-wider">
                      {notice.category}
                    </span>
                    <h3 className="text-base font-extrabold text-slate-805 pt-1.5 leading-tight">{notice.title}</h3>
                  </div>
                  <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                    isHigh 
                      ? 'bg-rose-50 text-rose-700 border border-rose-100' 
                      : isMedium
                      ? 'bg-amber-50 text-amber-700 border border-amber-100'
                      : 'bg-blue-50 text-blue-700 border border-blue-100'
                  }`}>
                    {notice.urgency} Priority
                  </span>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed font-semibold">{notice.description}</p>
              </div>

              <div className="pt-3 border-t border-slate-50 flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>Posted: {notice.date} ({notice.timeAgo})</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
