import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './store/useApp';
import ToastContainer from './components/common/ToastContainer';
import ChatDock from './components/chat/ChatDock';
import DashboardDataBootstrap from './components/dashboard/DashboardDataBootstrap';

// Layouts
import ResidentLayout from './layouts/ResidentLayout';
import AdminLayout from './layouts/AdminLayout';
import SecurityLayout from './layouts/SecurityLayout';
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
import DepartmentHiring from './pages/AdminDashboard/DepartmentHiring';
import EmployeeDetail from './pages/AdminDashboard/EmployeeDetail';
import AdminMessages from './pages/AdminDashboard/Messages';
import JoinPage from './pages/Join/JoinPage';
import ResidentLandingPage from './pages/ResidentLanding/ResidentLandingPage';
import OnboardingFlowRoute from './routes/OnboardingFlowRoute';
import { AUTH_ROUTES, homeRouteFor } from './routes/authRoutes';
import { useAuthStore } from './store/authStore';
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
import WorkerHome from './pages/WorkerDashboard/Dashboard';
import WorkerCalendar from './pages/WorkerDashboard/Calendar';
import WorkerAvailability from './pages/WorkerDashboard/Availability';
import WorkerCommunities from './pages/WorkerDashboard/Communities';
import WorkerMessages from './pages/WorkerDashboard/Messages';
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

// Protected Route Guard Simulation
function ProtectedRoute({
  children,
  requiredRole,
  loginPath = AUTH_ROUTES.LOGIN,
}) {
  const { currentUser, isAuthReady } = useApp();

  if (!isAuthReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-semibold text-slate-400">
        Restoring your session…
      </div>
    );
  }
  
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
  const sessionContext = useAuthStore((state) => state.sessionContext);

  if (!isAuthReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-semibold text-slate-400">
        Restoring your session…
      </div>
    );
  }
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
        <DashboardDataBootstrap />
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
            <Route index element={<WorkerHome />} />
            <Route path="calendar" element={<WorkerCalendar />} />
            <Route path="availability" element={<WorkerAvailability />} />
            <Route path="communities" element={<WorkerCommunities />} />
            <Route path="messages" element={<WorkerMessages />} />
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
            <Route
              path="departments/:departmentId/hiring"
              element={<DepartmentHiring />}
            />
            {/* The employee page: roster tiles open it, and
                departure.requested notifications deep-link to it. */}
            <Route
              path="departments/:departmentId/staff/:staffId"
              element={<EmployeeDetail />}
            />
            {/* The URL 0041's department-side notification links to. */}
            <Route path="messages" element={<AdminMessages />} />
            <Route
              path="department/new"
              element={<Navigate to="/admin/departments?create=1" replace />}
            />
            <Route path="pending" element={<PendingRegistrations />} />
            <Route path="residents" element={<ResidentsTable />} />
            <Route path="admins" element={<AdminsList />} />
            <Route path="notices" element={<AdminNotices />} />
            <Route path="complaints" element={<AdminComplaints />} />
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
