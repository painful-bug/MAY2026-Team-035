import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './store/useApp';
import ToastContainer from './components/common/ToastContainer';
import ChatDock from './components/chat/ChatDock';
import SessionRestorationState from './components/auth/SessionRestorationState';

// Layouts
import ResidentLayout from './layouts/ResidentLayout';
import AdminLayout from './layouts/AdminLayout';
import SecurityLayout from './layouts/SecurityLayout';
import ManagerLayout from './layouts/ManagerLayout';
import ManagerOverview from './pages/ManagerDashboard/Overview';
import ManagerComplaints from './pages/ManagerDashboard/Complaints';
import ManagerSkills from './pages/ManagerDashboard/Skills';
import ManagerTeam from './pages/ManagerDashboard/Team';
import WorkerLayout from './layouts/WorkerLayout';

// Public Pages
import LandingPage from './pages/Landing/LandingPage';
import LoginPage from './pages/Login/LoginPage';
import RegistrationPage from './pages/Registration/RegistrationPage';
import GetStartedPage from './pages/GetStarted/GetStartedPage';
import AuthCallbackPage from './pages/AuthCallback/AuthCallbackPage';
import EmailConfirmationPage from './pages/Auth/EmailConfirmationPage';
import PasswordRecoveryPage from './pages/Auth/PasswordRecoveryPage';
import AssociationRegistrationPage from './pages/AssociationRegistration/AssociationRegistrationPage';
import MapConfigurationPage from './pages/MapConfiguration/MapConfigurationPage';
import FeatureConfigurationPage from './pages/FeatureConfiguration/FeatureConfigurationPage';
import AdminProfilePage from './pages/AdminProfile/AdminProfilePage';
import OnboardingSuccessPage from './pages/OnboardingSuccess/OnboardingSuccessPage';
import OnboardingReviewPage from './pages/OnboardingReview/OnboardingReviewPage';
import AccountPage from './pages/Account/AccountPage';
import CandidateDetail from './pages/AdminDashboard/CandidateDetail';
import DepartmentHiring from './pages/AdminDashboard/DepartmentHiring';
import EmployeeDetail from './pages/AdminDashboard/EmployeeDetail';
import AdminMessages from './pages/AdminDashboard/Messages';
import WorkOrderTriage from './pages/AdminDashboard/WorkOrderTriage';
import JoinPage from './pages/Join/JoinPage';
import ResidentLandingPage from './pages/ResidentLanding/ResidentLandingPage';
import OnboardingFlowRoute from './routes/OnboardingFlowRoute';
import { AUTH_ROUTES, homeRouteFor } from './routes/authRoutes';
import { SESSION_STATUS, useAuthStore } from './store/authStore';
import { ONBOARDING_STEPS } from './data/onboarding';

// Resident Pages
import ResidentHome from './pages/ResidentDashboard/DashboardHome';
import ResidentVisitors from './pages/ResidentDashboard/Visitors';
import ResidentComplaints from './pages/ResidentDashboard/Complaints';
import ResidentAmenities from './pages/ResidentDashboard/Amenities';
import ResidentPayments from './pages/ResidentDashboard/Payments';
import ResidentNotices from './pages/ResidentDashboard/Notices';
import ResidentProfile from './pages/ResidentDashboard/Profile';
import ResidentFaq from './pages/ResidentDashboard/Faq';

// Admin Pages
import AdminHome from './pages/AdminDashboard/AdminHome';
import PendingRegistrations from './pages/AdminDashboard/PendingRegistrations';
import ResidentsTable from './pages/AdminDashboard/Residents';
import AdminsList from './pages/AdminDashboard/Admins';
import AdminNotices from './pages/AdminDashboard/Notices';
import AdminComplaints from './pages/AdminDashboard/Complaints';
import AdminComplaintTriage from './pages/AdminDashboard/ComplaintTriage';
import AdminMaintenance from './pages/AdminDashboard/Maintenance';
import AdminSettings from './pages/AdminDashboard/Settings';
import AdminAmenities from './pages/AdminDashboard/Amenities';
import AdminDepartments from './pages/AdminDashboard/Departments';
import AdminDepartmentDetail from './pages/AdminDashboard/DepartmentDetail';
import GateHome from './pages/SecurityDashboard/GateHome';
import SecurityRegisters from './pages/SecurityDashboard/Registers';
import SecurityIncidents from './pages/SecurityDashboard/Incidents';
import SecurityShifts from './pages/SecurityDashboard/Shifts';
import SecurityEmergency from './pages/SecurityDashboard/Emergency';
import SecurityOverview from './pages/SecurityManagerDashboard/Overview';
import SecurityRoster from './pages/SecurityManagerDashboard/Roster';
import ManagerIncidents from './pages/SecurityManagerDashboard/ManagerIncidents';
import SecurityExports from './pages/SecurityManagerDashboard/Exports';
import AdminSecurityIncidents from './pages/AdminDashboard/SecurityIncidents';

// Service Partner Pages
import WorkerLanding from './pages/WorkerDashboard/WorkerLanding';
import WorkerCalendar from './pages/WorkerDashboard/Calendar';
import WorkerAvailability from './pages/WorkerDashboard/Availability';
import WorkerCommunities from './pages/WorkerDashboard/Communities';
import WorkerMessages from './pages/WorkerDashboard/Messages';
import WorkerComplaints from './pages/WorkerDashboard/Complaints';
import WorkerCompletedWork from './pages/WorkerDashboard/CompletedWork';
import WorkerWorkOrders from './pages/WorkerDashboard/WorkOrders';
import WorkerProfile from './pages/WorkerDashboard/Profile';
import WorkerSettings from './pages/WorkerDashboard/Settings';

import AmenityDetailLayout from './features/amenities/layouts/AmenityDetailLayout';
import AmenityDashboardPage from './features/amenities/pages/AmenityDashboardPage';
import AmenityApprovalsPage from './features/amenities/pages/AmenityApprovalsPage';
import AmenityLedgerPage from './features/amenities/pages/AmenityLedgerPage';
import AmenitySettingsPage from './features/amenities/pages/AmenitySettingsPage';

const AmenityReportsPage = lazy(() =>
  import('./features/amenities/pages/AmenityReportsPage')
);

// The hiring sub-tree, mounted identically under three portal bases.
//
// **One fragment rather than three copies**, because the bug this closes is
// exactly what three copies produce. The endpoints have accepted `admin` or
// `manager` since `0035` — `require_admin_or_manager` at the router,
// `can_manage_department` inside every RPC — and until 2026-08-11 only `/admin`
// had screens, so a department manager and a security department's manager both
// held a permission with no way to use it (`docs/potential issues/14`).
//
// The paths keep the admin's shape under every base, including the
// `:departmentId` a manager could have had implied by their session. That is
// what lets `DepartmentHiring`, `EmployeeDetail` and `CandidateDetail` be one
// implementation each with no per-portal branch — and typing somebody else's
// department id is not a way in, because `can_manage_department` refuses it in
// Postgres.
//
// A React fragment inside <Route> children is flattened by the router, so these
// arrive as siblings of the routes around them.
const HIRING_ROUTES = (
  <>
    <Route
      path="departments/:departmentId/hiring"
      element={<DepartmentHiring />}
    />
    {/* The employee page: roster tiles open it, and departure.requested
        notifications deep-link to it. */}
    <Route
      path="departments/:departmentId/staff/:staffId"
      element={<EmployeeDetail />}
    />
    {/* The candidate page. Not the employee page and it cannot be: every way
        into it — a candidate tile, an application card, the
        `service_application_received` notification — is about somebody with no
        `staff_assignments` row, which is what that route reads. */}
    <Route
      path="departments/:departmentId/candidates/:providerId"
      element={<CandidateDetail />}
    />
    {/* The hiring conversation. The URL 0041's department-side notification
        links to, and where the candidate page's Message button lands. */}
    <Route path="messages" element={<AdminMessages />} />
  </>
);

// Work-order triage, mounted under the admin and the department-manager bases.
//
// **The same idiom as `HIRING_ROUTES` and for the same reason.** The eight
// endpoints behind this screen guard on `can_supervise_department` inside
// Postgres and admit every kind of staff at the router, so a department manager
// has always been allowed to call them — and had no screen. One fragment rather
// than a copy per portal is what keeps that from happening again the next time
// a base is added.
//
// The `:departmentId` stays in the path under every base, so the component has
// no per-portal branch. It is not a permission: `can_supervise_department`
// refuses somebody else's id in the database, which is the whole posture of
// `work_orders.py`.
const WORK_ORDER_ROUTES = (
  <Route
    path="departments/:departmentId/work-orders"
    element={<WorkOrderTriage />}
  />
);

// Protected Route Guard Simulation
function ProtectedRoute({
  children,
  requiredRole,
  loginPath = AUTH_ROUTES.LOGIN,
}) {
  const { currentUser, isAuthReady, sessionStatus } = useApp();

  if (!isAuthReady || sessionStatus === SESSION_STATUS.ERROR) return <SessionRestorationState />;
  
  if (!currentUser) {
    // If not logged in, redirect to login page
    return <Navigate to={loginPath} replace />;
  }
  
  const allowedRoles = Array.isArray(requiredRole)
    ? requiredRole
    : requiredRole
      ? [requiredRole]
      : [];

  if (allowedRoles.length && !allowedRoles.includes(currentUser.role)) {
    return <Navigate to={homeRouteFor(currentUser)} replace />;
  }
  
  return children;
}

// A signed-in identity is the whole guard, with no membership and no role.
//
// ProtectedRoute cannot express this: it reads `currentUser`, and
// `applicationUser()` returns null for anybody whose session carries no
// membership. That is precisely the service person who has registered and not
// yet been hired -- the population the worker portal's registration and
// community-search screens exist for. The same problem, and the same answer, as
// `require_service_provider` on the backend depending on `get_current_user`
// alone rather than on membership.
//
// What the portal then shows is decided by GET /worker/snapshot, whose null
// `provider` and empty `communities` are the two empty states.
function SignedInRoute({ children }) {
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const sessionStatus = useAuthStore((state) => state.sessionStatus);
  const sessionContext = useAuthStore((state) => state.sessionContext);

  if (!isAuthReady || sessionStatus === SESSION_STATUS.ERROR) return <SessionRestorationState />;
  if (!sessionContext?.identity) return <Navigate to={AUTH_ROUTES.LOGIN} replace />;
  return children;
}

function AuthSessionBootstrap() {
  const initializeAuth = useAuthStore((state) => state.initializeAuth);

  useEffect(() => {
    void initializeAuth();
  }, [initializeAuth]);

  return null;
}

export default function App() {
  return (
      <BrowserRouter>
        <AuthSessionBootstrap />
        <Routes>
          {/* Public Routes */}
          <Route path={AUTH_ROUTES.HOME} element={<LandingPage />} />
          <Route path={AUTH_ROUTES.LOGIN} element={<LoginPage />} />
          <Route path={AUTH_ROUTES.REGISTER} element={<RegistrationPage />} />
          <Route path={AUTH_ROUTES.AUTH_CALLBACK} element={<AuthCallbackPage />} />
          <Route path={AUTH_ROUTES.CONFIRM_EMAIL} element={<EmailConfirmationPage />} />
          <Route path={AUTH_ROUTES.FORGOT_PASSWORD} element={<PasswordRecoveryPage />} />
          <Route path={AUTH_ROUTES.RESET_PASSWORD} element={<PasswordRecoveryPage />} />
          <Route path={AUTH_ROUTES.GET_STARTED} element={<GetStartedPage />} />
          <Route
            path={AUTH_ROUTES.ACCOUNT}
            element={<ProtectedRoute><AccountPage /></ProtectedRoute>}
          />
          <Route
            path={AUTH_ROUTES.RESIDENT_LANDING}
            element={<ResidentLandingPage />}
          />
          <Route
            path={AUTH_ROUTES.ASSOCIATION_REGISTRATION}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.ASSOCIATION_DETAILS}
                previousRoute={`${AUTH_ROUTES.GET_STARTED}?tab=create`}
              >
                <AssociationRegistrationPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.MAP_CONFIGURATION}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.MAP_CONFIGURATION}
                previousRoute={AUTH_ROUTES.ASSOCIATION_REGISTRATION}
              >
                <MapConfigurationPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.FEATURE_CONFIGURATION}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.FEATURE_CONFIGURATION}
                previousRoute={AUTH_ROUTES.MAP_CONFIGURATION}
              >
                <FeatureConfigurationPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.ADMIN_PROFILE}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.ADMIN_PROFILE}
                previousRoute={AUTH_ROUTES.FEATURE_CONFIGURATION}
              >
                <AdminProfilePage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.ONBOARDING_REVIEW}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.REVIEW}
                previousRoute={AUTH_ROUTES.ADMIN_PROFILE}
              >
                <OnboardingReviewPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.ONBOARDING_SUCCESS}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.REVIEW}
                previousRoute={AUTH_ROUTES.ONBOARDING_REVIEW}
                requireCreatedAssociation
              >
                <OnboardingSuccessPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path="/signup"
            element={<Navigate to={AUTH_ROUTES.REGISTER} replace />}
          />
          <Route path="/join/:token" element={<JoinPage />} />
          <Route path="/join" element={<JoinPage />} />

          {/* Resident Dashboard Layout */}
          <Route 
            path={AUTH_ROUTES.RESIDENT_DASHBOARD}
            element={
              <ProtectedRoute
                requiredRole={['Resident', 'Admin']}
                loginPath={AUTH_ROUTES.LOGIN}
              >
                <ResidentLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<ResidentHome />} />
            <Route path="visitors" element={<ResidentVisitors />} />
            <Route path="complaints" element={<ResidentComplaints />} />
            <Route path="amenities" element={<ResidentAmenities />} />
            <Route path="payments" element={<ResidentPayments />} />
            <Route path="notices" element={<ResidentNotices />} />
            <Route path="faq" element={<ResidentFaq />} />
            <Route path="profile" element={<ResidentProfile />} />
          </Route>

          {/* Security Operations Dashboard.
              A security manager is admitted here as well as to their own
              portal. They hold a gate role — `/security-manager/gate` renders
              this folder's own pages — and two notifications address a guard's
              URL to somebody who may by then be ranked manager:
              `shift.scheduled` (`0040:893`) and `security_shift.assigned`
              (`0043:950`) both point at `/security/shifts`. Guarding this
              subtree on `Security` alone would bounce exactly those people to
              an overview screen that does not answer the notification. */}
          <Route
            path={AUTH_ROUTES.SECURITY_DASHBOARD}
            element={
              <ProtectedRoute
                requiredRole={['Security', 'SecurityManager']}
                loginPath={AUTH_ROUTES.LOGIN}
              >
                <SecurityLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<GateHome />} />
            <Route path="registers" element={<SecurityRegisters />} />
            <Route path="incidents" element={<SecurityIncidents />} />
            {/* The URL `0040`'s `shift.scheduled` notification links to. */}
            <Route path="shifts" element={<SecurityShifts />} />
            <Route path="emergency" element={<SecurityEmergency />} />
          </Route>

          {/* Security Department Manager Dashboard */}
          <Route
            path={AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD}
            element={
              <ProtectedRoute
                requiredRole="SecurityManager"
                loginPath={AUTH_ROUTES.LOGIN}
              >
                <SecurityLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<SecurityOverview />} />
            <Route path="roster" element={<SecurityRoster />} />
            <Route path="incidents" element={<ManagerIncidents />} />
            <Route path="exports" element={<SecurityExports />} />
            {/* A manager holds a gate role too, so the guard's own screens
                serve them unchanged rather than being duplicated. */}
            <Route path="gate" element={<GateHome />} />
            <Route path="registers" element={<SecurityRegisters />} />
            <Route path="emergency" element={<SecurityEmergency />} />
            {/* Hiring, mounted at the same shape as under /admin.
                Two different people reach this portal — a security
                department's *manager* (`membership_role = 'manager'`) and a
                senior guard (`'security'` with a manager/supervisor roster
                rank). Only the first may hire, so the nav entry is gated on
                `accessRole` in SecurityLayout. The routes are not: a guard who
                types the URL gets the screen's own error from a 403 the
                database returned, which is a truthful answer, and duplicating
                the role test here would be a second place for it to drift. */}
            {HIRING_ROUTES}
            {/* Work-order triage, on the reasoning one line up and with one
                difference worth stating. Hiring admits the senior guard to a
                screen they may not always act on, and pays one click and an
                explanation for it. Here there is no such gap:
                `can_supervise_department` is what every work-order RPC checks,
                and a supervisor satisfies it — so this surface is theirs to
                use rather than merely to look at. A security department is a
                department, and hiding its queue from one of two permitted
                roles is `docs/potential issues/14` a third time. */}
            {WORK_ORDER_ROUTES}
          </Route>

          {/* Department manager portal.
              New: `_portal_for` has returned `'manager'` for a non-security
              department's manager since the security work, and there was no
              route for it — that person landed on `/account`. Nothing minted a
              `manager` membership until `staff_provisioning`, so nobody had hit it yet. */}
          <Route
            path={AUTH_ROUTES.MANAGER_DASHBOARD}
            element={
              <ProtectedRoute requiredRole="Manager" loginPath={AUTH_ROUTES.LOGIN}>
                <ManagerLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<ManagerOverview />} />
            <Route path="skills" element={<ManagerSkills />} />
            <Route path="team" element={<ManagerTeam />} />
            {/* Where `complaint.raised` now lands for a manager. It used to
                point at `/admin/complaints`, which this portal has no route
                for, so the click redirected them home and looked like nothing
                happened. */}
            <Route path="complaints" element={<ManagerComplaints />} />
            {HIRING_ROUTES}
            {WORK_ORDER_ROUTES}
            {/* The one shape that is *not* the admin's, and it is here rather
                than in the fragment above because only this portal can answer
                it: a manager's session names their department, so
                `usePortalScope` fills the id in when the URL has not. An admin
                has no such default, which is why `/admin/work-orders` is not a
                route. */}
            <Route path="work-orders" element={<WorkOrderTriage />} />
          </Route>

          {/* Service Partner (worker) portal.
              Guarded by SignedInRoute, not ProtectedRoute — see its comment.
              A service person who has registered and not yet been hired holds
              no membership, so `currentUser` is null and ProtectedRoute would
              bounce them to /login: exactly the population these screens exist
              to serve. */}
          <Route
            path={AUTH_ROUTES.WORKER_DASHBOARD}
            element={
              <SignedInRoute>
                <WorkerLayout />
              </SignedInRoute>
            }
          >
            {/* Two landing pages behind one index, picked on the roster rank
                the worker snapshot already carries. A technician gets
                `WorkerHome` unchanged — their day, their offers, their
                calendar. Department leadership gets the triage dashboard,
                because a supervisor holds no jobs and the technician's landing
                page was showing them an empty calendar (product rulings,
                `docs/COMPLAINT_ENGINE_HANDOFF.md` §18). The fork itself is
                `WorkerLanding` and is four lines long; neither page knows
                about the other. */}
            <Route index element={<WorkerLanding />} />
            <Route path="calendar" element={<WorkerCalendar />} />
            <Route path="availability" element={<WorkerAvailability />} />
            <Route path="communities" element={<WorkerCommunities />} />
            <Route path="messages" element={<WorkerMessages />} />
            {/* The supervisor's department queue. Gated inside the page on the
                roster rank the worker snapshot already carries, because rank is
                not on the session and putting it there would mean editing the
                auth owner's file for a nav entry. */}
            <Route path="complaints" element={<WorkerComplaints />} />
            {/* The read-only archive of ended complaints (amendment 3, ruling
                B2). Gated inside the page on the same roster rank as the two
                routes around it. */}
            <Route path="completed" element={<WorkerCompletedWork />} />
            {/* Work-order triage, and this portal is the one it was always
                missing from.
                `WORK_ORDER_ROUTES` is mounted under `/admin`, `/manager` and
                `/security-manager`, and the comment at that last mount says why
                a supervisor belongs on this surface — "a supervisor satisfies
                `can_supervise_department`, so this surface is theirs to use
                rather than merely to look at" — while `/worker`, where every
                supervisor of a service department actually lands, had no route
                for it at all. That is `docs/potential issues/14` a fourth time,
                and the product ruling of 2026-08-21 closes it: the supervisor
                is the channel through whom the worker gets the job.
                Not the fragment itself, because the fragment mounts the screen
                bare and this portal has two things to resolve first — the rank,
                which is on the roster and not the session, and the department,
                which for a supervisor is the roster row's rather than the
                membership's. `WorkerWorkOrders` answers both and then renders
                the very same `WorkOrderTriage`. Two paths and one element: the
                bare one is what a nav item can link to before any snapshot has
                loaded, and it redirects onto the `:departmentId` shape every
                other portal uses. */}
            <Route path="work-orders" element={<WorkerWorkOrders />} />
            <Route
              path="departments/:departmentId/work-orders"
              element={<WorkerWorkOrders />}
            />
            <Route path="profile" element={<WorkerProfile />} />
            <Route path="settings" element={<WorkerSettings />} />
          </Route>

          {/* Admin Dashboard Layout */}
          <Route 
            path={AUTH_ROUTES.ADMIN_DASHBOARD}
            element={
              <ProtectedRoute requiredRole="Admin">
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AdminHome />} />
            <Route path="departments" element={<AdminDepartments />} />
            <Route
              path="departments/:departmentId"
              element={<AdminDepartmentDetail />}
            />
            {HIRING_ROUTES}
            {WORK_ORDER_ROUTES}
            <Route
              path="department/new"
              element={<Navigate to="/admin/departments?create=1" replace />}
            />
            <Route path="pending" element={<PendingRegistrations />} />
            <Route path="residents" element={<ResidentsTable />} />
            <Route path="admins" element={<AdminsList />} />
            <Route path="notices" element={<AdminNotices />} />
            <Route path="complaints" element={<AdminComplaints />} />
            {/* Complaints the routing rule in `complaint_department_routing` could not place. A page of
                its own rather than a panel on the screen above, because that
                one is a teammate's and asks a different question: theirs is
                "how is this complaint going", this is "whose is it". */}
            <Route path="complaint-triage" element={<AdminComplaintTriage />} />
            {/* The URL `0040` sends admins on a high or critical incident. */}
            <Route path="security/incidents" element={<AdminSecurityIncidents />} />
            <Route path="maintenance" element={<AdminMaintenance />} />
            <Route path="amenities" element={<AdminAmenities />} />
            <Route
              path="amenities/reports"
              element={
                <Suspense
                  fallback={
                    <div className="rounded-2xl border border-slate-100 bg-white px-6 py-16 text-center text-xs font-semibold text-slate-400">
                      Loading amenity reports...
                    </div>
                  }
                >
                  <AmenityReportsPage />
                </Suspense>
              }
            />
            <Route
              path="amenities/:amenityId"
              element={<AmenityDetailLayout />}
            >
              <Route index element={<AmenityDashboardPage />} />
              <Route path="approvals" element={<AmenityApprovalsPage />} />
              <Route path="ledger" element={<AmenityLedgerPage />} />
              <Route path="settings" element={<AmenitySettingsPage />} />
            </Route>
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          {/* Fallback Redirect */}
          <Route path="*" element={<Navigate to={AUTH_ROUTES.HOME} replace />} />
        </Routes>

        {/* Global Floating Toast Alert Messages */}
        <ToastContainer />

        {/* The chat dock — every portal, one mount (renders null signed out). */}
        <ChatDock />
      </BrowserRouter>
  );
}
