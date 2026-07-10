import React, { useState } from 'react';
import { ArrowLeft, LogIn, KeyRound } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { AUTH_FLOW_STATE, useAuthStore } from '../../store/authStore';
import { formatPhoneNumber } from '../../utils/phone';

export default function OtpVerificationPage() {
  const navigate = useNavigate();
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const submitAdminOtp = useAuthStore(
    (state) => state.submitAdminOtp
  );
  const resetAdminAuthentication = useAuthStore(
    (state) => state.resetAdminAuthentication
  );
  const [otp, setOtp] = useState('');
  const isSubmitting = authFlowState === AUTH_FLOW_STATE.OTP_SUBMITTING;

  const handleOtpChange = (event) => {
    setOtp(event.target.value.replace(/\D/g, '').slice(0, 6));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const result = await submitAdminOtp(otp);

    if (result.success) {
      navigate(AUTH_ROUTES.ADMIN_DASHBOARD, { replace: true });
    }
  };

  const handleChangeMobileNumber = () => {
    resetAdminAuthentication();
    navigate(AUTH_ROUTES.LOGIN, { replace: true });
  };

  return (
    <AuthCard
      title="OTP Verification"
      description={`Enter the OTP requested for ${formatPhoneNumber(currentPhone)}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label
            htmlFor="admin-otp"
            className="text-[11px] font-bold text-slate-500 uppercase tracking-wider"
          >
            Verification OTP Code
          </label>
          <div className="relative">
            <KeyRound className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="admin-otp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={otp}
              onChange={handleOtpChange}
              placeholder="Enter OTP code"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400 font-medium tracking-widest text-center"
            />
          </div>
          <p className="text-[10px] text-center text-slate-400 font-semibold pt-1">
            OTP verification is intentionally simulated in Task 1.
          </p>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
        >
          <LogIn className="w-4 h-4" />
          Submit
        </button>

        <button
          type="button"
          onClick={handleChangeMobileNumber}
          className="w-full text-[11px] font-bold text-slate-500 hover:text-indigo-600 flex items-center justify-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" />
          Change mobile number
        </button>
      </form>
    </AuthCard>
  );
}
