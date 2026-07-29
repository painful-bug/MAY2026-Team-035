import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { AUTH_ROUTES } from './authRoutes';
import { homeRouteFor } from '../lib/auth/authService';

export default function OnboardingFlowRoute({
  minimumStep,
  previousRoute,
  requireCreatedAssociation = false,
  children,
}) {
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const onboardingStep = useOnboardingStore((state) => state.onboardingStep);
  const createdAssociation = useOnboardingStore(
    (state) => state.createdAssociation
  );

  if (!isAuthReady) return null;
  if (!sessionContext?.identity) return <Navigate to={AUTH_ROUTES.REGISTER} replace />;
  if (sessionContext.membership || !sessionContext.onboarding_eligible) {
    return <Navigate to={homeRouteFor(sessionContext)} replace />;
  }

  if (onboardingStep < minimumStep) {
    return <Navigate to={previousRoute} replace />;
  }

  if (requireCreatedAssociation && !createdAssociation) {
    return <Navigate to={previousRoute} replace />;
  }

  return children;
}
