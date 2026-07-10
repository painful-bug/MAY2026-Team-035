import React from 'react';
import { Building } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AUTH_ROUTES } from '../../routes/authRoutes';

export default function AuthCard({ title, description, children }) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-12 px-6 font-sans">
      <div className="max-w-md w-full space-y-8 bg-white border border-slate-100 p-8 rounded-3xl shadow-xl shadow-slate-100 animate-slide-up">
        <div className="text-center space-y-2">
          <Link to={AUTH_ROUTES.HOME} className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold shadow-md shadow-indigo-150">
              <Building className="w-5 h-5" />
            </div>
            <div className="text-left">
              <span className="font-extrabold text-slate-900 text-sm block tracking-tight">
                HomeBandhu
              </span>
              <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">
                Admin Portal
              </span>
            </div>
          </Link>

          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight pt-4">
            {title}
          </h1>
          {description && (
            <p className="text-xs font-semibold text-slate-400">{description}</p>
          )}
        </div>

        {children}
      </div>
    </div>
  );
}
