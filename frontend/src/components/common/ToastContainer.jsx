import React from 'react';
import { useApp } from '../../store/useApp';
import { CheckCircle2, AlertCircle, Info } from 'lucide-react';

export default function ToastContainer() {
  const toasts = useApp((state) => state.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-3 max-w-sm w-full px-4 sm:px-0">
      {toasts.map((toast) => {
        const isSuccess = toast.type === 'success';
        const isError = toast.type === 'error';
        const isInfo = toast.type === 'info';

        return (
          <div
            key={toast.id}
            className={`flex items-start p-4 rounded-2xl border shadow-lg backdrop-blur-md transition-all duration-300 animate-slide-up ${
              isSuccess
                ? 'bg-emerald-50/95 border-emerald-100 text-emerald-900 shadow-emerald-100/50'
                : isError
                ? 'bg-rose-50/95 border-rose-100 text-rose-900 shadow-rose-100/50'
                : 'bg-blue-50/95 border-blue-100 text-blue-900 shadow-blue-100/50'
            }`}
          >
            <div className="flex-shrink-0 mr-3 mt-0.5">
              {isSuccess && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
              {isError && <AlertCircle className="w-5 h-5 text-rose-600" />}
              {isInfo && <Info className="w-5 h-5 text-blue-600" />}
            </div>
            <div className="flex-1 text-sm font-semibold">{toast.message}</div>
          </div>
        );
      })}
    </div>
  );
}
