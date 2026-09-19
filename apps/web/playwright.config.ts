import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// A fresh ephemeral SQLite path per test run - never the app's own
// `.dev-data/backend.db` default (CLAUDE.md: "Keep development activity off
// the app's real default data path"). Computed once here, at config-load
// time, and handed to the backend-api webServer below via `env`.
const e2eDbDir = fs.mkdtempSync(path.join(os.tmpdir(), 'towing-e2e-'));
const e2eDbPath = path.join(e2eDbDir, 'backend.db').replace(/\\/g, '/');
const backendDbUrl = `sqlite+aiosqlite:///${e2eDbPath}`;

const webDir = __dirname;
const backendDir = path.resolve(__dirname, '../backend');
const referenceApiDir = path.resolve(__dirname, '../../docs/design/web/api');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  projects: [
    {
      name: 'calculator',
      testMatch: /calculator\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:5174' },
    },
    {
      name: 'authenticated',
      testMatch: /auth-and-journey\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:5173' },
    },
  ],
  webServer: [
    {
      // The free calculator's own, pre-existing stateless reference backend
      // (docs/design/web/api) - not apps/backend. The calculator was never
      // rebuilt against apps/backend (issue #30: "keeping its already-built
      // anonymous calculator exactly as it is"), so proving its flow is
      // genuinely untouched means exercising it against the same kind of
      // backend it always talked to, not the new authenticated one.
      command: 'uv run uvicorn main:app --host 127.0.0.1 --port 8001',
      cwd: referenceApiDir,
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // The real apps/backend (issues #18-#21), pointed at a fresh ephemeral
      // SQLite DB. Launched via towing_backend.asgi:app (issue #35's fix),
      // never `towing_backend.app:create_app --factory ...` - that form
      // crashes on startup under this uvicorn version (a nested-event-loop
      // conflict between uvicorn's own loop and Alembic's migration path).
      command: 'uv run uvicorn towing_backend.asgi:app --host 127.0.0.1 --port 8000',
      cwd: backendDir,
      env: {
        TOWING_BACKEND_DB_URL: backendDbUrl,
        TOWING_BACKEND_CORS_ORIGIN: 'http://localhost:5173',
        TOWING_BACKEND_SECRET: 'e2e-test-secret-not-for-real-use',
      },
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx vite --port 5174 --strictPort',
      cwd: webDir,
      env: { VITE_API_BASE: 'http://localhost:8001' },
      url: 'http://localhost:5174',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx vite --port 5173 --strictPort',
      cwd: webDir,
      env: { VITE_API_BASE: 'http://localhost:8000' },
      url: 'http://localhost:5173',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
