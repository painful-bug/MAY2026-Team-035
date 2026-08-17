import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useApp } from '../store/useApp';
import { AUTH_ROUTES } from '../routes/authRoutes';
import Header from '../components/layout/Header';
import PortalErrorBoundary from '../components/common/PortalErrorBoundary';
import {
  LayoutDashboard, 
  Users, 
  AlertOctagon, 
  Calendar, 
  CreditCard, 
  BellRing, 
  User, 
  ArrowLeftRight,
  LogOut,
  Building,
  X,
  PhoneCall,
  CircleHelp
} from 'lucide-react';

export default function ResidentLayout() {
  const { currentUser, logout } = useApp();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    void logout();
    navigate(AUTH_ROUTES.RESIDENT_LANDING);
  };

  const navItems = [
    { name: 'Dashboard', path: '/resident', icon: LayoutDashboard, end: true },
    { name: 'Visitors', path: '/resident/visitors', icon: Users },
    { name: 'Complaints', path: '/resident/complaints', icon: AlertOctagon },
    { name: 'Amenities', path: '/resident/amenities', icon: Calendar },
    { name: 'Payments', path: '/resident/payments', icon: CreditCard },
    { name: 'Notices', path: '/resident/notices', icon: BellRing },
    { name: 'Help & FAQ', path: '/resident/faq', icon: CircleHelp },
    { name: 'Profile', path: '/resident/profile', icon: User },
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
        fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-100 flex flex-col justify-between
        transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col overflow-y-auto flex-1">
          {/* Sidebar Header */}
          <div className="h-16 flex items-center justify-between px-6 border-b border-slate-50">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold">
                <Building className="w-4 h-4" />
              </div>
              <div>
                <span className="font-bold text-slate-800 text-sm block">HomeBandhu</span>
                <span className="text-[10px] text-slate-400 font-semibold block uppercase tracking-wider">Residency</span>
              </div>
            </div>
            <button 
              onClick={() => setSidebarOpen(false)}
              className="p-1 rounded-lg text-slate-400 hover:bg-slate-50"
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
                  flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200
                  ${isActive 
                    ? 'border-l-4 border-amber-400 bg-indigo-600 text-white shadow-md shadow-indigo-100'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'}
                `}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {item.name}
              </NavLink>
            ))}
          </nav>

          {/* Bottom Help Widget */}
          <div className="p-4 mx-4 mb-4 bg-indigo-50/50 rounded-2xl border border-indigo-100/50 hidden lg:block">
            <div className="flex gap-3 items-start mb-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600 flex-shrink-0">
                <PhoneCall className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-bold text-indigo-950">Need help?</p>
                <p className="text-[10px] text-indigo-700/80 mt-0.5 leading-relaxed">Contact the management office for any query.</p>
              </div>
            </div>
            <button 
              onClick={() => navigate('/resident/profile')}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-2 rounded-xl transition-all shadow-sm"
            >
              Contact Office
            </button>
          </div>
        </div>

        {/* Sidebar Footer Controls */}
        <div className="p-4 border-t border-slate-50 space-y-2">
          {currentUser && currentUser.role === 'Admin' && (
            <button
              onClick={() => {
                setSidebarOpen(false);
                navigate('/admin');
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl transition-all shadow-sm shadow-amber-100"
            >
              <ArrowLeftRight className="w-4 h-4" />
              Switch to Admin Panel
            </button>
          )}

          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-100 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-100 text-slate-600 text-xs font-bold rounded-xl transition-all"
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
          <PortalErrorBoundary>
            <Outlet />
          </PortalErrorBoundary>
        </main>
      </div>
    </div>
  );
}
