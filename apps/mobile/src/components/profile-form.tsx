import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { ApiError, saveCommunityProfile } from '@/api/client';
import type { MyCommunityProfile, ProfileUpsert } from '@/api/types';
import { BIO_MAX, communityError, HANDLE_RULE, PROFILE_VISIBILITY, TEXT_RULES } from '@/components/community-copy';
import { Field, SwitchRow } from '@/components/form';
import { LimitedText, tooLong } from '@/components/limited-text';
import { Button, Notice } from '@/components/states';
import { Txt } from '@/components/text';
import { useSession } from '@/providers/session';
import { space } from '@/theme';

const HANDLE = /^[a-z0-9_]{3,20}$/;

/** Which field an API rejection is about, when the API says (`details.field`) or the code implies it. */
function fieldOf(error: unknown): 'handle' | 'bio' | null {
  if (!(error instanceof ApiError)) return null;
  if (['handle_taken', 'handle_reserved', 'invalid_handle'].includes(error.code)) return 'handle';
  const details = error.details;
  if (typeof details === 'object' && details !== null && 'field' in details) {
    if (details.field === 'handle') return 'handle';
    if (details.field === 'bio') return 'bio';
  }
  return null;
}

/**
 * Creates or edits the caller's community profile (`PUT /v1/community/profile`). Opt-in and private unless
 * the switch is turned on; the statement under the switch says exactly what a public profile shows.
 */
export function ProfileForm({ existing, onSaved }: { existing?: MyCommunityProfile | null; onSaved?: (profile: MyCommunityProfile) => void }) {
  const { changed } = useSession();
  const [handle, setHandle] = useState(existing?.handle ?? '');
  const [bio, setBio] = useState(existing?.bio ?? '');
  const [isPublic, setIsPublic] = useState(existing?.is_public ?? false);
  const [handleError, setHandleError] = useState<string | null>(null);
  const [bioError, setBioError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setSaved(false);
    setError(null);
    setBioError(null);
    if (!HANDLE.test(handle)) return setHandleError(`Enter a handle of ${HANDLE_RULE}`);
    setHandleError(null);
    if (tooLong(bio, BIO_MAX)) return;
    const body: ProfileUpsert = { handle, bio: bio.trim() || null, is_public: isPublic };
    setBusy(true);
    try {
      const profile = await saveCommunityProfile(body);
      setSaved(true);
      changed('community');
      onSaved?.(profile);
    } catch (caught) {
      const message = communityError(caught, 'Your profile was not saved. Try again.', 'profile');
      const field = fieldOf(caught);
      if (field === 'handle') setHandleError(message);
      else if (field === 'bio') setBioError(message);
      else setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <Field
        label="Handle"
        hint={`${HANDLE_RULE} This is the only name other people see.`}
        placeholder="your_handle"
        value={handle}
        onChangeText={(text) => setHandle(text.toLowerCase())}
        error={handleError}
        mono
      />
      <LimitedText label="Bio (optional)" value={bio} onChangeText={setBio} max={BIO_MAX} error={bioError} />
      <Txt variant="caption" tone="muted">
        {TEXT_RULES}
      </Txt>
      <SwitchRow label="Make my profile public" value={isPublic} onChange={setIsPublic} />
      <Txt variant="secondary" tone="muted">
        {PROFILE_VISIBILITY}
      </Txt>
      <Txt variant="secondary" tone="muted">
        {isPublic
          ? 'Public: you can post picks and comments and follow people, and other people can find your profile.'
          : "Private: you can browse, but you can't post picks or comments or follow people, and nobody can find your profile."}
      </Txt>
      {error ? <Notice tone="error" text={error} /> : null}
      {saved ? <Notice tone="accent" text="Profile saved." /> : null}
      <Button label={busy ? 'Saving profile' : existing ? 'Save profile' : 'Create profile'} onPress={submit} disabled={busy} />
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[3] },
});
