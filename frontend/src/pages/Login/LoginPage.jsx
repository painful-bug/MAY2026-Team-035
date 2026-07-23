import React, { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
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
  const adminDemoAccount = demoAuthAccounts.find(
    (account) => account.role === 'Admin'
  );

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

  const handleShortcutLogin = () => {
    if (!adminDemoAccount) return;
    const result = login(adminDemoAccount.phone);

    if (result.success) {
      navigate(AUTH_ROUTES.ADMIN_DASHBOARD);
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

      <button
        type="button"
        onClick={handleShortcutLogin}
        className="flex w-full flex-col items-center justify-center gap-1 rounded-xl border border-slate-150 bg-slate-50 p-3 text-slate-700 transition-all hover:bg-slate-100"
      >
        <span className="text-[10px] font-extrabold uppercase tracking-wide">
          Sign in as Demo Admin
        </span>
      </button>

      <p className="text-center text-[10px] font-semibold text-slate-400">
        Resident or society staff?{' '}
        <Link
          to={AUTH_ROUTES.RESIDENT_LOGIN}
          className="font-bold text-indigo-600 hover:underline"
        >
          Open Community Portal
        </Link>
      </p>
    </AuthCard>
  );
}
