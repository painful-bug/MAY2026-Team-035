import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useApp } from '../store/useApp';
import Header from '../components/layout/Header';
import { 
  LayoutDashboard, 
  UserPlus, 
  Users, 
  Megaphone, 
  AlertOctagon, 
  Wrench,
  Settings, 
  ArrowLeftRight,
  LogOut,
  ShieldCheck,
  X,
  Calendar,
  Building2
} from 'lucide-react';

export default function AdminLayout() {
  const { logout, pendingRequests } = useApp();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    navigate('/');
    setTimeout(() => {
      logout();
    }, 50);
  };

  const navItems = [
    { name: 'Dashboard', path: '/admin', icon: LayoutDashboard, end: true },
    { name: 'Pending Registrations', path: '/admin/pending', icon: UserPlus, badgeKey: 'pending' },
    { name: 'Residents', path: '/admin/residents', icon: Users },
    { name: 'Admins', path: '/admin/admins', icon: ShieldCheck },
    { name: 'Departments', path: '/admin/departments', icon: Building2 },
    { name: 'Amenities Management', path: '/admin/amenities', icon: Calendar },
    { name: 'Notices Board', path: '/admin/notices', icon: Megaphone },
    { name: 'Complaints Management', path: '/admin/complaints', icon: AlertOctagon },
    { name: 'Maintenance Payments', path: '/admin/maintenance', icon: Wrench },
    { name: 'Settings', path: '/admin/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm animate-fade-in"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-slate-350 flex flex-col justify-between
        transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col overflow-y-auto flex-1">
          {/* Sidebar Header */}
          <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-500 text-white flex items-center justify-center font-bold">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <span className="font-bold text-white text-sm block">HomeBandhu</span>
                <span className="text-[10px] text-indigo-400 font-semibold block uppercase tracking-wider">Admin Panel</span>
              </div>
            </div>
            <button 
              onClick={() => setSidebarOpen(false)}
              className="p-1 rounded-lg text-slate-400 hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1 flex-1">
            {navItems.map((item) => (
              <NavLink
                key={item.name}
                to={item.path}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => `
                  flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200
                  ${isActive 
                    ? 'border-l-4 border-amber-400 bg-indigo-650 text-white shadow-md shadow-indigo-900/30'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'}
                `}
              >
                <div className="flex items-center gap-3">
                  <item.icon className="w-5 h-5 flex-shrink-0" />
                  <span>{item.name}</span>
                </div>
                {item.badgeKey === 'pending' && pendingRequests.length > 0 && (
                  <span className="bg-rose-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {pendingRequests.length}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer Controls */}
        <div className="p-4 border-t border-slate-800 space-y-2 bg-slate-950/40">
          <button
            onClick={() => {
              setSidebarOpen(false);
              navigate('/resident');
            }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm shadow-emerald-900/20"
          >
            <ArrowLeftRight className="w-4 h-4" />
            Switch to Resident App
          </button>

          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-800 hover:bg-rose-950/40 hover:text-rose-400 hover:border-rose-900/60 text-slate-400 text-xs font-bold rounded-xl transition-all"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="p-6 flex-1 max-w-7xl w-full mx-auto animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
