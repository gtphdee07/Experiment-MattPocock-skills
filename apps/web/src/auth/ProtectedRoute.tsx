import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

/** Guards a Garage/Weigh-Event route: while the initial session check is in
 * flight, renders nothing (avoids a login-page flash for an already-signed-in
 * visitor); once resolved, either renders `children` or redirects to
 * `/login`, remembering where the visitor was headed (issue #30 Story 8). */
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { account } = useAuth();
  const location = useLocation();

  if (account === undefined) return null;
  if (account === null) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
