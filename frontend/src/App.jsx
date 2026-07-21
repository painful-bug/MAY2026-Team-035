import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './store/useApp';
import ToastContainer from './components/common/ToastContainer';

// Layouts
import ResidentLayout from './layouts/ResidentLayout';
import AdminLayout from './layouts/AdminLayout';

// Public Pages
import LandingPage from './pages/Landing/LandingPage';
import LoginPage from './pages/Login/LoginPage';
import OtpVerificationPage from './pages/OtpVerification/OtpVerificationPage';
import AssociationRegistrationPage from './pages/AssociationRegistration/AssociationRegistrationPage';
import MapConfigurationPage from './pages/MapConfiguration/MapConfigurationPage';
import FeatureConfigurationPage from './pages/FeatureConfiguration/FeatureConfigurationPage';
import AdminProfilePage from './pages/AdminProfile/AdminProfilePage';
import OnboardingOtpPage from './pages/OnboardingOtp/OnboardingOtpPage';
import OnboardingSuccessPage from './pages/OnboardingSuccess/OnboardingSuccessPage';
import SignupPage from './pages/Signup/SignupPage';
import JoinPage from './pages/Join/JoinPage';
import AuthFlowRoute from './routes/AuthFlowRoute';
import OnboardingFlowRoute from './routes/OnboardingFlowRoute';
import { AUTH_ROUTES } from './routes/authRoutes';
import { AUTH_FLOW_STATE } from './store/authStore';
import { ONBOARDING_STEPS } from './data/onboarding';

// Resident Pages
import ResidentHome from './pages/ResidentDashboard/DashboardHome';
import ResidentVisitors from './pages/ResidentDashboard/Visitors';
import ResidentComplaints from './pages/ResidentDashboard/Complaints';
import ResidentAmenities from './pages/ResidentDashboard/Amenities';
import ResidentPayments from './pages/ResidentDashboard/Payments';
import ResidentNotices from './pages/ResidentDashboard/Notices';
import ResidentProfile from './pages/ResidentDashboard/Profile';

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
import CreateDepartment from './pages/AdminDashboard/CreateDepartment';
import AmenityDetailLayout from './features/amenities/layouts/AmenityDetailLayout';
import AmenityDashboardPage from './features/amenities/pages/AmenityDashboardPage';
import AmenityApprovalsPage from './features/amenities/pages/AmenityApprovalsPage';
import AmenityLedgerPage from './features/amenities/pages/AmenityLedgerPage';
import AmenitySettingsPage from './features/amenities/pages/AmenitySettingsPage';

const AmenityReportsPage = lazy(() =>
  import('./features/amenities/pages/AmenityReportsPage')
);

// Protected Route Guard Simulation
function ProtectedRoute({ children, requiredRole }) {
  const { currentUser } = useApp();
  
  if (!currentUser) {
    // If not logged in, redirect to login page
    return <Navigate to={AUTH_ROUTES.LOGIN} replace />;
  }
  
  if (requiredRole && currentUser.role !== requiredRole) {
    // If user doesn't have the required role (e.g. resident tries to access admin)
    return <Navigate to={AUTH_ROUTES.RESIDENT_DASHBOARD} replace />;
  }
  
  return children;
}

export default function App() {
  return (
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path={AUTH_ROUTES.HOME} element={<LandingPage />} />
          <Route path={AUTH_ROUTES.LOGIN} element={<LoginPage />} />
          <Route
            path={AUTH_ROUTES.OTP_VERIFICATION}
            element={
              <AuthFlowRoute
                allowedStates={[
                  AUTH_FLOW_STATE.OTP_REQUIRED,
                  AUTH_FLOW_STATE.OTP_SUBMITTING,
                ]}
                authenticatedRedirect={AUTH_ROUTES.ADMIN_DASHBOARD}
              >
                <OtpVerificationPage />
              </AuthFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.ASSOCIATION_REGISTRATION}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.ASSOCIATION_DETAILS}
                previousRoute={AUTH_ROUTES.LOGIN}
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
            path={AUTH_ROUTES.ONBOARDING_OTP}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.ONBOARDING_OTP}
                previousRoute={AUTH_ROUTES.ADMIN_PROFILE}
              >
                <OnboardingOtpPage />
              </OnboardingFlowRoute>
            }
          />
          <Route
            path={AUTH_ROUTES.ONBOARDING_SUCCESS}
            element={
              <OnboardingFlowRoute
                minimumStep={ONBOARDING_STEPS.ONBOARDING_OTP}
                previousRoute={AUTH_ROUTES.ONBOARDING_OTP}
                requireCreatedAssociation
              >
                <OnboardingSuccessPage />
              </OnboardingFlowRoute>
            }
          />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/join/:token" element={<JoinPage />} />

          {/* Resident Dashboard Layout */}
          <Route 
            path={AUTH_ROUTES.RESIDENT_DASHBOARD}
            element={
              <ProtectedRoute>
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
            <Route path="profile" element={<ResidentProfile />} />
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
            <Route path="department/new" element={<CreateDepartment />} />
            <Route path="pending" element={<PendingRegistrations />} />
            <Route path="residents" element={<ResidentsTable />} />
            <Route path="admins" element={<AdminsList />} />
            <Route path="notices" element={<AdminNotices />} />
            <Route path="complaints" element={<AdminComplaints />} />
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
      </BrowserRouter>
  );
}
