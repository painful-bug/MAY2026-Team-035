import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Link, Navigate } from 'react-router-dom';
import AuthCard from './AuthCard';
import { getAuthMethods, homeRouteFor } from '../../lib/auth/authService';
import { AUTH_FLOW_STATE, useAuthStore } from '../../store/authStore';
import { AUTH_ROUTES } from '../../routes/authRoutes';

export default function AuthEntryPage({ intent }) {
  const beginGoogleSignIn = useAuthStore((state) => state.beginGoogleSignIn);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const [methods, setMethods] = useState(null);
  const [error, setError] = useState('');
  const register = intent === 'register';

  useEffect(() => {
    let active = true;
    getAuthMethods()
      .then((config) => {
        if (active) setMethods(config);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Authentication is unavailable.');
      });
    return () => { active = false; };
  }, []);

  if (isAuthReady && sessionContext?.identity) {
    return <Navigate to={homeRouteFor(sessionContext)} replace />;
  }

  const redirecting = authFlowState === AUTH_FLOW_STATE.REDIRECTING;
  const next = register
    ? `${AUTH_ROUTES.AUTH_CALLBACK}?intent=register`
    : AUTH_ROUTES.AUTH_CALLBACK;

  return (
    <AuthCard
      title={register ? 'Create your HomeBandhu account' : 'Sign in to HomeBandhu'}
      description={register
        ? 'Continue with your verified Google account, then create or join a community.'
        : 'Use the verified Google account linked to your community.'}
    >
      <div className="space-y-4">
        {methods === null && !error ? (
          <div className="flex justify-center py-3"><Loader2 className="h-5 w-5 animate-spin text-indigo-600" /></div>
        ) : null}
        {methods?.methods?.map((method) => (
          method.id === 'google' ? (
            <button
              key={method.id}
              type="button"
              onClick={() => beginGoogleSignIn(next)}
              disabled={redirecting}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 shadow-sm transition-all hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60"
            >
              {redirecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <span className="text-base font-black text-[#4285F4]">G</span>}
              {redirecting ? 'Redirecting to Google…' : method.label}
            </button>
          ) : null
        ))}
        {error ? <p role="alert" className="text-center text-xs font-semibold text-rose-600">{error}</p> : null}
        <p className="text-center text-[11px] font-semibold text-slate-500">
          {register ? 'Already registered?' : 'New to HomeBandhu?'}{' '}
          <Link to={register ? AUTH_ROUTES.LOGIN : AUTH_ROUTES.REGISTER} className="font-bold text-indigo-600 hover:underline">
            {register ? 'Sign in' : 'Register'}
          </Link>
        </p>
        {!register ? (
          <p className="text-center text-[11px] font-semibold text-slate-500">
            Have an invitation? <Link to="/join" className="font-bold text-indigo-600 hover:underline">Activate it with Google</Link>
          </p>
        ) : null}
      </div>
    </AuthCard>
  );
}
