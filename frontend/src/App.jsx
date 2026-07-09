import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './store/useApp';
import ToastContainer from './components/common/ToastContainer';

// Layouts
import ResidentLayout from './layouts/ResidentLayout';
import AdminLayout from './layouts/AdminLayout';

// Public Pages
import LandingPage from './pages/Landing/LandingPage';
import LoginPage from './pages/Login/LoginPage';
import SignupPage from './pages/Signup/SignupPage';
import JoinPage from './pages/Join/JoinPage';

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

// Protected Route Guard Simulation
function ProtectedRoute({ children, requiredRole }) {
  const { currentUser } = useApp();
  
  if (!currentUser) {
    // If not logged in, redirect to login page
    return <Navigate to="/login" replace />;
  }
  
  if (requiredRole && currentUser.role !== requiredRole) {
    // If user doesn't have the required role (e.g. resident tries to access admin)
    return <Navigate to="/resident" replace />;
  }
  
  return children;
}

export default function App() {
  return (
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/join/:token" element={<JoinPage />} />

          {/* Resident Dashboard Layout */}
          <Route 
            path="/resident" 
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
            path="/admin" 
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
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          {/* Fallback Redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        {/* Global Floating Toast Alert Messages */}
        <ToastContainer />
      </BrowserRouter>
  );
}
