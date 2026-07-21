import React from 'react';

export default function SettingsSection({ title, description, children }) {
  return (
    <div className="space-y-4 border-t border-slate-100 pt-5 first:border-t-0 first:pt-0">
      <div>
        <h3 className="text-xs font-extrabold text-slate-700">{title}</h3>
        {description && (
          <p className="mt-1 text-[11px] font-medium leading-relaxed text-slate-400">
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
