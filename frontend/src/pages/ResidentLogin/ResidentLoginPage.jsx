import React, { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  KeyRound,
  LogIn,
  ShieldCheck,
  TicketCheck,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import PhoneNumberField from '../../components/auth/PhoneNumberField';
import {
  AUTH_ROUTES,
  getDashboardRouteForRole,
} from '../../routes/authRoutes';
import { useAppStore } from '../../store/appStore';
import { useAuthStore } from '../../store/authStore';
import {
  formatPhoneNumber,
  isValidMobileNumber,
  normalizePhoneNumber,
  sanitizePhoneInput,
} from '../../utils/phone';
import { findSecurityCommunityAccount } from '../../lib/securityAccounts';

export default function ResidentLoginPage() {
  const navigate = useNavigate();
  const users = useAppStore((state) => state.users);
  const departments = useAppStore((state) => state.departments);
  const redeemInvite = useAppStore((state) => state.redeemInvite);
  const login = useAuthStore((state) => state.login);
  const setCurrentUser = useAuthStore((state) => state.setCurrentUser);
  const [step, setStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [registrationCode, setRegistrationCode] = useState('');
  const [matchedAccount, setMatchedAccount] = useState(null);
  const [error, setError] = useState('');

  const handlePhoneChange = (event) => {
    setPhone(sanitizePhoneInput(event.target.value));
    setError('');
  };

  const handleRequestOtp = (event) => {
    event.preventDefault();
    setError('');
    const cleanPhone = normalizePhoneNumber(phone);

    if (!isValidMobileNumber(cleanPhone)) {
      setError('Please enter a valid 10-digit mobile number.');
      return;
    }

    const user = users.find(
      (item) => normalizePhoneNumber(item.phone) === cleanPhone
    );
    const account =
      user || findSecurityCommunityAccount(departments, cleanPhone);

    if (!account) {
      setError(
        'This number is not registered. Ask your society admin or apartment member to add it.'
      );
      return;
    }

    if (account.role === 'Admin') {
      setError('Administrator accounts must use the Admin Portal.');
      return;
    }

    if (account.status !== 'Active') {
      setError(
        account.status === 'Invited'
          ? 'Your account is awaiting activation. Use the registration code option below.'
          : 'This account is currently inactive. Contact your society office.'
      );
      return;
    }

    setMatchedAccount(account);
    setStep('otp');
  };

  const handleVerifyOtp = (event) => {
    event.preventDefault();
    setError('');

    if (otp.length !== 6) {
      setError('Enter the 6-digit OTP sent to your mobile number.');
      return;
    }

    if (!matchedAccount || matchedAccount.role === 'Admin') {
      setError('Unable to verify this community account. Please start again.');
      return;
    }

    const result = login(phone);
    if (!result.success || result.user?.role === 'Admin') {
      setError(result.message || 'Unable to sign in. Please try again.');
      return;
    }

    navigate(getDashboardRouteForRole(result.user.role), { replace: true });
  };

  const resetPhone = () => {
    setStep('phone');
    setMatchedAccount(null);
    setOtp('');
    setError('');
  };

  const handleRegistrationCode = (event) => {
    event.preventDefault();
    setError('');
    const rawCode = registrationCode.trim();
    const token = rawCode.includes('/join/')
      ? rawCode.split('/join/').pop().split(/[?#]/)[0]
      : rawCode;

    if (!token) {
      setError('Enter the registration code shared by your society admin.');
      return;
    }

    const result = redeemInvite(token);
    if (!result.ok || !result.user) {
      setError(result.message || 'This registration code is not valid.');
      return;
    }

    setCurrentUser(result.user);
    navigate(AUTH_ROUTES.RESIDENT_DASHBOARD, { replace: true });
  };

  const openRegistrationCode = () => {
    setStep('code');
    setError('');
    setRegistrationCode('');
  };

  const openPhoneSignIn = () => {
    setStep('phone');
    setError('');
    setRegistrationCode('');
  };

  return (
    <AuthCard
      title={
        step === 'phone'
          ? 'Community Sign In'
          : step === 'otp'
            ? 'Verify Your Number'
            : 'Activate Your Account'
      }
      description={
        step === 'phone'
          ? 'For registered residents, apartment members, security, and society staff'
          : step === 'otp'
            ? `Enter the OTP requested for ${formatPhoneNumber(phone)}`
            : 'Use the one-time registration code shared by your society admin'
      }
      homePath={AUTH_ROUTES.RESIDENT_LANDING}
      portalLabel="Community Portal"
    >
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-rose-100 bg-rose-50 p-3.5 text-center text-xs font-semibold text-rose-800"
        >
          {error}
        </div>
      )}

      {step === 'phone' && (
        <>
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <PhoneNumberField
              id="community-phone"
              value={phone}
              onChange={handlePhoneChange}
            />
            <button
              type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700"
            >
              Get OTP
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <div className="relative flex items-center justify-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-100" />
            </div>
            <span className="relative bg-white px-4 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              First-time activation
            </span>
          </div>

          <button
            type="button"
            onClick={openRegistrationCode}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-xs font-bold text-indigo-700 transition-colors hover:bg-indigo-100"
          >
            <TicketCheck className="h-4 w-4" />
            Sign In with Registration Code
          </button>
        </>
      )}

      {step === 'otp' && (
        <form onSubmit={handleVerifyOtp} className="space-y-4">
          <div className="space-y-1">
            <label
              htmlFor="community-otp"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              Verification OTP
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="community-otp"
                autoFocus
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={otp}
                onChange={(event) => {
                  setOtp(event.target.value.replace(/\D/g, '').slice(0, 6));
                  setError('');
                }}
                placeholder="Enter 6-digit OTP"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 text-center text-sm font-medium tracking-[0.3em] text-slate-700 placeholder:tracking-normal placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
              />
            </div>
            <p className="pt-1 text-center text-[10px] font-semibold text-slate-400">
              OTP delivery is simulated; enter any six digits.
            </p>
          </div>
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700"
          >
            <LogIn className="h-4 w-4" />
            Verify and Sign In
          </button>
          <button
            type="button"
            onClick={resetPhone}
            className="flex w-full items-center justify-center gap-1 text-[11px] font-bold text-slate-500 hover:text-indigo-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Change mobile number
          </button>
        </form>
      )}

      {step === 'code' && (
        <form onSubmit={handleRegistrationCode} className="space-y-4">
          <div className="space-y-1">
            <label
              htmlFor="registration-code"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-500"
            >
              Registration Code
            </label>
            <div className="relative">
              <TicketCheck className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="registration-code"
                autoFocus
                value={registrationCode}
                onChange={(event) => {
                  setRegistrationCode(event.target.value);
                  setError('');
                }}
                placeholder="Paste your invite code"
                autoComplete="one-time-code"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 font-mono text-xs font-semibold text-slate-700 placeholder:font-sans placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
              />
            </div>
            <p className="pt-1 text-[10px] font-semibold leading-relaxed text-slate-400">
              You can paste either the registration code or the complete invite link.
            </p>
          </div>
          <button
            type="submit"
            disabled={!registrationCode.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <LogIn className="h-4 w-4" />
            Activate and Sign In
          </button>
          <button
            type="button"
            onClick={openPhoneSignIn}
            className="flex w-full items-center justify-center gap-1 text-[11px] font-bold text-slate-500 hover:text-indigo-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to mobile sign in
          </button>
        </form>
      )}

      <div className="rounded-xl border border-slate-100 bg-slate-50 p-3.5">
        <div className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
          <p className="text-[10px] font-semibold leading-relaxed text-slate-500">
            There is no public registration. Access is available only after an
            admin or existing apartment member adds your number. New residents
            can activate their account using the shared registration code.
          </p>
        </div>
      </div>
    </AuthCard>
  );
}
