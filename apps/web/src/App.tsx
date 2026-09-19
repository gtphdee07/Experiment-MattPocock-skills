import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import AuthedLayout from './components/AuthedLayout';
import { AppThemeProvider } from './theme/ThemeContext';
import Calculator from './pages/Calculator';
import Login from './pages/Login';
import Register from './pages/Register';
import GarageDashboard from './pages/GarageDashboard';
import WeighEventNew from './pages/WeighEventNew';
import WeighEventHistory from './pages/WeighEventHistory';
import NotFound from './pages/NotFound';

/** Route map (issue #30 Implementation Decisions: "exact path names are your
 * call, not grilled"):
 *  /                  - the free calculator, unauthenticated, untouched (Story 1)
 *  /login, /register  - Account auth (Story 2/4)
 *  /garage            - Garage dashboard, protected (Story 8/9/14)
 *  /weigh-events/new  - Weigh Event creation flow, protected (Story 16-24)
 *  /weigh-events      - Weigh Event history, protected (Story 27/28)
 * Everything else falls through to a "not found" page (Story 30) rather than
 * a broken route.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppThemeProvider>
          <Routes>
            <Route path="/" element={<Calculator />} />
            <Route element={<AuthedLayout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/garage"
                element={
                  <ProtectedRoute>
                    <GarageDashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/weigh-events/new"
                element={
                  <ProtectedRoute>
                    <WeighEventNew />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/weigh-events"
                element={
                  <ProtectedRoute>
                    <WeighEventHistory />
                  </ProtectedRoute>
                }
              />
              <Route path="/not-found" element={<NotFound />} />
              <Route path="*" element={<Navigate to="/not-found" replace />} />
            </Route>
          </Routes>
        </AppThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
