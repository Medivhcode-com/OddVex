import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';

/**
 * What a signed-in person has typed into a form and not yet saved, kept in memory only (never on disk).
 *
 * A form normally loses its fields when it leaves the screen, and that is unchanged. The one exception is a
 * session that ends without the person asking for it (the API answered 401 to a request that carried the
 * token): the forms are replaced by a log in prompt, so each field that was changed and not saved is kept here
 * until the same person logs in again and the form is drawn again. "Not saved" means different from the value
 * the field had when the form was drawn or, if the form has been saved since, when it was last saved: a form
 * tells this module about a successful save (`draftsSaved`). Logging out, deleting the account, a suspension
 * and a log in by a different account all discard everything. The session provider is the only caller of
 * `holdDrafts`, `releaseDrafts` and `dropDrafts`.
 */
const kept = new Map<string, unknown>();
let holding = false;

/** The session ended unexpectedly: forms that leave the screen from now on keep their changed fields. */
export function holdDrafts(): void {
  holding = true;
}

/** The same person is signed in again: forms take their fields back as they mount, and leaving a form drops them as before. */
export function releaseDrafts(): void {
  holding = false;
}

/** Forget everything. Nothing typed under one account is ever shown to another. */
export function dropDrafts(): void {
  holding = false;
  kept.clear();
}

/** Shown on a form whose fields came back after an unexpected sign-out. */
export const DRAFT_KEPT = 'You were signed out, so nothing was saved. What you entered is still here.';

// Fields hold plain data (text, switches, lists of legs), so comparing the JSON is enough.
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** A field on screen: the value it had when its form was drawn or last saved, and the value it has now. */
type Field = { id: string; saved: unknown; latest: unknown };
const onScreen = new Set<Field>();
/** The forms on screen that can show `DRAFT_KEPT`, with the way to stop showing it. */
const notices = new Set<{ form: string; dismiss: () => void }>();

/**
 * The API accepted what the form whose fields are keyed `<form>:<field>` sent. Call it in the success path,
 * after the form has reset whatever it resets. From here on the fields count as saved as they stand, so a later
 * sign-out keeps only what is changed after this. A copy kept because the form left the screen while the request
 * was still on its way is dropped, and a form that already took that copy back stops saying nothing was saved.
 */
export function draftsSaved(form: string): void {
  const prefix = `${form}:`;
  for (const field of onScreen) if (field.id.startsWith(prefix)) field.saved = field.latest;
  for (const key of [...kept.keys()]) if (key.startsWith(prefix)) kept.delete(key);
  for (const notice of [...notices]) if (notice.form === form) notice.dismiss();
}

/**
 * `useState` for a form field that must survive an unexpected sign-out. `key` names the field: it starts with
 * the form's own prefix and is read once, when the component mounts. A kept value is handed to the first form
 * that mounts with its key and is then removed from the store.
 */
export function useDraft<T>(key: string, initial: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const [id] = useState(key);
  const [start] = useState<T>(initial);
  const [value, setValue] = useState<T>(() => (kept.has(id) ? (kept.get(id) as T) : start));
  // A value that came back from the store is not saved: `saved` stays at the starting value.
  const field = useRef<Field>({ id, saved: start, latest: value });

  // The current value is tracked here as it is set, not after the next render, so that `draftsSaved` called
  // straight after a form resets its fields sees the reset values.
  const set = useCallback<Dispatch<SetStateAction<T>>>((next) => {
    const current = field.current;
    const resolved = typeof next === 'function' ? (next as (previous: T) => T)(current.latest as T) : next;
    current.latest = resolved;
    setValue(resolved);
  }, []);

  useEffect(() => {
    const current = field.current;
    kept.delete(id);
    onScreen.add(current);
    return () => {
      onScreen.delete(current);
      if (holding && !same(current.latest, current.saved)) kept.set(id, current.latest);
    };
  }, [id]);

  return [value, set];
}

/**
 * For the form whose fields are keyed `<form>:<field>` (read once, when the component mounts): whether it got
 * any of them back from a kept draft, a function that stops saying so (called when the form is submitted), and
 * a function to call when the API has accepted the form (`draftsSaved` for this form).
 */
export function useDraftKept(form: string): [kept: boolean, dismiss: () => void, saved: () => void] {
  const [name] = useState(form);
  const [shown, setShown] = useState(() => [...kept.keys()].some((key) => key.startsWith(`${name}:`)));
  const dismiss = useCallback(() => setShown(false), []);
  const saved = useCallback(() => draftsSaved(name), [name]);

  useEffect(() => {
    const notice = { form: name, dismiss };
    notices.add(notice);
    return () => {
      notices.delete(notice);
    };
  }, [name, dismiss]);

  return [shown, dismiss, saved];
}
