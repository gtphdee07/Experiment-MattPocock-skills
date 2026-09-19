import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createTruck, getMe, login, setUnauthorizedHandler } from './api';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? undefined : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('api fetch wrapper', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setUnauthorizedHandler(null);
    vi.restoreAllMocks();
  });

  it('sends credentials: include on every request', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(200, { id: 1, email: 'a@example.com', is_active: true, is_verified: true, is_superuser: false, created_at: 'now' })
    );
    await getMe();
    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.credentials).toBe('include');
  });

  it('sends login as form-encoded username/password, not JSON', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response(null, { status: 204 }));
    await login('a@example.com', 'hunter22');
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain('/auth/login');
    expect(init.headers['Content-Type']).toBe('application/x-www-form-urlencoded');
    expect(init.body).toBe('username=a%40example.com&password=hunter22');
  });

  it('calls the registered unauthorized handler and throws ApiError(401) on a 401', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response(null, { status: 401 }));
    const handler = vi.fn();
    setUnauthorizedHandler(handler);

    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('surfaces the parsed `detail` body on a non-2xx response', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(409, { detail: { reason: 'solo_link_unconfirmed' } })
    );
    try {
      await createTruck({ gvwr: 1, front_gawr: 1, rear_gawr: 1 });
      throw new Error('expected createTruck to reject');
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(409);
      expect((err as ApiError).detail).toEqual({ reason: 'solo_link_unconfirmed' });
    }
  });

  it('resolves to undefined for a 204 No Content response', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(new Response(null, { status: 204 }));
    await expect(login('a@example.com', 'pw')).resolves.toBeUndefined();
  });
});
