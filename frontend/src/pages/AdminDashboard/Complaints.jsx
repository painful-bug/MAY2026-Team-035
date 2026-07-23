import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { AlertOctagon, Edit2, CheckCircle2, User, Home, Clock, Check } from 'lucide-react';

export default function Complaints() {
  const { complaints, updateComplaint, addComplaintComment } = useApp();
  const [filterStatus, setFilterStatus] = useState('All');
  
  // Edit state
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({
    status: 'Pending',
    progress: 0,
    assignee: '',
    expectedResolutionAt: '',
    updateNote: '',
    comment: '',
  });

  const filteredComplaints = complaints.filter(c => {
    if (filterStatus === 'All') return true;
    return c.status === filterStatus;
  });

  const handleEditClick = (c) => {
    setEditingId(c.id);
    setEditForm({
      status: c.status,
      progress: c.progress,
      assignee: c.assignee,
      expectedResolutionAt: c.expectedResolutionAt
        ? c.expectedResolutionAt.slice(0, 16)
        : '',
      updateNote: '',
      comment: '',
    });
  };

  const handleSave = (id) => {
    updateComplaint(id, {
      status: editForm.status,
      progress: editForm.status === 'Resolved' ? 100 : Number(editForm.progress),
      assignee: editForm.assignee,
      expectedResolutionAt: editForm.expectedResolutionAt
        ? new Date(editForm.expectedResolutionAt).toISOString()
        : null,
      updateNote: editForm.updateNote,
    });
    if (editForm.comment.trim()) {
      addComplaintComment(id, editForm.comment);
    }
    setEditingId(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Complaints Management</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Review resident complaints, dispatch technicians, track repair progress, and close resolved tickets.</p>
        </div>

        {/* Filter buttons */}
        <div className="flex gap-2 self-start sm:self-auto bg-white border border-slate-100 p-1 rounded-xl shadow-sm text-xs font-bold">
          {['All', 'Pending', 'In Progress', 'Resolved'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                filterStatus === status 
                  ? 'bg-indigo-600 text-white shadow-sm' 
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Complaints Grid */}
      <div className="space-y-4">
        {filteredComplaints.length === 0 ? (
          <div className="bg-white border border-slate-100 p-12 text-center rounded-2xl text-xs text-slate-400 font-semibold">
            No complaints found matching this status filter.
          </div>
        ) : (
          filteredComplaints.map((c) => {
            const isEditing = editingId === c.id;

            return (
              <div key={c.id} className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm space-y-4 hover:border-slate-200 transition-colors">
                <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base font-extrabold text-slate-850">{c.title}</h3>
                      <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded ${
                        c.urgency === 'High' 
                          ? 'bg-rose-50 text-rose-700 border border-rose-100' 
                          : c.urgency === 'Medium'
                          ? 'bg-amber-50 text-amber-700 border border-amber-100'
                          : 'bg-blue-50 text-blue-700 border border-blue-100'
                      }`}>
                        {c.urgency} Urgency
                      </span>
                    </div>

                    <div className="flex items-center gap-3.5 text-[10px] font-bold text-slate-450">
                      <span className="flex items-center gap-1">
                        <Home className="w-3.5 h-3.5" /> Flat {c.flat}
                      </span>
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5" /> Raised By: {c.raisedBy}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> Filed: {c.date} ({c.timeAgo})
                      </span>
                    </div>
                  </div>

                  <span className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wide border ${
                    c.status === 'Resolved' 
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-100' 
                      : c.status === 'In Progress'
                      ? 'bg-blue-50 text-blue-750 border-blue-100'
                      : 'bg-rose-50 text-rose-750 border-rose-100'
                  }`}>
                    {c.status}
                  </span>
                </div>

                <p className="text-xs text-slate-500 leading-relaxed font-semibold">
                  {c.description}
                </p>

                {(c.comments ?? []).length > 0 && (
                  <div className="space-y-2 rounded-xl border border-slate-100 bg-slate-50 p-3">
                    <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                      Recent conversation
                    </p>
                    {c.comments.slice(-3).map((comment) => (
                      <div
                        key={comment.id}
                        className="rounded-lg bg-white px-3 py-2"
                      >
                        <p className="text-[10px] font-bold text-slate-700">
                          {comment.authorName}
                        </p>
                        <p className="mt-0.5 text-xs font-semibold text-slate-500">
                          {comment.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Edit Form or Display status details */}
                {isEditing ? (
                  <div className="bg-slate-50 border border-indigo-100 rounded-xl p-4.5 space-y-4">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                      <span className="text-[10px] font-extrabold uppercase text-indigo-650 tracking-wider">Update Ticket Status</span>
                      <button 
                        onClick={() => handleSave(c.id)}
                        className="px-3.5 py-1 bg-indigo-600 hover:bg-indigo-755 text-white text-[10px] font-bold rounded-lg transition-colors shadow-sm flex items-center gap-1"
                      >
                        <Check className="w-3.5 h-3.5" /> Save Changes
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-semibold">
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Staff / Assignee</label>
                        <input
                          type="text"
                          value={editForm.assignee}
                          onChange={(e) => setEditForm({ ...editForm, assignee: e.target.value })}
                          placeholder="e.g. Suresh - Electrician"
                          className="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500 font-semibold"
                        />
                      </div>

                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Status</label>
                        <select
                          value={editForm.status}
                          onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                          className="w-full bg-white border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500 font-semibold"
                        >
                          <option value="Pending">Pending</option>
                          <option value="In Progress">In Progress</option>
                          <option value="Resolved">Resolved</option>
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Expected Resolution</label>
                        <input
                          type="datetime-local"
                          value={editForm.expectedResolutionAt}
                          onChange={(e) =>
                            setEditForm({
                              ...editForm,
                              expectedResolutionAt: e.target.value,
                            })
                          }
                          className="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500 font-semibold"
                        />
                      </div>

                      {editForm.status !== 'Resolved' && (
                        <div className="space-y-1">
                          <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Progress Percent ({editForm.progress}%)</label>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            step="5"
                            value={editForm.progress}
                            onChange={(e) => setEditForm({ ...editForm, progress: e.target.value })}
                            className="w-full h-2 bg-slate-200 rounded-lg cursor-pointer accent-indigo-600 mt-2.5"
                          />
                        </div>
                      )}

                      <div className="space-y-1 sm:col-span-2">
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Resident-visible Update</label>
                        <textarea
                          rows={2}
                          value={editForm.updateNote}
                          onChange={(e) =>
                            setEditForm({
                              ...editForm,
                              updateNote: e.target.value,
                            })
                          }
                          placeholder="Explain what changed or what happens next."
                          className="w-full resize-none bg-white border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold"
                        />
                      </div>

                      <div className="space-y-1 sm:col-span-2">
                        <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Message Resident</label>
                        <textarea
                          rows={2}
                          value={editForm.comment}
                          onChange={(e) =>
                            setEditForm({
                              ...editForm,
                              comment: e.target.value,
                            })
                          }
                          placeholder="Reply to the resident's conversation."
                          className="w-full resize-none bg-white border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold"
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 text-xs font-semibold">
                    <div className="space-y-1">
                      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wide">Assigned Technician</p>
                      <p className="text-slate-800 font-bold">{c.assignee || 'Unassigned (Waiting review)'}</p>
                    </div>

                    <div className="flex-1 sm:max-w-xs w-full flex items-center gap-4">
                      {c.status !== 'Resolved' ? (
                        <div className="flex-1 space-y-1.5">
                          <div className="flex justify-between text-[10px] font-bold text-slate-400">
                            <span>Repair Progress</span>
                            <span>{c.progress}%</span>
                          </div>
                          <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                            <div 
                              className="bg-indigo-650 h-full rounded-full transition-all duration-500" 
                              style={{ width: `${c.progress}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-emerald-700 font-bold">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <span>Resolved</span>
                        </div>
                      )}

                      <button
                        onClick={() => handleEditClick(c)}
                        className="px-3 py-1.5 bg-white border border-slate-200 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 rounded-lg text-slate-500 font-bold transition-all flex items-center gap-1"
                      >
                        <Edit2 className="w-3 h-3" /> Update
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
