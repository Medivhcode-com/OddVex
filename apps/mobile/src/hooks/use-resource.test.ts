import { act, renderHook, waitFor } from '@testing-library/react-native';

import { useResource } from '@/hooks/use-resource';

describe('useResource', () => {
  it('goes from loading to ready', async () => {
    const { result } = await renderHook(() => useResource('a', async () => 'value'));
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toBe('value');
    expect(result.current.refreshing).toBe(false);
  });

  it('reports an error, then recovers on reload', async () => {
    const fetcher = jest.fn<Promise<string>, [AbortSignal]>().mockRejectedValueOnce(new Error('down')).mockResolvedValue('back');
    const { result } = await renderHook(() => useResource('a', fetcher));
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toEqual(new Error('down'));

    await act(async () => result.current.reload());
    await waitFor(() => expect(result.current.status).toBe('ready'));
    expect(result.current.data).toBe('back');
    expect(result.current.error).toBeUndefined();
  });

  it('keeps earlier data on screen when a refresh fails', async () => {
    const fetcher = jest.fn<Promise<string>, [AbortSignal]>().mockResolvedValueOnce('first').mockRejectedValue(new Error('down'));
    const { result } = await renderHook(() => useResource('a', fetcher));
    await waitFor(() => expect(result.current.data).toBe('first'));

    await act(async () => result.current.reload());
    await waitFor(() => expect(result.current.error).toBeDefined());
    expect(result.current.status).toBe('ready');
    expect(result.current.data).toBe('first');
    expect(result.current.refreshing).toBe(false);
  });

  it('drops the old data and a late answer when the key changes', async () => {
    let resolveSlow: (value: string) => void = () => {};
    const fetcher = (key: string) =>
      key === 'slow' ? new Promise<string>((resolve) => (resolveSlow = resolve)) : Promise.resolve(`data for ${key}`);
    const { result, rerender } = await renderHook(({ id }: { id: string }) => useResource(id, () => fetcher(id)), {
      initialProps: { id: 'slow' },
    });
    expect(result.current.status).toBe('loading');

    await rerender({ id: 'fast' });
    await waitFor(() => expect(result.current.data).toBe('data for fast'));

    await act(async () => resolveSlow('late answer'));
    expect(result.current.data).toBe('data for fast');
  });
});
