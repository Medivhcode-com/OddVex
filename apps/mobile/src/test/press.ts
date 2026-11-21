import type { TestInstance } from 'test-renderer';

type Fiber = { memoizedProps?: { onPress?: unknown }; return: Fiber | null };

/**
 * The nearest `onPress` above a rendered element, read from the tree. `fireEvent.press` lets React render between
 * two presses; calling this twice inside one `act` does not, which is what a fast double tap does on a phone.
 */
export function onPressOf(element: TestInstance): () => void {
  let fiber = (element as unknown as { unstable_fiber: Fiber | null }).unstable_fiber;
  while (fiber && typeof fiber.memoizedProps?.onPress !== 'function') fiber = fiber.return;
  if (!fiber) throw new Error('No onPress above this element');
  return fiber.memoizedProps?.onPress as () => void;
}
