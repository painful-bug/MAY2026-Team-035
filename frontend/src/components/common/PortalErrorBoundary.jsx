import React from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';

// The portal shells' render-error fence. Before it existed, any uncaught render
// error in a routed page — an unguarded `.map` over a payload the snapshot 500
// made undefined, a hook used without its import — unmounted the entire React
// tree to a bare background, chrome included (`/admin/departments?create=1`,
// 2026-08-12). React removes the whole tree above the nearest boundary, so the
// fence sits where the chrome ends and the page begins: each layout wraps its
// `<Outlet />`, keeping the sidebar, header and navigation alive while only the
// failed page shows the panel.
//
// Recovery is remounting, twice over:
// * "Try again" bumps a key, throwing away the crashed subtree's state and
//   rendering it fresh — right for transient causes (a payload that has since
//   refetched).
// * Navigating anywhere resets the boundary (`key={location.pathname}` on the
//   class below), because the sidebar stays usable and a crash on one page must
//   never follow the user to the next.

class RenderErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false, attempt: 0 };
    this.retry = this.retry.bind(this);
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  retry() {
    this.setState((state) => ({ failed: false, attempt: state.attempt + 1 }));
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-6 py-12 text-center">
          <AlertTriangle className="mx-auto h-6 w-6 text-rose-400" />
          <p className="mt-3 text-xs font-bold text-rose-700">
            Something went wrong here.
          </p>
          <p className="mx-auto mt-1 max-w-sm text-[11px] font-semibold leading-relaxed text-rose-400">
            This page hit an unexpected error. The rest of the app is fine — try
            again, or use the menu to go somewhere else.
          </p>
          <button
            type="button"
            onClick={this.retry}
            className="mt-4 rounded-xl border border-rose-100 bg-white px-4 py-2 text-xs font-bold text-rose-700 transition-colors hover:bg-rose-50"
          >
            Try again
          </button>
        </div>
      );
    }
    // The key makes "Try again" a true remount rather than a re-render of a
    // subtree still holding the state that crashed it.
    return (
      <React.Fragment key={this.state.attempt}>
        {this.props.children}
      </React.Fragment>
    );
  }
}

export default function PortalErrorBoundary({ children }) {
  const location = useLocation();
  return (
    <RenderErrorBoundary key={location.pathname}>
      {children}
    </RenderErrorBoundary>
  );
}

// The Suspense fallback every portal layout shows in its content area while
// its `<Outlet />` route — now a `lazy()` chunk — is still loading. Small and
// chrome-less on purpose: the sidebar, header and nav around it never
// unmount, so this is the only thing that should visibly change.
export function PortalRouteFallback() {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white px-6 py-16 text-center text-xs font-semibold text-slate-400">
      Loading...
    </div>
  );
}
