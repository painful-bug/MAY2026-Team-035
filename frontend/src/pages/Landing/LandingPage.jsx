import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  Building, 
  Users, 
  CreditCard, 
  ShieldCheck, 
  Calendar, 
  AlertTriangle, 
  Megaphone, 
  HeartHandshake,
  ArrowRight,
  CheckCircle,
  Menu,
  X
} from 'lucide-react';

export default function LandingPage() {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const features = [
    {
      title: 'Visitor Management',
      desc: 'Pre-approve guests, delivery agents, and service providers with quick security entry codes.',
      icon: Users,
      color: 'text-indigo-600 bg-indigo-50'
    },
    {
      title: 'Complaint Management',
      desc: 'Raise maintenance complaints directly from the app, track live progress, and review resolutions.',
      icon: AlertTriangle,
      color: 'text-rose-600 bg-rose-50'
    },
    {
      title: 'Maintenance Payments',
      desc: 'View maintenance invoices, pay securely online, and track payment history instantly.',
      icon: CreditCard,
      color: 'text-emerald-600 bg-emerald-50'
    },
    {
      title: 'Notice Board',
      desc: 'Never miss important society updates. View high-priority alerts and celebrations in real-time.',
      icon: Megaphone,
      color: 'text-amber-600 bg-amber-50'
    },
    {
      title: 'Amenities Booking',
      desc: 'Reserve swimming pool, gym slots, tennis court, or the banquet hall directly through the calendar.',
      icon: Calendar,
      color: 'text-teal-600 bg-teal-50'
    },
    {
      title: 'Resident Directory',
      desc: 'Find emergency contacts, security gate phone numbers, and interact securely within the community.',
      icon: HeartHandshake,
      color: 'text-sky-600 bg-sky-50'
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* Navbar */}
      <header className="bg-white/80 backdrop-blur-md sticky top-0 z-50 border-b border-slate-100/80">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold shadow-md shadow-indigo-150">
              <Building className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-slate-900 text-sm block tracking-tight"> HomeBandhu</span>
              <span className="text-[10px] text-slate-400 font-bold block uppercase tracking-wider">Residency</span>
            </div>
          </div>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-8">
            <a href="#home" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 transition-colors">Home</a>
            <a href="#features" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 transition-colors">Features</a>
            <a href="#about" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 transition-colors">About Us</a>
            <a href="#contact" className="text-sm font-semibold text-slate-600 hover:text-indigo-600 transition-colors">Contact</a>
          </nav>

          {/* CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <Link to="/login" className="px-4 py-2 text-sm font-bold text-slate-650 hover:text-indigo-600 transition-colors">
              Log In
            </Link>
            <Link to="/signup" className="px-4.5 py-2.5 text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-all shadow-sm shadow-indigo-100">
              Register
            </Link>
          </div>

          {/* Mobile Menu Toggle */}
          <button 
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-slate-600 hover:bg-slate-50 rounded-lg md:hidden transition-colors"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Menu Dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white border-b border-slate-100 px-6 py-4 space-y-4 animate-slide-up">
            <a 
              href="#home" 
              onClick={() => setMobileMenuOpen(false)}
              className="block text-sm font-bold text-slate-600 hover:text-indigo-600"
            >
              Home
            </a>
            <a 
              href="#features" 
              onClick={() => setMobileMenuOpen(false)}
              className="block text-sm font-bold text-slate-600 hover:text-indigo-600"
            >
              Features
            </a>
            <a 
              href="#about" 
              onClick={() => setMobileMenuOpen(false)}
              className="block text-sm font-bold text-slate-600 hover:text-indigo-600"
            >
              About Us
            </a>
            <a 
              href="#contact" 
              onClick={() => setMobileMenuOpen(false)}
              className="block text-sm font-bold text-slate-600 hover:text-indigo-600"
            >
              Contact
            </a>
            <hr className="border-slate-100" />
            <div className="flex flex-col gap-2">
              <Link 
                to="/login" 
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 text-sm font-bold text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-xl"
              >
                Log In
              </Link>
              <Link 
                to="/signup" 
                onClick={() => setMobileMenuOpen(false)}
                className="w-full text-center py-2.5 text-sm font-bold bg-indigo-600 text-white hover:bg-indigo-700 rounded-xl shadow-sm"
              >
                Register
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Hero Section */}
      <section id="home" className="py-20 lg:py-28 px-6 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-12 items-center flex-1">
        <div className="lg:col-span-6 space-y-6 text-center lg:text-left">
          <div className="inline-flex items-center gap-1.5 bg-indigo-50 border border-indigo-100 text-indigo-750 px-3.5 py-1.5 rounded-full text-xs font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            Safe & Smart Gated Community App
          </div>
          
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.1]">
             HomeBandhu <span className="text-indigo-600">Made Simple</span>
          </h1>
          
          <p className="text-base sm:text-lg text-slate-500 max-w-xl mx-auto lg:mx-0 leading-relaxed font-medium">
            HomeBandhu Residency features an all-in-one portal designed for seamless visitor check-ins, transparent complaint tracking, instant maintenance payouts, and smart amenity reservations.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4">
            <Link 
              to="/login" 
              className="w-full sm:w-auto px-6 py-3.5 text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-indigo-200 hover:-translate-y-0.5"
            >
              Sign In to Portal
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link 
              to="/signup" 
              className="w-full sm:w-auto px-6 py-3.5 text-sm font-bold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-xl flex items-center justify-center transition-all hover:-translate-y-0.5"
            >
              Register Flat
            </Link>
          </div>
        </div>

        {/* Mockup Dashboard Preview */}
        <div className="lg:col-span-6 relative">
          <div className="absolute -inset-1 rounded-3xl bg-gradient-to-r from-indigo-500 to-sky-500 opacity-20 blur-2xl z-0" />
          <div className="relative bg-white border border-slate-100 rounded-2xl shadow-2xl p-6 space-y-6 z-10">
            {/* Header Mockup */}
            <div className="flex justify-between items-center pb-4 border-b border-slate-50">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-bold text-slate-650">B-1204 • Owner Dashboard</span>
              </div>
              <span className="text-xs font-bold text-slate-400">HomeBandhu App</span>
            </div>

            {/* Content Mockup */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-indigo-50/50 border border-indigo-100/30 p-4 rounded-xl space-y-1">
                <span className="text-[10px] uppercase font-bold text-indigo-500 tracking-wider">Maintenance</span>
                <p className="text-lg font-extrabold text-slate-800">₹4,250</p>
                <span className="text-[10px] font-bold text-slate-450 block">Due in 9 days</span>
              </div>
              <div className="bg-rose-50/50 border border-rose-100/30 p-4 rounded-xl space-y-1">
                <span className="text-[10px] uppercase font-bold text-rose-500 tracking-wider">Active Complaints</span>
                <p className="text-lg font-extrabold text-slate-800">2 Issues</p>
                <span className="text-[10px] font-bold text-slate-450 block">1 in progress</span>
              </div>
            </div>

            {/* Timeline Mockup */}
            <div className="space-y-3">
              <span className="text-xs font-bold text-slate-650">Recent Notice</span>
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 flex items-start gap-3">
                <span className="w-2 h-2 mt-1.5 rounded-full bg-rose-500" />
                <div>
                  <p className="text-xs font-bold text-slate-800">Water tank cleaning scheduled</p>
                  <p className="text-[10px] text-slate-450 font-semibold mt-0.5">Water supply interrupted from 10am to 4pm.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-white border-t border-b border-slate-100/80 px-6">
        <div className="max-w-7xl mx-auto w-full space-y-12">
          <div className="text-center space-y-3 max-w-2xl mx-auto">
            <span className="text-xs font-bold uppercase text-indigo-650 tracking-widest bg-indigo-50 border border-indigo-100/50 px-3 py-1 rounded-full">Portal Highlights</span>
            <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Everything You Need In One Dashboard</h2>
            <p className="text-slate-500 font-medium text-sm sm:text-base leading-relaxed">
              Designed carefully to keep communication clear, operations secure, and facility bookings simple for all ages.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feat) => (
              <div key={feat.title} className="p-6 border border-slate-100 hover:border-indigo-100 bg-slate-50/50 hover:bg-white rounded-2xl transition-all group hover:shadow-xl hover:shadow-indigo-50/20">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 transition-transform group-hover:scale-110 ${feat.color}`}>
                  <feat.icon className="w-5 h-5" />
                </div>
                <h3 className="font-extrabold text-slate-800 mb-2">{feat.title}</h3>
                <p className="text-xs font-medium text-slate-450 leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="py-20 px-6 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 space-y-6">
            <span className="text-xs font-bold uppercase text-indigo-650 tracking-widest bg-indigo-50 border border-indigo-100/50 px-3 py-1 rounded-full">Why Choose Us</span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">Elegance and transparency in Gated Living</h2>
            <p className="text-slate-500 font-medium text-sm sm:text-base leading-relaxed">
              HomeBandhu Residency has always prioritized resident safety, comfort, and state-of-the-art facilities. Our customized management app eliminates paperwork and brings security approvals to your mobile screen.
            </p>
            
            <div className="space-y-3.5">
              {[
                'Instant visitor notification alerts',
                'Live technician assignment for repairs',
                'Transparent financial auditing and payment history',
                'Seamless booking of common areas'
              ].map((bullet) => (
                <div key={bullet} className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <span className="text-xs sm:text-sm font-semibold text-slate-700">{bullet}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-6 bg-indigo-900/5 border border-indigo-100 rounded-3xl p-8 space-y-6">
            <h3 className="text-xl font-bold text-slate-850">Quick Resident Statistics</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white p-4.5 rounded-2xl shadow-sm border border-slate-100/50 text-center">
                <p className="text-3xl font-extrabold text-indigo-600">300+</p>
                <p className="text-xs font-bold text-slate-400 mt-1 uppercase">Happy Flats</p>
              </div>
              <div className="bg-white p-4.5 rounded-2xl shadow-sm border border-slate-100/50 text-center">
                <p className="text-3xl font-extrabold text-indigo-600">99.8%</p>
                <p className="text-xs font-bold text-slate-400 mt-1 uppercase">Safe Gate Entries</p>
              </div>
              <div className="bg-white p-4.5 rounded-2xl shadow-sm border border-slate-100/50 text-center">
                <p className="text-3xl font-extrabold text-indigo-600">12 mins</p>
                <p className="text-xs font-bold text-slate-400 mt-1 uppercase">Avg. Complaint Resolution</p>
              </div>
              <div className="bg-white p-4.5 rounded-2xl shadow-sm border border-slate-100/50 text-center">
                <p className="text-3xl font-extrabold text-indigo-600">24/7</p>
                <p className="text-xs font-bold text-slate-400 mt-1 uppercase">Staff Support</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer id="contact" className="bg-slate-900 text-slate-400 border-t border-slate-800 py-12 px-6">
        <div className="max-w-7xl mx-auto w-full grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-500 text-white flex items-center justify-center font-bold">
                <Building className="w-4 h-4" />
              </div>
              <span className="font-extrabold text-white text-sm"> HomeBandhu</span>
            </div>
            <p className="text-xs text-slate-450 leading-relaxed font-medium">
              Elegance, security, and convenience at your fingertips. Live smart.
            </p>
          </div>

          <div>
            <h4 className="text-white text-xs font-bold uppercase tracking-wider mb-4">Quick Links</h4>
            <ul className="space-y-2.5 text-xs font-semibold">
              <li><a href="#home" className="hover:text-white transition-colors">Home</a></li>
              <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
              <li><a href="#about" className="hover:text-white transition-colors">About Us</a></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white text-xs font-bold uppercase tracking-wider mb-4">Resident Portal</h4>
            <ul className="space-y-2.5 text-xs font-semibold">
              <li><Link to="/login" className="hover:text-white transition-colors">Sign In</Link></li>
              <li><Link to="/signup" className="hover:text-white transition-colors">Request Registration</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white text-xs font-bold uppercase tracking-wider mb-4">Contact Info</h4>
            <address className="not-italic space-y-2.5 text-xs font-semibold">
              <p>HomeBandhu Residency, Gate 1</p>
              <p>Sector 12, Gachibowli, Hyderabad</p>
              <p className="text-indigo-400">support@HomeBandhu.com</p>
            </address>
          </div>
        </div>

        <div className="max-w-7xl mx-auto w-full border-t border-slate-800 mt-8 pt-6 text-center text-[11px] font-semibold text-slate-500">
          © {new Date().getFullYear()} HomeBandhu Residency Association. All rights reserved.
        </div>
      </footer>
    </div>
  );
}
