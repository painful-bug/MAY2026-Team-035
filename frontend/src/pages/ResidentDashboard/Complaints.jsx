import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { AlertOctagon, HelpCircle, CheckCircle, Clock, Send, Hammer } from 'lucide-react';

export default function Complaints() {
  const { complaints, currentUser, raiseComplaint } = useApp();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Plumbing');
  const [urgency, setUrgency] = useState('Medium');

  const userComplaints = complaints.filter(c => c.userId === currentUser?.id);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title || !description) return;
    raiseComplaint({ title, description, category, urgency });
    setTitle('');
    setDescription('');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Complaint Management</h1>
        <p className="text-xs font-semibold text-slate-400 mt-1">Raise support tickets for maintenance, amenities, or security issues.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Raise ticket Form */}
        <div className="lg:col-span-4 bg-white p-6 border border-slate-100 rounded-2xl h-fit space-y-4 shadow-sm">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-50">
            <AlertOctagon className="w-5 h-5 text-rose-600" />
            <h3 className="font-extrabold text-slate-805 text-sm">File a Complaint</h3>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Issue Title</label>
              <input
                type="text"
                required
                placeholder="e.g. Leaking kitchen tap"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
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
                  <option value="Plumbing">Plumbing</option>
                  <option value="Electrical">Electrical</option>
                  <option value="Infrastructure">Infrastructure</option>
                  <option value="Cleaning">Cleaning</option>
                  <option value="Security">Security</option>
                  <option value="Others">Others</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Urgency</label>
                <select
                  value={urgency}
                  onChange={(e) => setUrgency(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Description</label>
              <textarea
                required
                rows={4}
                placeholder="Explain the problem in detail so the technician is prepared..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-medium"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-100 text-xs flex items-center justify-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              File Complaint
            </button>
          </form>
        </div>

        {/* Complaints List */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-white p-5 border border-slate-100 rounded-2xl flex items-center justify-between shadow-sm">
            <h3 className="font-extrabold text-slate-800 text-sm flex items-center gap-2">
              <Hammer className="w-5 h-5 text-indigo-650" />
              Raised Complaints Logs
            </h3>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-indigo-50 px-2.5 py-1 border border-indigo-100/50 rounded-lg text-indigo-700">
              {userComplaints.length} Tickets
            </span>
          </div>

          {userComplaints.length === 0 ? (
            <div className="bg-white p-12 text-center text-xs text-slate-400 font-semibold border border-slate-100 rounded-2xl">
              You haven't filed any complaints yet. Everything is working perfectly in your flat!
            </div>
          ) : (
            <div className="space-y-4">
              {userComplaints.map((comp) => (
                <div key={comp.id} className="bg-white border border-slate-100 p-6 rounded-2xl shadow-sm space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-base font-extrabold text-slate-850">{comp.title}</h4>
                        <span className={`text-[9px] font-extrabold uppercase px-2.5 py-0.5 rounded-full ${
                          comp.urgency === 'High' 
                            ? 'bg-rose-50 text-rose-700 border border-rose-100' 
                            : comp.urgency === 'Medium'
                            ? 'bg-amber-50 text-amber-700 border border-amber-100'
                            : 'bg-blue-50 text-blue-700 border border-blue-100'
                        }`}>
                          {comp.urgency} Urgency
                        </span>
                      </div>
                      <p className="text-[10px] font-semibold text-slate-400 mt-1">
                        Category: **{comp.category}** • Filed on {comp.date}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-auto">
                      <span className={`text-[10px] font-extrabold px-3 py-1 rounded-full border ${
                        comp.status === 'Resolved' 
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-100' 
                          : comp.status === 'In Progress'
                          ? 'bg-blue-50 text-blue-750 border-blue-100'
                          : 'bg-rose-50 text-rose-750 border-rose-100'
                      }`}>
                        {comp.status}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-500 leading-relaxed font-semibold">
                    {comp.description}
                  </p>

                  <div className="bg-slate-50 border border-slate-100/60 rounded-xl p-4.5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 text-xs font-semibold">
                    <div className="space-y-1">
                      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wide">Assigned To</p>
                      <p className="text-slate-800 font-bold">{comp.assignee || 'Awaiting assignment'}</p>
                    </div>
                    
                    {comp.status !== 'Resolved' ? (
                      <div className="flex-1 sm:max-w-xs w-full space-y-1.5">
                        <div className="flex justify-between text-[10px] font-bold text-slate-400">
                          <span>Progress</span>
                          <span>{comp.progress}%</span>
                        </div>
                        <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                          <div 
                            className="bg-indigo-650 h-full rounded-full transition-all duration-500" 
                            style={{ width: `${comp.progress}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-emerald-700 font-bold text-xs">
                        <CheckCircle className="w-4 h-4 text-emerald-600" />
                        <span>Resolved and Closed</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
