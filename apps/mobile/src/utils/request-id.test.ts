import { CLIENT_REQUEST_ID, newClientRequestId } from '@/utils/request-id';

describe('newClientRequestId', () => {
  const original = globalThis.crypto;
  afterEach(() => {
    Object.defineProperty(globalThis, 'crypto', { value: original, configurable: true, writable: true });
  });

  it('makes an id the API accepts, different every time', () => {
    const ids = new Set(Array.from({ length: 50 }, () => newClientRequestId()));
    expect(ids.size).toBe(50);
    for (const id of ids) expect(id).toMatch(CLIENT_REQUEST_ID);
  });

  it('still makes one where the platform has no randomUUID', () => {
    Object.defineProperty(globalThis, 'crypto', { value: undefined, configurable: true, writable: true });
    const a = newClientRequestId();
    const b = newClientRequestId();
    expect(a).toMatch(CLIENT_REQUEST_ID);
    expect(b).toMatch(CLIENT_REQUEST_ID);
    expect(a).not.toBe(b);
  });
});
