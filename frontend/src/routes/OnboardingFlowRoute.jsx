import React from 'react';
import { Navigate } from 'react-router-dom';
import { AUTH_FLOW_STATE, useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { AUTH_ROUTES } from './authRoutes';

export default function OnboardingFlowRoute({
  minimumStep,
  previousRoute,
  requireCreatedAssociation = false,
  children,
}) {
  const currentPhone = useAuthStore((state) => state.currentPhone);
  const authFlowState = useAuthStore((state) => state.authFlowState);
  const currentUser = useAuthStore((state) => state.currentUser);
  const associationName = useOnboardingStore((state) => state.associationName);
  const onboardingStep = useOnboardingStore((state) => state.onboardingStep);
  const createdAssociation = useOnboardingStore(
    (state) => state.createdAssociation
  );

  const activeRegistrationFlow =
    Boolean(currentPhone) &&
    authFlowState === AUTH_FLOW_STATE.REGISTRATION_REQUIRED;
  const persistedOnboardingDraft =
    Boolean(associationName.trim()) && onboardingStep >= minimumStep;

  if (
    currentUser?.role === 'Admin' &&
    authFlowState === AUTH_FLOW_STATE.AUTHENTICATED
  ) {
    return <Navigate to={AUTH_ROUTES.ADMIN_DASHBOARD} replace />;
  }

  if (!activeRegistrationFlow && !persistedOnboardingDraft) {
    return <Navigate to={AUTH_ROUTES.LOGIN} replace />;
  }

  if (onboardingStep < minimumStep) {
    return <Navigate to={previousRoute} replace />;
  }

  if (requireCreatedAssociation && !createdAssociation) {
    return <Navigate to={previousRoute} replace />;
  }

  return children;
}
