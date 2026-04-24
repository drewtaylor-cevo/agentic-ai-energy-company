import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRecommendations } from './useRecommendations';

// Canonical success payload — mirrors the DEMO-02 flagship numbers that the
// backend's simulate_savings pure function produces for CUST-001 (see
// tests/conftest.py:47-62 and ui/src/lib/mock/recommendations.ts:CUST-001).
// Used by API-mode tests where we stub `fetch` directly rather than read
// from MOCK_RECOMMENDATIONS.
const MOCK_SUCCESS = {
  green:    { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.0,  saving_annual: 360.0 },
  cheapest: { plan_id: 'VAL', plan_name: 'Value 12',    saving_monthly: 55.0,  saving_annual: 660.0 },
};

beforeEach(() => {
  // Reset both stubbed globals (fetch) and stubbed envs (VITE_API_URL)
  // between tests so branches don't leak between cases.
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('useRecommendations - API mode', () => {
  beforeEach(() => {
    // VITE_API_URL truthy -> real-fetch branch in the hook. Any URL string
    // works; the tests stub `fetch` itself so the URL is never resolved.
    vi.stubEnv('VITE_API_URL', 'https://api.example.com');
  });

  it('starts in idle state before any lookup is called', () => {
    const { result } = renderHook(() => useRecommendations());
    expect(result.current.state.status).toBe('idle');
  });

  it('returns success state on HTTP 200 with parsed data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(MOCK_SUCCESS), { status: 200 }))),
    );
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.customerId).toBe('CUST-001');
      expect(result.current.state.data.green.plan_id).toBe('ECO');
      expect(result.current.state.data.green.saving_monthly).toBe(30.0);
      expect(result.current.state.data.cheapest.plan_id).toBe('VAL');
      expect(result.current.state.data.cheapest.saving_monthly).toBe(55.0);
    }
  });

  it('builds the URL using encodeURIComponent on the path segment', async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify(MOCK_SUCCESS), { status: 200 })),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls[0]!;
    expect(firstCall[0]).toBe('https://api.example.com/recommendations/CUST-001');
  });

  it.each([
    [400],
    [404],
    [500],
    [502],
    [504],
  ])('HTTP %i maps to error state with matching httpStatus', async (httpStatus) => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('{"error":"x"}', { status: httpStatus }))),
    );
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(httpStatus);
      expect(result.current.state.customerId).toBe('CUST-001');
    }
  });

  it('does NOT parse JSON on non-200 responses (status-first parse)', async () => {
    // The body intentionally throws if json() is called — if the hook ever
    // tries to parse a 500 body this test will fail with the parse error
    // instead of reaching the status-code branch.
    const jsonThrows = vi.fn(() => Promise.reject(new Error('json() should not be called on non-2xx')));
    const fakeResponse = {
      ok: false,
      status: 500,
      json: jsonThrows,
    } as unknown as Response;
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(fakeResponse)));
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('error');
    expect(jsonThrows).not.toHaveBeenCalled();
  });

  it('network failure (TypeError) maps to error state with httpStatus 0', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))));
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(0);
      expect(result.current.state.customerId).toBe('CUST-001');
    }
  });

  it('normalizes raw input before submitting (lowercase + dashless -> canonical)', async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify(MOCK_SUCCESS), { status: 200 })),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('  cust001  ');
    });

    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.customerId).toBe('CUST-001');
    }
    const firstCall = fetchMock.mock.calls[0]!;
    expect(firstCall[0]).toBe('https://api.example.com/recommendations/CUST-001');
  });

  it('invalid ID (post-normalize) returns 400 without firing fetch', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('NOTVALID');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(400);
      expect(result.current.state.customerId).toBe('NOTVALID');
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rapid re-query aborts the in-flight request and only the second resolves', async () => {
    // First fetch never resolves unless the caller's signal fires — this lets
    // us assert that the second lookup pre-empts the first.
    let firstAborted = false;
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      const signal = init?.signal;
      if (signal?.aborted) {
        return Promise.reject(new DOMException('Aborted', 'AbortError'));
      }
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () => {
          firstAborted = true;
          reject(new DOMException('Aborted', 'AbortError'));
        });
      });
    });
    // Second call returns a real 200 with the mock payload.
    const secondFetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(MOCK_SUCCESS), { status: 200 })),
    );
    const combined = vi.fn()
      .mockImplementationOnce(fetchMock)
      .mockImplementationOnce(secondFetch);
    vi.stubGlobal('fetch', combined);

    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      // Fire the first lookup — it won't resolve on its own.
      void result.current.lookup('CUST-001');
      // Immediately fire a second lookup — should abort the first and resolve.
      await result.current.lookup('CUST-002');
    });

    // Aborted flag set by the first fetch's abort listener.
    expect(firstAborted).toBe(true);
    // The second lookup is the one that won — state reflects CUST-002 success.
    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.customerId).toBe('CUST-002');
    }
  });
});

describe('useRecommendations - mock fallback (VITE_API_URL unset)', () => {
  beforeEach(() => {
    // Empty string triggers the mock branch (hook checks `if (!apiUrl)`).
    vi.stubEnv('VITE_API_URL', '');
  });

  it('returns mock data for known persona CUST-001', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-001');
    });

    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.customerId).toBe('CUST-001');
      expect(result.current.state.data.green.plan_id).toBe('ECO');
      expect(result.current.state.data.green.plan_name).toBe('EcoFlex 100');
      expect(result.current.state.data.cheapest.plan_id).toBe('VAL');
      expect(result.current.state.data.cheapest.plan_name).toBe('Value 12');
    }
    // Mock mode must NOT hit the network.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('returns mock data for CUST-002 and CUST-003 (all seeded personas)', async () => {
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-002');
    });
    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.data.green.saving_monthly).toBe(16.9);
    }

    await act(async () => {
      await result.current.lookup('CUST-003');
    });
    expect(result.current.state.status).toBe('success');
    if (result.current.state.status === 'success') {
      expect(result.current.state.data.green.saving_monthly).toBe(14.0);
    }
  });

  it('returns 404 error for unknown ID in mock mode', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('CUST-999');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(404);
      expect(result.current.state.customerId).toBe('CUST-999');
    }
    // Mock-mode 404 must also not hit the network.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('rejects invalid ID with 400 without reading mock map', async () => {
    const { result } = renderHook(() => useRecommendations());

    await act(async () => {
      await result.current.lookup('NOTVALID');
    });

    expect(result.current.state.status).toBe('error');
    if (result.current.state.status === 'error') {
      expect(result.current.state.httpStatus).toBe(400);
    }
  });
});
