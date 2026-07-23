import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { Building, XCircle, Loader2 } from 'lucide-react';
import { AUTH_ROUTES } from '../../routes/authRoutes';

// Magic-link landing: /join/:token. Redeems the invite (activating the flat),
// logs the resident in, and forwards to their dashboard. A single-use token, so
// the redeem runs exactly once — the ref guards against StrictMode's double
// effect invocation, which would otherwise "spend" the token on the first run
// and report it already-used on the second.
export default function JoinPage() {
  const { token } = useParams();
  const { redeemInvite, setCurrentUser } = useApp();
  const navigate = useNavigate();
  const ran = useRef(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const res = redeemInvite(token);
    if (res.ok && res.user) {
      setCurrentUser(res.user);
      navigate(AUTH_ROUTES.RESIDENT_DASHBOARD, { replace: true });
    } else {
      setMessage(res.message || 'This invite link is not valid.');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-12 px-6 font-sans">
      <div className="max-w-md w-full bg-white border border-slate-100 p-8 rounded-3xl shadow-xl shadow-slate-100 text-center space-y-6 animate-slide-up">
        <div className="inline-flex items-center gap-2 justify-center">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center">
            <Building className="w-5 h-5" />
          </div>
          <span className="font-extrabold text-slate-900 tracking-tight">HomeBandhu</span>
        </div>

        {!message ? (
          <div className="space-y-3">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin mx-auto" />
            <p className="text-sm font-semibold text-slate-500">Verifying your invite…</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="w-14 h-14 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto">
              <XCircle className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">Invite not valid</h2>
              <p className="text-xs font-semibold text-slate-400">{message}</p>
            </div>
            <Link
              to={AUTH_ROUTES.RESIDENT_LOGIN}
              className="inline-block w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl transition-all shadow-md shadow-indigo-100"
            >
              Go to Sign In
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
