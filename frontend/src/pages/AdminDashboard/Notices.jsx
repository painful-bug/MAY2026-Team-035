import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { Megaphone, Plus, Calendar } from 'lucide-react';
import { api } from '../../lib/api/client';

export default function Notices() {
  const { notices, showToast } = useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('General');
  const [urgency, setUrgency] = useState('Info');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title || !description) return;
    try {
      await api('/notices', {
        method: 'POST',
        body: JSON.stringify({ title, description, category, urgency }),
      });
      showToast('Notice published successfully!', 'success');
      setTitle('');
      setDescription('');
      setCategory('General');
      setUrgency('Info');
      setModalOpen(false);
    } catch (error) {
      showToast(error.message || 'Failed to publish notice', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Manage Notice Board</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Publish circulars, facility maintenance updates, and celebration plans for residents.</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="bg-indigo-650 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          Post Notice
        </button>
      </div>

      {/* Notices Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {notices.map((notice) => {
          // The API stores urgency lowercase (info/important/urgent); the old
          // demo rows said High/Medium. Compare case-insensitively and accept
          // both vocabularies so neither generation of data renders unstyled.
          const urgency = (notice.urgency || '').toLowerCase();
          const isHigh = urgency === 'urgent' || urgency === 'high';
          const isMedium = urgency === 'important' || urgency === 'medium';

          return (
            <div 
              key={notice.id} 
              className={`bg-white border rounded-2xl p-6 shadow-sm flex flex-col justify-between gap-4 transition-all hover:shadow-md ${
                isHigh ? 'border-l-4 border-l-rose-500' : isMedium ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-indigo-500'
              }`}
            >
              <div className="space-y-3">
                <div className="flex justify-between items-start gap-4">
                  <div className="space-y-0.5">
                    {/* The snapshot's notice rows don't carry category or
                        urgency yet — hide the chips rather than render
                        "undefined". */}
                    {notice.category && (
                      <span className="text-[9px] font-extrabold px-2 py-0.5 bg-slate-50 border border-slate-100 rounded text-slate-400 uppercase tracking-wider">
                        {notice.category}
                      </span>
                    )}
                    <h3 className="text-base font-extrabold text-slate-805 pt-1.5 leading-tight">{notice.title}</h3>
                  </div>
                  {notice.urgency && (
                    <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                      isHigh
                        ? 'bg-rose-50 text-rose-700 border border-rose-100'
                        : isMedium
                        ? 'bg-amber-50 text-amber-700 border border-amber-100'
                        : 'bg-indigo-50 text-indigo-700 border border-indigo-100'
                    }`}>
                      {notice.urgency} Priority
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 leading-relaxed font-semibold">{notice.description}</p>
              </div>

              <div className="pt-3 border-t border-slate-50 flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                <Calendar className="w-3.5 h-3.5" />
                <span>Posted: {notice.date} ({notice.timeAgo})</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Post Notice Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-extrabold text-slate-900">Post New Notice</h3>
              <button 
                onClick={() => setModalOpen(false)}
                className="text-xs font-bold text-slate-400 hover:text-slate-650"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Notice Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Lift maintenance - Tower B"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    <option value="General">General</option>
                    <option value="Maintenance">Maintenance</option>
                    <option value="Celebration">Celebration</option>
                    <option value="Facility">Facility</option>
                    <option value="Security">Security</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Urgency Priority</label>
                  <select
                    value={urgency}
                    onChange={(e) => setUrgency(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                  >
                    {/* The API's vocabulary (NOTICE_URGENCIES, matched
                        case-insensitively) — the demo's Low/Medium/High values
                        were refused with a 422 on every publish. */}
                    <option value="Info">Info</option>
                    <option value="Important">Important</option>
                    <option value="Urgent">Urgent</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Announcement Description</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Type the notice details clearly for the residents..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-750 font-medium"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 mt-2 text-xs flex items-center justify-center gap-1.5"
              >
                <Megaphone className="w-4 h-4" />
                Publish Announcement
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
