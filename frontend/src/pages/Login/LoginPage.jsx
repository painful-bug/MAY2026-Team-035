import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { Building, Phone, Key, LogIn, ArrowRight, ArrowLeft, Ticket } from 'lucide-react';

export default function LoginPage() {
  const { login, redeemInvite, setCurrentUser, showToast } = useApp();
  const navigate = useNavigate();
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [inviteMode, setInviteMode] = useState(false);
  const [inviteCode, setInviteCode] = useState('');
  const [error, setError] = useState('');

  // Route by role — admins land on /admin, everyone else on /resident.
  const goToDashboard = (user) => navigate(user.role === 'Admin' ? '/admin' : '/resident');

  const handleRequestOtp = (e) => {
    e.preventDefault();
    if (!phone) {
      setError('Please enter your phone number.');
      return;
    }
    const cleanPhone = phone.trim().replace(/\s+/g, '');
    if (cleanPhone.length < 10) {
      setError('Please enter a valid 10-digit phone number.');
      return;
    }
    setOtpSent(true);
    setError('');
    showToast('OTP sent successfully! Enter any 4-digit code (e.g. 1234)', 'success');
  };

  const handleSubmitLogin = (e) => {
    e.preventDefault();
    if (!otp) {
      setError('Please enter the OTP.');
      return;
    }
    if (otp.length < 4) {
      setError('OTP must be at least 4 digits.');
      return;
    }
    const result = login(phone, otp);
    if (result.success) {
      goToDashboard(result.user);
    } else {
      setError(result.message);
    }
  };

  const handleShortcutLogin = (role) => {
    const mockPhone = role === 'Admin' ? '+91 99999 88888' : '+91 98765 43210';
    const result = login(mockPhone, '1234');
    if (result.success) {
      goToDashboard(result.user);
    }
  };

  // Invite path (PRD "enter number + hash"): redeem the code, which activates the
  // flat and returns the member for this phone; then log them straight in.
  const handleRedeemCode = (e) => {
    e.preventDefault();
    if (!phone || !inviteCode.trim()) {
      setError('Enter your phone number and invite code.');
      return;
    }
    const res = redeemInvite(inviteCode.trim(), phone);
    if (res.ok && res.user) {
      setCurrentUser(res.user);
      goToDashboard(res.user);
    } else {
      setError(res.message || 'Invalid invite code.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-12 px-6 font-sans">
      <div className="max-w-md w-full space-y-8 bg-white border border-slate-100 p-8 rounded-3xl shadow-xl shadow-slate-100 animate-slide-up">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <Link to="/" className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold shadow-md shadow-indigo-150">
              <Building className="w-5 h-5" />
            </div>
            <div className="text-left">
              <span className="font-extrabold text-slate-900 text-sm block tracking-tight">HomeBandhu</span>
              <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Residency Portal</span>
            </div>
          </Link>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight pt-4">
            {inviteMode ? 'Join with an invite' : 'Sign in to your flat'}
          </h2>
          <p className="text-xs font-semibold text-slate-400">
            {inviteMode
              ? 'Enter your mobile number and the invite code shared by your admin'
              : 'Enter your registered mobile number to request an OTP'}
          </p>
        </div>

        {error && (
          <div className="bg-rose-50 border border-rose-100 text-rose-800 text-xs font-semibold p-3.5 rounded-xl text-center">
            {error}
          </div>
        )}

        {inviteMode ? (
          /* Invite Code Redemption */
          <form onSubmit={handleRedeemCode} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setError(''); }}
                  placeholder="e.g. 9876543210"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400 font-medium"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Invite Code</label>
              <div className="relative">
                <Ticket className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={inviteCode}
                  onChange={(e) => { setInviteCode(e.target.value); setError(''); }}
                  placeholder="Paste your invite code"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400 font-medium"
                />
              </div>
            </div>
            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
            >
              <LogIn className="w-4 h-4" />
              Join & Sign In
            </button>
            <button
              type="button"
              onClick={() => { setInviteMode(false); setError(''); }}
              className="w-full text-[11px] font-bold text-slate-500 hover:text-indigo-600 flex items-center justify-center gap-1"
            >
              <ArrowLeft className="w-3 h-3" /> Back to OTP sign in
            </button>
          </form>
        ) : !otpSent ? (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setError(''); }}
                  placeholder="e.g. 9876543210"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400 font-medium"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
            >
              Get OTP
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmitLogin} className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Verification OTP Code</label>
                <button
                  type="button"
                  onClick={() => setOtpSent(false)}
                  className="text-[11px] font-bold text-indigo-600 hover:underline flex items-center gap-1"
                >
                  <ArrowLeft className="w-3 h-3" /> Change Number
                </button>
              </div>
              <div className="relative">
                <Key className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => { setOtp(e.target.value.replace(/\D/g, '')); setError(''); }}
                  placeholder="Enter 4 or 6-digit OTP code"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400 font-medium tracking-widest text-center"
                />
              </div>
              <p className="text-[10px] text-center text-slate-400 font-semibold">Simulated OTP sent to {phone}</p>
            </div>

            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
            >
              <LogIn className="w-4 h-4" />
              Verify & Sign In
            </button>
          </form>
        )}

        {/* Divider */}
        <div className="relative flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-100" />
          </div>
          <span className="relative bg-white px-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            Demonstration Shortcuts
          </span>
        </div>

        {/* Shortcut Quick Logins */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => handleShortcutLogin('Resident')}
            className="flex flex-col items-center justify-center p-3 border border-slate-150 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 transition-all gap-1 group"
          >
            <span className="text-[10px] font-extrabold uppercase tracking-wide">As Resident</span>
          </button>

          <button
            type="button"
            onClick={() => handleShortcutLogin('Admin')}
            className="flex flex-col items-center justify-center p-3 border border-slate-150 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 transition-all gap-1 group"
          >
            <span className="text-[10px] font-extrabold uppercase tracking-wide">As Admin</span>
          </button>
        </div>

        {/* Invite + Signup links */}
        <div className="text-center pt-2 space-y-2">
          {!inviteMode && (
            <button
              type="button"
              onClick={() => { setInviteMode(true); setOtpSent(false); setError(''); }}
              className="text-xs font-bold text-indigo-600 hover:underline inline-flex items-center gap-1"
            >
              <Ticket className="w-3.5 h-3.5" /> Have an invite code?
            </button>
          )}
          <p className="text-xs font-semibold text-slate-455">
            New resident?{' '}
            <Link to="/signup" className="text-indigo-600 hover:underline font-bold inline-flex items-center gap-0.5">
              Request Portal Access
              <ArrowRight className="w-3 h-3" />
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
