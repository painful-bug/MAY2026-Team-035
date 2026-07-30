import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BellRing,
  Building2,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  Menu,
  QrCode,
  ShieldCheck,
  UserRoundCheck,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import { AUTH_ROUTES } from '../../routes/authRoutes';

const FEATURES = [
  {
    title: 'Visitor QR Passes',
    description:
      'Create secure group passes, review arrivals, and keep a complete visitor history.',
    icon: QrCode,
    tone: 'bg-indigo-50 text-indigo-600',
  },
  {
    title: 'Complaint Conversations',
    description:
      'Raise issues, message the assigned team, and follow every update until resolution.',
    icon: AlertTriangle,
    tone: 'bg-rose-50 text-rose-600',
  },
  {
    title: 'Amenity Booking',
    description:
      'Check availability and reserve community amenities for one or multiple days.',
    icon: CalendarDays,
    tone: 'bg-emerald-50 text-emerald-600',
  },
  {
    title: 'Maintenance Payments',
    description:
      'See the exact amount and due date, pay securely, and retain payment history.',
    icon: CreditCard,
    tone: 'bg-amber-50 text-amber-600',
  },
  {
    title: 'Community Notices',
    description:
      'Receive society announcements, service updates, and important safety information.',
    icon: BellRing,
    tone: 'bg-amber-50 text-amber-700',
  },
  {
    title: 'Role-based Access',
    description:
      'Residents and society staff see the tools permitted for their registered role.',
    icon: ShieldCheck,
    tone: 'bg-indigo-50 text-indigo-700',
  },
];

const ACCESS_TYPES = [
  {
    title: 'Residents',
    description:
      'Owners, tenants, and registered apartment members can access their home dashboard.',
    icon: Building2,
  },
  {
    title: 'Apartment Members',
    description:
      'Family members added by an existing resident can sign in using their own number.',
    icon: Users,
  },
  {
    title: 'Society Staff',
    description:
      'Security and operational staff use the same secure entry point with role-based access.',
    icon: Wrench,
  },
];

export default function ResidentLandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800">
      <header className="sticky top-0 z-50 border-b border-slate-100 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link
            to={AUTH_ROUTES.RESIDENT_LANDING}
            className="flex items-center gap-2.5"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-100">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <span className="block text-sm font-extrabold tracking-tight text-slate-900">
                HomeBandhu
              </span>
              <span className="block text-[9px] font-bold uppercase tracking-wider text-slate-400">
                Community Portal
              </span>
            </div>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            <a
              href="#features"
              className="text-sm font-semibold text-slate-600 hover:text-indigo-600"
            >
              Features
            </a>
            <a
              href="#access"
              className="text-sm font-semibold text-slate-600 hover:text-indigo-600"
            >
              Who can access
            </a>
            <a
              href="#help"
              className="text-sm font-semibold text-slate-600 hover:text-indigo-600"
            >
              Help
            </a>
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            <Link
              to={AUTH_ROUTES.LOGIN}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm shadow-indigo-100 hover:bg-indigo-700"
            >
              Sign In
            </Link>
          </div>

          <button
            type="button"
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-50 md:hidden"
            aria-label="Toggle navigation"
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="space-y-3 border-t border-slate-100 bg-white px-6 py-4 md:hidden">
            <a href="#features" className="block text-sm font-bold text-slate-600">
              Features
            </a>
            <a href="#access" className="block text-sm font-bold text-slate-600">
              Who can access
            </a>
            <Link
              to={AUTH_ROUTES.LOGIN}
              className="block rounded-xl bg-indigo-600 py-2.5 text-center text-sm font-bold text-white"
            >
              Sign In
            </Link>
          </div>
        )}
      </header>

      <main>
        <section className="relative overflow-hidden px-6 py-20 lg:py-28">
          <div className="absolute left-1/2 top-10 h-72 w-72 rounded-full bg-indigo-200/40 blur-3xl" />
          <div className="absolute right-16 top-40 h-64 w-64 rounded-full bg-amber-200/40 blur-3xl" />
          <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-12">
            <div className="space-y-6 text-center lg:col-span-6 lg:text-left">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-indigo-100 bg-indigo-50 px-3.5 py-1.5 text-xs font-bold text-indigo-700">
                <ShieldCheck className="h-3.5 w-3.5" />
                Secure access for your entire community
              </div>
              <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
                Your home, staff, and society{' '}
                <span className="text-indigo-600">connected simply.</span>
              </h1>
              <p className="mx-auto max-w-xl text-base font-medium leading-relaxed text-slate-500 lg:mx-0 lg:text-lg">
                One trusted portal for registered residents, apartment members,
                security teams, and society staff.
              </p>
              <div className="flex flex-col items-center justify-center gap-3 sm:flex-row lg:justify-start">
                <Link
                  to={AUTH_ROUTES.LOGIN}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-3.5 text-sm font-bold text-white shadow-md shadow-indigo-200 transition-all hover:-translate-y-0.5 hover:bg-indigo-700 sm:w-auto"
                >
                  Sign In to Community Portal
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <p className="text-xs font-semibold text-slate-400">
                  No self-registration required
                </p>
              </div>
            </div>

            <div className="relative lg:col-span-6">
              <div className="absolute -inset-3 rounded-3xl bg-gradient-to-r from-indigo-500 to-amber-400 opacity-15 blur-2xl" />
              <div className="relative rounded-3xl border border-slate-100 bg-white p-6 shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <p className="text-xs font-bold text-slate-700">
                      B-1204 · Resident Home
                    </p>
                  </div>
                  <span className="text-[10px] font-bold text-slate-400">
                    Today
                  </span>
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <PreviewStat
                    label="Maintenance due"
                    value="₹4,250"
                    helper="Due 15 Jul"
                  />
                  <PreviewStat
                    label="Upcoming bookings"
                    value="2"
                    helper="This week"
                    tone="emerald"
                  />
                </div>
                <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-extrabold text-slate-700">
                      Complaint update
                    </p>
                    <span className="rounded-full bg-blue-50 px-2 py-1 text-[9px] font-bold text-blue-700">
                      In Progress
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-bold text-slate-800">
                    Leaking tap in kitchen
                  </p>
                  <p className="mt-1 text-[10px] font-semibold text-slate-400">
                    Ramesh was assigned · New message from management
                  </p>
                </div>
                <div className="mt-4 flex items-center gap-3 rounded-2xl bg-indigo-600 p-4 text-white">
                  <QrCode className="h-8 w-8" />
                  <div>
                    <p className="text-xs font-extrabold">Visitor QR ready</p>
                    <p className="mt-0.5 text-[10px] font-semibold text-indigo-100">
                      One pass for your complete guest group
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          id="features"
          className="border-y border-slate-100 bg-white px-6 py-20"
        >
          <div className="mx-auto max-w-7xl">
            <div className="mx-auto max-w-2xl text-center">
              <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-indigo-700">
                Community essentials
              </span>
              <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900">
                Everything you need, without the paperwork
              </h2>
              <p className="mt-3 text-sm font-medium leading-relaxed text-slate-500">
                Clear workflows for daily home needs, gate operations, and
                communication with society management.
              </p>
            </div>
            <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-2xl border border-slate-100 bg-slate-50/50 p-5 transition-all hover:border-indigo-100 hover:bg-white hover:shadow-lg"
                >
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-xl ${feature.tone}`}
                  >
                    <feature.icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-sm font-extrabold text-slate-800">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="access" className="px-6 py-20">
          <div className="mx-auto max-w-5xl">
            <div className="text-center">
              <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">
                Who can sign in?
              </h2>
              <p className="mt-3 text-sm font-medium text-slate-500">
                Access is created by your society administrator or an existing
                apartment resident.
              </p>
            </div>
            <div className="mt-9 grid gap-4 md:grid-cols-3">
              {ACCESS_TYPES.map((accessType) => (
                <div
                  key={accessType.title}
                  className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
                >
                  <accessType.icon className="h-5 w-5 text-indigo-600" />
                  <h3 className="mt-4 text-sm font-extrabold text-slate-800">
                    {accessType.title}
                  </h3>
                  <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">
                    {accessType.description}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-2xl bg-slate-900 p-6 text-white sm:flex-row">
              <div className="flex items-start gap-3">
                <UserRoundCheck className="mt-0.5 h-5 w-5 text-indigo-300" />
                <div>
                  <p className="text-sm font-extrabold">Already registered?</p>
                  <p className="mt-1 text-xs font-semibold text-slate-400">
                    Use the mobile number connected to your resident or staff account.
                  </p>
                </div>
              </div>
              <Link
                to={AUTH_ROUTES.LOGIN}
                className="flex shrink-0 items-center gap-2 rounded-xl bg-white px-5 py-3 text-xs font-bold text-slate-900 hover:bg-indigo-50"
              >
                Continue to Sign In
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer id="help" className="border-t border-slate-800 bg-slate-900 px-6 py-10">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-extrabold text-white">HomeBandhu</p>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Contact your society office if your mobile number is not recognized.
            </p>
          </div>
          <div className="flex items-center gap-5 text-xs font-bold">
            <Link
              to={AUTH_ROUTES.LOGIN}
              className="text-indigo-300 hover:text-white"
            >
              Community Sign In
            </Link>
          </div>
        </div>
        <div className="mx-auto mt-7 flex max-w-7xl items-center gap-2 border-t border-slate-800 pt-6 text-[10px] font-semibold text-slate-500">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
          Sign-in is available only to accounts approved by the society.
        </div>
      </footer>
    </div>
  );
}

function PreviewStat({ label, value, helper, tone = 'indigo' }) {
  return (
    <div
      className={`rounded-2xl border p-4 ${
        tone === 'emerald'
          ? 'border-emerald-100 bg-emerald-50/50'
          : 'border-indigo-100 bg-indigo-50/50'
      }`}
    >
      <p
        className={`text-[9px] font-bold uppercase tracking-wider ${
          tone === 'emerald' ? 'text-emerald-600' : 'text-indigo-600'
        }`}
      >
        {label}
      </p>
      <p className="mt-1 text-lg font-extrabold text-slate-800">{value}</p>
      <p className="mt-1 text-[9px] font-semibold text-slate-400">{helper}</p>
    </div>
  );
}
