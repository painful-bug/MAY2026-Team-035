import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { Building, User, Mail, Phone, Lock, ClipboardCheck, ArrowLeft, ArrowRight } from 'lucide-react';

export default function SignupPage() {
  const { addPendingRequest } = useApp();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [tower, setTower] = useState('A');
  const [flatNumber, setFlatNumber] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Validations
    if (!fullName || !email || !mobile || !flatNumber || !password || !confirmPassword) {
      setError('Please fill in all fields.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    // Submit request
    addPendingRequest({
      fullName,
      email,
      mobile,
      tower,
      flatNumber,
      password
    });

    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center py-12 px-6 font-sans">
        <div className="max-w-md w-full bg-white border border-slate-100 p-8 rounded-3xl shadow-xl shadow-slate-100 text-center space-y-6 animate-slide-up">
          <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
            <ClipboardCheck className="w-8 h-8" />
          </div>
          
          <div className="space-y-2">
            <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Request Submitted!</h2>
            <p className="text-sm font-semibold text-emerald-600 bg-emerald-50 py-1.5 px-3 rounded-full inline-block">
              Registration Request Submitted Successfully.
            </p>
            <p className="text-xs text-slate-400 font-semibold px-4 pt-2">
              Your request is awaiting admin approval. You will be able to log in once the building administrator approves your profile.
            </p>
          </div>

          <div className="bg-slate-50 border border-slate-100 rounded-2xl p-4 text-left space-y-2 text-xs">
            <p className="font-bold text-slate-500 uppercase tracking-wider text-[10px]">Submitted Details</p>
            <div className="grid grid-cols-2 gap-2 text-slate-700 font-semibold">
              <div>Name: <span className="text-slate-900">{fullName}</span></div>
              <div>Flat: <span className="text-slate-900">{tower}-{flatNumber}</span></div>
              <div>Email: <span className="text-slate-900">{email}</span></div>
              <div>Phone: <span className="text-slate-900">{mobile}</span></div>
            </div>
          </div>

          <div className="pt-2">
            <Link
              to="/login"
              className="w-full bg-indigo-650 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
            >
              Back to Sign In
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center py-12 px-6 font-sans">
      <div className="max-w-lg w-full bg-white border border-slate-100 p-8 rounded-3xl shadow-xl shadow-slate-100 space-y-8 animate-slide-up">
        {/* Brand Header */}
        <div className="flex justify-between items-center">
          <Link to="/" className="inline-flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold">
              <Building className="w-4.5 h-4.5" />
            </div>
            <span className="font-extrabold text-slate-800 text-sm">HomeBandhu</span>
          </Link>
          <Link to="/login" className="text-xs font-bold text-indigo-650 hover:underline inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Sign In
          </Link>
        </div>

        <div className="space-y-1">
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Request Portal Access</h2>
          <p className="text-xs font-semibold text-slate-400">Submit your flat ownership details for admin verification</p>
        </div>

        {error && (
          <div className="bg-rose-50 border border-rose-100 text-rose-800 text-xs font-semibold p-3.5 rounded-xl text-center">
            {error}
          </div>
        )}

        {/* Signup Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="john.doe@gmail.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1 sm:col-span-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Mobile Number</label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>
            </div>

            <div className="space-y-1 sm:col-span-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Apartment Block</label>
              <select
                value={tower}
                onChange={(e) => setTower(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-semibold"
              >
                <option value="A">Tower A</option>
                <option value="B">Tower B</option>
                <option value="C">Tower C</option>
                <option value="D">Tower D</option>
              </select>
            </div>

            <div className="space-y-1 sm:col-span-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Flat Number</label>
              <input
                type="text"
                value={flatNumber}
                onChange={(e) => setFlatNumber(e.target.value)}
                placeholder="e.g. 1204"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Confirm Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium"
                />
              </div>
            </div>
          </div>

          <div className="pt-4">
            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-100"
            >
              Request Registration
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
