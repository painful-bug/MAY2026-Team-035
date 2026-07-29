import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Building, Loader2 } from 'lucide-react';
import { homeRouteFor } from '../../lib/auth/authService';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useAuthStore } from '../../store/authStore';
import { isValidMobileNumber, normalizePhoneNumber } from '../../utils/phone';

// Invitation redemption stays server-side. The client never activates a local
// user record from an invite token.
export default function JoinPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const redeemInvite = useAuthStore((state) => state.redeemInvite);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const normalizedPhone = normalizePhoneNumber(phone);
    if (!isValidMobileNumber(normalizedPhone)) {
      setError('Enter the mobile number that received this invitation.');
      return;
    }

    setError('');
    setIsSubmitting(true);
    const result = await redeemInvite(token, `+91${normalizedPhone}`);
    setIsSubmitting(false);
    if (result.success) navigate(homeRouteFor(result.user), { replace: true });
    else setError(result.message);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12 font-sans">
      <div className="w-full max-w-md space-y-6 rounded-3xl border border-slate-100 bg-white p-8 text-center shadow-xl shadow-slate-100 animate-slide-up">
        <div className="inline-flex items-center justify-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white"><Building className="h-5 w-5" /></div>
          <span className="font-extrabold tracking-tight text-slate-900">HomeBandhu</span>
        </div>
        <div className="space-y-1">
          <h1 className="text-xl font-extrabold text-slate-900">Activate your invitation</h1>
          <p className="text-xs font-semibold text-slate-400">Confirm the invited mobile number. You can link Google from your profile after activation.</p>
        </div>
        {error && <p role="alert" className="rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs font-semibold text-rose-700">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-3 text-left">
          <label htmlFor="invite-phone" className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Invited mobile number</label>
          <input id="invite-phone" value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" autoComplete="tel" placeholder="98765 43210" className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500 focus:bg-white" />
          <button type="submit" disabled={isSubmitting} className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-wait disabled:bg-indigo-400">
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isSubmitting ? 'Activating…' : 'Activate invitation'}
          </button>
        </form>
        <Link to={AUTH_ROUTES.LOGIN} className="block text-xs font-bold text-indigo-600 hover:underline">Already have access? Sign in</Link>
      </div>
    </div>
  );
}
