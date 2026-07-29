import { useEffect, useRef, useState } from 'react';
import { Loader2, XCircle } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AuthCard from '../../components/auth/AuthCard';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { homeRouteFor } from '../../lib/auth/authService';
import { useAuthStore } from '../../store/authStore';

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const completeExternalLogin = useAuthStore((state) => state.completeExternalLogin);
  const ran = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    completeExternalLogin().then((result) => {
      if (result.success) navigate(homeRouteFor(result.user), { replace: true });
      else setError(result.message);
    });
  }, [completeExternalLogin, navigate]);

  return (
    <AuthCard title="Completing sign in" description="Verifying your HomeBandhu access">
      {error ? (
        <div className="space-y-4 text-center">
          <XCircle className="w-9 h-9 text-rose-600 mx-auto" />
          <p className="text-xs font-semibold text-rose-700">{error}</p>
          <Link to={AUTH_ROUTES.LOGIN} className="inline-flex w-full justify-center rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white">
            Back to sign in
          </Link>
        </div>
      ) : (
        <div className="space-y-3 text-center">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto" />
          <p className="text-xs font-semibold text-slate-500">Please wait…</p>
        </div>
      )}
    </AuthCard>
  );
}
