import React, { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import PhoneNumberField from '../../components/auth/PhoneNumberField';
import { demoAuthAccounts } from '../../data/authentication';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import {
  AUTH_FLOW_STATE,
  useAuthStore,
} from '../../store/authStore';

export default function LoginPage() {
  const navigate = useNavigate();
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const setCurrentPhone = useAuthStore((state) => state.setCurrentPhone);
  const startAdminAuthentication = useAuthStore(
    (state) => state.startAdminAuthentication
  );
  const login = useAuthStore((state) => state.login);
  const [error, setError] = useState('');

  const isChecking = authFlowState === AUTH_FLOW_STATE.CHECKING_REGISTRATION;

  const handlePhoneChange = (event) => {
    setCurrentPhone(event.target.value);
    setError('');
  };

  const handleRequestOtp = async (event) => {
    event.preventDefault();
    setError('');

    const result = await startAdminAuthentication();

    if (!result.success) {
      setError(result.message);
      return;
    }

    navigate(
      result.isRegistered
        ? AUTH_ROUTES.OTP_VERIFICATION
        : AUTH_ROUTES.ASSOCIATION_REGISTRATION
    );
  };

  const handleShortcutLogin = (account) => {
    const result = login(account.phone);

    if (result.success) {
      navigate(
        account.role === 'Admin'
          ? AUTH_ROUTES.ADMIN_DASHBOARD
          : AUTH_ROUTES.RESIDENT_DASHBOARD
      );
    }
  };

  return (
    <AuthCard
      title="Admin Login"
      description="Enter your mobile number to continue as an association administrator"
    >
      {error && (
        <div
          role="alert"
          className="bg-rose-50 border border-rose-100 text-rose-800 text-xs font-semibold p-3.5 rounded-xl text-center"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleRequestOtp} className="space-y-4">
        <PhoneNumberField
          value={currentPhone}
          onChange={handlePhoneChange}
          disabled={isChecking}
        />

        <button
          type="submit"
          disabled={isChecking}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 disabled:cursor-wait text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
        >
          {isChecking ? 'Checking Number...' : 'Get OTP'}
          {!isChecking && <ArrowRight className="w-4 h-4" />}
        </button>
      </form>

      <div className="relative flex items-center justify-center">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-100" />
        </div>
        <span className="relative bg-white px-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
          Demonstration Shortcuts
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {demoAuthAccounts.map((account) => (
          <button
            key={account.role}
            type="button"
            onClick={() => handleShortcutLogin(account)}
            className="flex flex-col items-center justify-center p-3 border border-slate-150 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 transition-all gap-1"
          >
            <span className="text-[10px] font-extrabold uppercase tracking-wide">
              As {account.role}
            </span>
          </button>
        ))}
      </div>
    </AuthCard>
  );
}
