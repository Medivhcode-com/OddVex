import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAuthToken } from '@/api/client';
import { PROFILE_VISIBILITY } from '@/components/community-copy';
import { ProfileForm } from '@/components/profile-form';
import { CommunityProfileEditScreen } from '@/screens/community-profile-edit';
import { errorResponse, jsonResponse } from '@/test/api';
import { showCommunity } from '@/test/community';
import { guidelines, myProfile, privateProfile } from '@/test/fixtures';

const PUT = 'PUT /v1/community/profile';
const HANDLE_ERROR = 'Enter a handle of 3 to 20 characters: lowercase letters, numbers and underscores.';

beforeEach(() => setAuthToken('token-1'));
afterEach(() => setAuthToken(null));

async function fill(handle: string, bio?: string) {
  await fireEvent.changeText(screen.getByLabelText('Handle'), handle);
  if (bio !== undefined) await fireEvent.changeText(screen.getByLabelText('Bio (optional)'), bio);
}
const submit = (label = 'Create profile') => fireEvent.press(screen.getByRole('button', { name: label }));

describe('ProfileForm validation', () => {
  it('lower-cases the handle as it is typed', async () => {
    await showCommunity(<ProfileForm />, {});
    await fill('Sam_Reads_LINES');
    expect(screen.getByLabelText('Handle').props.value).toBe('sam_reads_lines');
  });

  it.each([
    ['too short', 'ab'],
    ['too long', 'a_handle_that_is_far_too_long'],
    ['a space', 'sam reads'],
    ['a hyphen', 'sam-reads'],
    ['nothing', ''],
  ])('rejects %s without calling the API', async (_case, handle) => {
    const { fetchMock } = await showCommunity(<ProfileForm />, {});
    await fill(handle);
    await submit();

    expect(screen.getByText(HANDLE_ERROR)).toBeOnTheScreen();
    expect(screen.getByText(HANDLE_ERROR)).toHaveProp('accessibilityRole', 'alert');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('accepts 3 and 20 characters of a-z, 0-9 and underscore', async () => {
    const { sent } = await showCommunity(<ProfileForm />, { [PUT]: () => jsonResponse(myProfile, 201) });
    await fill('a_1');
    await submit();
    await waitFor(() => expect(sent()).toHaveLength(1));
    await fill('abcdefghij_123456789');
    await submit();
    await waitFor(() => expect(sent()).toHaveLength(2));
    expect(sent()[1].body).toMatchObject({ handle: 'abcdefghij_123456789' });
  });

  it('counts the bio as it is typed and stops at 280', async () => {
    const { fetchMock } = await showCommunity(<ProfileForm />, {});
    expect(screen.getByText('0 / 280 characters')).toBeOnTheScreen();
    await fill('sam_reads_lines', 'Totals.');
    expect(screen.getByText('7 / 280 characters')).toBeOnTheScreen();

    await fireEvent.changeText(screen.getByLabelText('Bio (optional)'), 'x'.repeat(281));
    expect(screen.getByText('281 / 280 characters. Shorten it to 280 or fewer.')).toHaveProp('accessibilityRole', 'alert');
    await submit();
    expect(fetchMock).not.toHaveBeenCalled();

    await fireEvent.changeText(screen.getByLabelText('Bio (optional)'), 'x'.repeat(280));
    expect(screen.getByText('280 / 280 characters')).toBeOnTheScreen();
  });

  it('says in plain words what a public profile shows and never shows', async () => {
    await showCommunity(<ProfileForm />, {});
    expect(screen.getByText(PROFILE_VISIBILITY)).toBeOnTheScreen();
    expect(PROFILE_VISIBILITY).toBe(
      'A public profile shows your handle, your bio, your picks and your graded record. It never shows your email, your name, your bets or your plan.',
    );
    expect(screen.getByText(/^Private: you can browse, but you can't post picks or comments or follow people/)).toBeOnTheScreen();
    await fireEvent.press(screen.getByRole('switch', { name: 'Make my profile public' }));
    expect(screen.getByRole('switch', { name: 'Make my profile public' })).toBeChecked();
    expect(screen.getByText(/^Public: you can post picks and comments and follow people/)).toBeOnTheScreen();
  });
});

describe('ProfileForm payload', () => {
  it('creates a private profile with no bio by default', async () => {
    const { sent, session } = await showCommunity(<ProfileForm />, { [PUT]: () => jsonResponse(privateProfile, 201) });
    await fill('sam_reads_lines');
    await submit();

    expect(await screen.findByText('Profile saved.')).toBeOnTheScreen();
    expect(sent()[0]).toMatchObject({ method: 'PUT', path: '/v1/community/profile' });
    expect(sent()[0].body).toEqual({ handle: 'sam_reads_lines', bio: null, is_public: false });
    expect(sent()[0].headers.authorization).toBe('Bearer token-1');
    expect(session.changed).toHaveBeenCalledWith('community');
  });

  it('sends the bio and the public choice', async () => {
    const { sent } = await showCommunity(<ProfileForm />, { [PUT]: () => jsonResponse(myProfile, 201) });
    await fill('Sam_Reads_Lines', '  Totals and closing lines.  ');
    await fireEvent.press(screen.getByRole('switch', { name: 'Make my profile public' }));
    await submit();

    await waitFor(() => expect(sent()).toHaveLength(1));
    expect(sent()[0].body).toEqual({ handle: 'sam_reads_lines', bio: 'Totals and closing lines.', is_public: true });
  });

  it('starts from the saved profile when editing', async () => {
    const { sent } = await showCommunity(<ProfileForm existing={myProfile} />, { [PUT]: { ...myProfile, is_public: false, can_post: false } });

    expect(screen.getByLabelText('Handle').props.value).toBe('sam_reads_lines');
    expect(screen.getByLabelText('Bio (optional)').props.value).toBe('Totals and closing lines.');
    expect(screen.getByRole('switch', { name: 'Make my profile public' })).toBeChecked();
    await fireEvent.press(screen.getByRole('switch', { name: 'Make my profile public' }));
    await submit('Save profile');

    await waitFor(() => expect(sent()).toHaveLength(1));
    expect(sent()[0].body).toEqual({ handle: 'sam_reads_lines', bio: 'Totals and closing lines.', is_public: false });
  });
});

describe('ProfileForm API rejections', () => {
  const details = (field: string, rule: string) => ({ field, rule });
  it.each([
    ['a taken handle', errorResponse(409, 'handle_taken', 'This handle is already in use'), 'That handle is already taken. Try another one.'],
    ['a reserved handle', errorResponse(422, 'handle_reserved', 'This handle is not available', { field: 'handle' }), "That handle is reserved and can't be used. Try another one."],
    ['a handle the API finds malformed', errorResponse(422, 'invalid_handle', 'A handle is 3 to 20 characters', { field: 'handle' }), 'A handle is 3 to 20 characters: lowercase letters, numbers and underscores.'],
    ['a link in the bio', errorResponse(422, 'links_not_allowed', 'Links are not allowed', details('bio', 'links')), "Links aren't allowed here. Remove the link and try again."],
    [
      'a promise about a result',
      errorResponse(422, 'content_not_allowed', 'Do not present a result as certain.', details('bio', 'guaranteed_outcome')),
      'This reads as a promise about a result, and no result is certain. Reword it and try again.',
    ],
    [
      'pressure to bet',
      errorResponse(422, 'content_not_allowed', 'Do not push other people to bet.', details('bio', 'inducement_to_bet')),
      'This reads as pressure to bet, to bet more or to win money back. Reword it and try again.',
    ],
    [
      'selling',
      errorResponse(422, 'content_not_allowed', 'Selling picks is not allowed here.', details('bio', 'selling_or_promotion')),
      "Selling picks, promotions and payment details aren't allowed here. Remove them and try again.",
    ],
    [
      'asking for contact elsewhere',
      errorResponse(422, 'content_not_allowed', 'Do not ask people to contact you elsewhere.', details('handle', 'contact_solicitation')),
      "Asking people to contact you somewhere else isn't allowed here. Remove that and try again.",
    ],
    [
      'contact details',
      errorResponse(422, 'content_not_allowed', 'Do not post contact details.', details('bio', 'contact_details')),
      "Phone numbers, email addresses and other contact details aren't allowed here. Remove them and try again.",
    ],
    ['too many attempts', errorResponse(429, 'rate_limited', 'Too many requests. Try again in 30 seconds.'), 'Too many attempts. Wait a minute, then try again.'],
  ])('explains %s', async (_case, response, message) => {
    const { session } = await showCommunity(<ProfileForm />, { [PUT]: () => response });
    await fill('sam_reads_lines', 'Some bio text.');
    await submit();

    const shown = await screen.findByText(message);
    expect(shown).toBeOnTheScreen();
    expect(screen.queryByText('Profile saved.')).toBeNull();
    expect(session.changed).not.toHaveBeenCalled();
    // What was typed is kept, so it can be reworded.
    expect(screen.getByLabelText('Bio (optional)').props.value).toBe('Some bio text.');
  });

  it('puts a handle problem on the handle field and a bio problem on the bio field', async () => {
    const { serve } = await showCommunity(<ProfileForm />, { [PUT]: () => errorResponse(409, 'handle_taken', 'This handle is already in use') });
    await fill('sam_reads_lines', 'Some bio text.');
    await submit();
    expect(await screen.findByText('That handle is already taken. Try another one.')).toHaveProp('accessibilityRole', 'alert');
    expect(screen.getByLabelText('Handle')).toHaveProp('aria-invalid', true);

    serve({ [PUT]: () => errorResponse(422, 'links_not_allowed', 'Links are not allowed', { field: 'bio', rule: 'links' }) });
    await submit();
    expect(await screen.findByText("Links aren't allowed here. Remove the link and try again.")).toBeOnTheScreen();
    expect(screen.getByLabelText('Bio (optional)')).toHaveProp('aria-invalid', true);
    expect(screen.getByLabelText('Handle')).not.toHaveProp('aria-invalid', true);
  });
});

describe('CommunityProfileEditScreen', () => {
  it('shows the guidelines and a blank form to someone without a profile', async () => {
    await showCommunity(<CommunityProfileEditScreen />, {
      'GET /v1/community/profile': () => errorResponse(404, 'not_found', 'You have no community profile yet'),
      'GET /v1/community/guidelines': guidelines,
    });

    expect(await screen.findByText('1. Fixture rule one')).toBeOnTheScreen();
    expect(screen.getByRole('button', { name: 'Create profile' })).toBeOnTheScreen();
    expect(screen.getByLabelText('Handle').props.value).toBe('');
  });

  it('opens on the saved profile and passes on a moderation note', async () => {
    await showCommunity(<CommunityProfileEditScreen />, {
      'GET /v1/community/profile': { ...myProfile, moderation_status: 'hidden', moderation_note: 'Hidden by moderators.', can_post: false },
    });

    expect(await screen.findByRole('button', { name: 'Save profile' })).toBeOnTheScreen();
    expect(screen.getByLabelText('Handle').props.value).toBe('sam_reads_lines');
    expect(screen.getByText('Hidden by moderators.')).toBeOnTheScreen();
  });
});
