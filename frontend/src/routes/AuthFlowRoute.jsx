import React from 'react';
import { Navigate } from 'react-router-dom';
import { AUTH_FLOW_STATE, useAuthStore } from '../store/authStore';
import { AUTH_ROUTES } from './authRoutes';

export default function AuthFlowRoute({
  allowedStates,
  authenticatedRedirect,
  children,
}) {
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const currentUser = useAuthStore((state) => state.currentUser);

  if (
    authenticatedRedirect &&
    currentUser &&
    authFlowState === AUTH_FLOW_STATE.AUTHENTICATED
  ) {
    return <Navigate to={authenticatedRedirect} replace />;
  }

  if (!currentPhone || !allowedStates.includes(authFlowState)) {
    return <Navigate to={AUTH_ROUTES.LOGIN} replace />;
  }

  return children;
}
