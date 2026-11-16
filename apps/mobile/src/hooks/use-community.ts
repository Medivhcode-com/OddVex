import { getMyCommunityProfile } from '@/api/client';
import type { MyCommunityProfile } from '@/api/types';
import { useResource, type Resource } from '@/hooks/use-resource';
import { useSession } from '@/providers/session';

/**
 * The signed-in user's own community profile: `null` when they have not created one (and when signed out).
 * Reloads whenever the profile, a follow or a block changes anywhere in the app. Callers check the
 * `community` flag first, so nothing is requested while the feature is off.
 */
export function useMyProfile(enabled = true): Resource<MyCommunityProfile | null> {
  const { user, revision } = useSession();
  const ask = enabled && user !== null;
  return useResource<MyCommunityProfile | null>(
    `community-profile:${ask ? user.id : 'none'}`,
    (signal) => (ask ? getMyCommunityProfile(signal) : Promise.resolve(null)),
    revision.community,
  );
}
