import { useState } from 'react';
import { ArrowRight, Loader2, Smartphone } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import PhoneNumberField from '../../components/auth/PhoneNumberField';
import { AUTH_PROVIDER, authConfiguration, availableAuthProviders } from '../../lib/auth/config';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { AUTH_FLOW_STATE, useAuthStore } from '../../store/authStore';

function Divider({ children }) {
  return (
    <div className="relative flex items-center justify-center">
      <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-100" /></div>
      <span className="relative bg-white px-4 text-[10px] font-bold uppercase tracking-widest text-slate-400">{children}</span>
    </div>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const setCurrentPhone = useAuthStore((state) => state.setCurrentPhone);
  const beginProviderSignIn = useAuthStore((state) => state.beginProviderSignIn);
  const requestPhoneOtp = useAuthStore((state) => state.requestPhoneOtp);
  const [error, setError] = useState('');

  const providers = availableAuthProviders();
  const googleIsPrimary = authConfiguration.primaryProvider === AUTH_PROVIDER.GOOGLE;
  const showGoogle = providers.includes(AUTH_PROVIDER.GOOGLE);
  const showOtp = providers.includes(AUTH_PROVIDER.OTP);
  const isRedirecting = authFlowState === AUTH_FLOW_STATE.REDIRECTING;
  const isRequestingOtp = authFlowState === AUTH_FLOW_STATE.OTP_SUBMITTING;

  const handleGoogleSignIn = async () => {
    setError('');
    const result = await beginProviderSignIn(AUTH_PROVIDER.GOOGLE);
    if (!result.success) setError(result.message);
  };

  const handleRequestOtp = async (event) => {
    event.preventDefault();
    setError('');
    const result = await requestPhoneOtp();
    if (!result.success) {
      setError(result.message);
      return;
    }
    navigate(AUTH_ROUTES.OTP_VERIFICATION);
  };

  return (
    <AuthCard
      title="Sign in to HomeBandhu"
      description="Use your approved Google account or phone number to access your community"
    >
      {error && <div role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-3.5 text-center text-xs font-semibold text-rose-800">{error}</div>}

      {showGoogle && googleIsPrimary && (
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isRedirecting || isRequestingOtp}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 shadow-sm transition-all hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60"
        >
          {isRedirecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="text-base font-black text-[#4285F4]">G</span>}
          {isRedirecting ? 'Redirecting to Google…' : 'Continue with Google'}
        </button>
      )}

      {showOtp && googleIsPrimary && <Divider>or use phone OTP</Divider>}

      {showOtp && (
        <form onSubmit={handleRequestOtp} className="space-y-4">
          <PhoneNumberField value={currentPhone} onChange={(event) => { setCurrentPhone(event.target.value); setError(''); }} disabled={isRequestingOtp || isRedirecting} />
          <button
            type="submit"
            disabled={isRequestingOtp || isRedirecting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-wait disabled:bg-indigo-400"
          >
            {isRequestingOtp ? <Loader2 className="h-4 w-4 animate-spin" /> : <Smartphone className="h-4 w-4" />}
            {isRequestingOtp ? 'Sending code…' : 'Send OTP'}
            {!isRequestingOtp && <ArrowRight className="h-4 w-4" />}
          </button>
        </form>
      )}

      {showGoogle && !googleIsPrimary && (
        <>
          <Divider>or</Divider>
          <button type="button" onClick={handleGoogleSignIn} disabled={isRedirecting || isRequestingOtp} className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 shadow-sm transition-all hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60">
            <span className="text-base font-black text-[#4285F4]">G</span>
            Continue with Google
          </button>
        </>
      )}
      <p className="text-center text-[10px] font-semibold text-slate-400">
        Resident or society staff?{' '}
        <Link to={AUTH_ROUTES.RESIDENT_LOGIN} className="font-bold text-indigo-600 hover:underline">
          Open Community Portal
        </Link>
      </p>
    </AuthCard>
  );
}
