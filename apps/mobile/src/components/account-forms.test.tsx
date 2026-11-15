import { fireEvent, render, screen } from '@testing-library/react-native';

import { ApiError } from '@/api/client';
import { ChangePasswordForm, DeleteAccountForm, validatePasswordChange } from '@/components/account-forms';
import { fakeSession, WithSession } from '@/test/session';

describe('validatePasswordChange', () => {
  it('uses the web wording', () => {
    expect(validatePasswordChange('', 'a long enough password')).toBe('Enter your current password.');
    expect(validatePasswordChange('current password', 'short')).toBe('Use at least 10 characters for the new password.');
    expect(validatePasswordChange('the same password', 'the same password')).toBe('The new password must be different from the current one.');
    expect(validatePasswordChange('current password', 'a long enough password')).toBeNull();
  });
});

describe('ChangePasswordForm', () => {
  it('changes the password through the session and confirms it', async () => {
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <ChangePasswordForm />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Current password'), 'current password');
    await fireEvent.changeText(screen.getByLabelText('New password'), 'a long enough password');
    await fireEvent.press(screen.getByRole('button', { name: 'Change password' }));

    expect(await screen.findByText('Password changed. Other devices have been signed out.')).toBeOnTheScreen();
    expect(session.changePassword).toHaveBeenCalledWith('current password', 'a long enough password');
    expect(screen.getByLabelText('Current password')).toHaveDisplayValue('');
  });

  it("shows the API's message when the current password is wrong", async () => {
    const session = fakeSession({
      changePassword: jest.fn().mockRejectedValue(new ApiError(400, 'invalid_credentials', 'The password was not changed. Check the details.')),
    });
    await render(
      <WithSession value={session}>
        <ChangePasswordForm />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Current password'), 'not my password');
    await fireEvent.changeText(screen.getByLabelText('New password'), 'a long enough password');
    await fireEvent.press(screen.getByRole('button', { name: 'Change password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The password was not changed. Check the details.');
  });
});

describe('DeleteAccountForm', () => {
  it('does nothing until DELETE is typed', async () => {
    const session = fakeSession();
    await render(
      <WithSession value={session}>
        <DeleteAccountForm />
      </WithSession>,
    );

    await fireEvent.changeText(screen.getByLabelText('Type DELETE to confirm'), 'yes');
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account and data' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Type DELETE to confirm.');
    expect(session.deleteAccount).not.toHaveBeenCalled();

    await fireEvent.changeText(screen.getByLabelText('Type DELETE to confirm'), ' delete ');
    await fireEvent.press(screen.getByRole('button', { name: 'Delete account and data' }));

    expect(session.deleteAccount).toHaveBeenCalledTimes(1);
  });
});
