import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { getVisitorSecurityCode } from '../../lib/visitorPasses';
import NotificationBell from '../notifications/NotificationBell';
import {
  Search,
  Bell,
  Menu,
  X,
  Megaphone,
  User,
  AlertCircle,
  Activity
} from 'lucide-react';

export default function Header({ onMenuClick }) {
  const {
    currentUser,
    users,
    notices,
    visitors,
    complaints,
    activities,
    searchQuery,
    setSearchQuery
  } = useApp();

  // The residency chip's data. `currentUser.flat`/`tower` were read here and
  // the session has never carried either (`applicationUser()` hard-codes both
  // to '—'), so every member saw "Flat — • Tower —". The snapshot's `users`
  // projection DOES carry them — `unit_residencies → units → buildings`, keyed
  // by profile id — so the chip reads its own row from there. The backend uses
  // the same '—' placeholder for members with no active residency (a pure
  // admin, typically), so '—' and absence both mean "no unit": the chip hides
  // rather than render a placeholder. While the snapshot is unavailable the
  // list is empty and the chip simply stays hidden.
  const residency = (users ?? []).find((user) => user.id === currentUser?.id);
  const flat = residency?.flat && residency.flat !== '—' ? residency.flat : '';
  const tower = residency?.tower && residency.tower !== '—' ? residency.tower : '';
  const unitLabel = [flat && `Flat ${flat}`, tower && `Tower ${tower}`]
    .filter(Boolean)
    .join(' • ');
  const statusChipLabel = currentUser
    ? ['Security', 'SecurityManager'].includes(currentUser.role)
      ? currentUser.role === 'SecurityManager'
        ? 'Security management'
        : 'On duty'
      : unitLabel
    : '';

  // Left Panel States
  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
  const [panelType, setPanelType] = useState('notifications'); // 'notifications' | 'search'

  // Open notifications panel
  const handleOpenNotifications = () => {
    setPanelType('notifications');
    setLeftPanelOpen(true);
  };

  // Perform search filtering
  const getSearchResults = () => {
    if (!searchQuery.trim()) return [];
    const query = searchQuery.toLowerCase();

    const matchedNotices = notices
      .filter(n => n.title.toLowerCase().includes(query) || n.description.toLowerCase().includes(query))
      .map(n => ({ ...n, resultType: 'Notice', icon: Megaphone, color: 'text-indigo-600 bg-indigo-50' }));

    const matchedVisitors = visitors
      .filter(v => v.name.toLowerCase().includes(query) || v.purpose.toLowerCase().includes(query))
      .map(v => ({ ...v, title: v.name, description: `Expected: ${v.eta} • Security code: ${getVisitorSecurityCode(v)}`, resultType: 'Visitor', icon: User, color: 'text-emerald-600 bg-emerald-50' }));

    const matchedComplaints = complaints
      .filter(c => c.title.toLowerCase().includes(query) || c.category.toLowerCase().includes(query))
      .map(c => ({ ...c, description: `Status: ${c.status} • Assigned: ${c.assignee}`, resultType: 'Complaint', icon: AlertCircle, color: 'text-rose-600 bg-rose-50' }));

    return [...matchedNotices, ...matchedVisitors, ...matchedComplaints];
  };

  const searchResults = getSearchResults();

  return (
    <>
      <header className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-4">
          {/* Menu trigger */}
          <button 
            onClick={onMenuClick}
            className="p-2 text-slate-500 hover:bg-slate-50 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* `departmentName` and `staffRole` were read here once and
              `applicationUser()` has never set either, so every gate user saw
              the literal "undefined • undefined" — and then residents saw
              "Flat — • Tower —" for the same reason. The label is computed
              above; when there is nothing truthful to say, no chip. */}
          {statusChipLabel && (
            <div className="flex items-center gap-2 bg-slate-50 border border-slate-100 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-600">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse"></span>
              {statusChipLabel}
            </div>
          )}
        </div>

        {/* Search bar inside header */}
        <div className="flex-1 max-w-md mx-8 hidden md:block">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search notices, visitors, complaints..."
              className="w-full bg-slate-50 border border-slate-100 rounded-full pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-300 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:bg-slate-100 rounded-full"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* The real notification feed (GET /notifications). The old bell here
              was a hard-coded red dot over demo data; the demo notice board it
              opened lives on behind the Megaphone button beside it. */}
          <NotificationBell />

          {/* Demo notice board + activity drawer */}
          <button
            onClick={handleOpenNotifications}
            className="relative p-2.5 text-slate-600 hover:bg-slate-50 rounded-full transition-colors"
            aria-label="Notice board"
          >
            <Megaphone className="w-5 h-5" />
          </button>

          {/* User profile */}
          {currentUser && (
            <div className="flex items-center gap-3 pl-3 border-l border-slate-100">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-bold text-slate-800">{currentUser.name}</p>
                <p className="text-[11px] font-semibold text-slate-400">
                  {currentUser.role === 'Admin'
                    ? 'Administrator'
                    : currentUser.role === 'SecurityManager'
                      ? 'Security Department Manager'
                      : currentUser.role === 'Security'
                      ? 'Security Staff'
                      : 'Resident Owner'}
                </p>
              </div>
              <div className="w-9 h-9 rounded-full bg-indigo-600 text-white font-bold flex items-center justify-center shadow-md shadow-indigo-100">
                {currentUser.name.charAt(0)}
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Left Side Panel Drawer Overlay */}
      {leftPanelOpen && (
        <div 
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm transition-opacity"
          onClick={() => setLeftPanelOpen(false)}
        />
      )}

      {/* Left Side Panel Component */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-96 bg-white border-r border-slate-100 flex flex-col justify-between
        transform transition-transform duration-300 ease-in-out shadow-2xl
        ${leftPanelOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Panel Header */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-slate-100">
          <div className="flex items-center gap-2">
            {panelType === 'notifications' ? (
              <>
                <Bell className="w-5 h-5 text-indigo-600" />
                <h3 className="font-extrabold text-slate-800 text-sm">Notifications & Board</h3>
              </>
            ) : (
              <>
                <Search className="w-5 h-5 text-indigo-600" />
                <h3 className="font-extrabold text-slate-800 text-sm">Quick Search</h3>
              </>
            )}
          </div>
          <button 
            onClick={() => setLeftPanelOpen(false)}
            className="p-1 rounded-lg text-slate-400 hover:bg-slate-50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Panel Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {panelType === 'notifications' ? (
            <>
              {/* Active Notices Section */}
              <div className="space-y-3">
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Active Bulletins</p>
                <div className="space-y-3">
                  {notices.slice(0, 3).map((notice) => (
                    <div key={notice.id} className="bg-slate-50 border border-slate-100 rounded-xl p-4 space-y-1.5 hover:bg-slate-100/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <span className={`text-[9px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          notice.urgency === 'High' 
                            ? 'bg-rose-50 text-rose-600' 
                            : notice.urgency === 'Medium' 
                            ? 'bg-amber-50 text-amber-600' 
                            : 'bg-indigo-50 text-indigo-600'
                        }`}>
                          {notice.urgency}
                        </span>
                        <span className="text-[10px] text-slate-400 font-semibold">{notice.date}</span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-800 line-clamp-1">{notice.title}</h4>
                      <p className="text-[11px] text-slate-450 leading-relaxed line-clamp-2">{notice.description}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Society Activities Log Section */}
              <div className="space-y-3">
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider flex items-center gap-1">
                  <Activity className="w-3.5 h-3.5 text-indigo-500" />
                  Recent Activity Log
                </p>
                <div className="space-y-4 pl-2 border-l-2 border-slate-100">
                  {activities.slice(0, 5).map((act) => (
                    <div key={act.id} className="relative pl-4 space-y-0.5 text-xs">
                      <span className="absolute -left-[21px] top-1.5 w-2 h-2 rounded-full bg-indigo-500 border border-white" />
                      <p className="font-semibold text-slate-700">{act.text}</p>
                      <p className="text-[10px] font-semibold text-slate-400">{act.time}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Search Panel input (useful for mobile) */}
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Type to filter..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-xs focus:outline-none focus:border-indigo-400 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>

              {/* Results List */}
              <div className="space-y-3">
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                  Matches ({searchResults.length})
                </p>
                
                {searchResults.length > 0 ? (
                  <div className="space-y-2.5">
                    {searchResults.map((res, index) => (
                      <div 
                        key={index}
                        className="bg-white border border-slate-100 hover:border-indigo-100 hover:shadow-md hover:shadow-indigo-50/10 rounded-xl p-3.5 flex items-start gap-3 transition-all cursor-pointer"
                        onClick={() => setLeftPanelOpen(false)}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${res.color}`}>
                          <res.icon className="w-4 h-4" />
                        </div>
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                              {res.resultType}
                            </span>
                          </div>
                          <h4 className="text-xs font-bold text-slate-800 line-clamp-1">{res.title}</h4>
                          <p className="text-[10px] text-slate-450 truncate">{res.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : searchQuery ? (
                  <div className="text-center py-8 text-slate-400 space-y-1">
                    <p className="text-xs font-bold">No matches found</p>
                    <p className="text-[10px] font-semibold text-slate-400">Try searching for notices, visitor names, or complaints.</p>
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-400 text-xs font-semibold">
                    Start typing to search HomeBandhu records...
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Panel Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50 flex justify-center text-center">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
            HomeBandhu Residency Security Guarded
          </p>
        </div>
      </aside>
    </>
  );
}
