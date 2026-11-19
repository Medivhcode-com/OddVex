import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { reportCommunityContent } from '@/api/client';
import type { ReportCreate, ReportReason, ReportTarget } from '@/api/types';
import { communityError, REPORT_DETAILS_MAX, REPORT_REASONS, REPORT_SENT } from '@/components/community-copy';
import { Choice } from '@/components/form';
import { LimitedText, tooLong } from '@/components/limited-text';
import { Button, Notice } from '@/components/states';
import { DRAFT_KEPT, useDraft, useDraftKept } from '@/session/drafts';
import { space } from '@/theme';

/**
 * "Report" on a pick, a comment or a profile: a button that opens the form in place. A reason, optional
 * details, then `POST /v1/community/reports`. The confirmation is neutral and says the reported person is
 * not told who sent it. An open form is a draft: it comes back, still open, if the session ends before the
 * report is sent.
 */
export function ReportControl({ targetType, targetId, what }: { targetType: ReportTarget; targetId: string; what: string }) {
  const draft = `report:${targetType}:${targetId}`;
  const [open, setOpen] = useDraft(`${draft}:open`, false);
  const [reason, setReason] = useDraft<ReportReason>(`${draft}:reason`, 'spam');
  const [details, setDetails] = useDraft(`${draft}:details`, '');
  const [keptNotice, dismissKeptNotice, draftSaved] = useDraftKept(draft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit() {
    dismissKeptNotice();
    if (tooLong(details, REPORT_DETAILS_MAX)) return;
    const text = details.trim();
    const body: ReportCreate = { target_type: targetType, target_id: targetId, reason, ...(text ? { details: text } : null) };
    setBusy(true);
    setError(null);
    try {
      await reportCommunityContent(body);
      setSent(true);
      setOpen(false);
      setDetails('');
      draftSaved();
    } catch (caught) {
      setError(communityError(caught, 'The report was not sent. Try again.', 'report'));
    } finally {
      setBusy(false);
    }
  }

  if (sent) return <Notice tone="neutral" text={REPORT_SENT} />;
  if (!open) {
    return <Button label="Report" variant="ghost" compact accessibilityLabel={`Report ${what}`} onPress={() => setOpen(true)} />;
  }
  return (
    <View style={styles.form}>
      {keptNotice ? <Notice tone="neutral" text={DRAFT_KEPT} /> : null}
      <Choice label={`Why are you reporting ${what}?`} options={REPORT_REASONS} value={reason} onChange={setReason} />
      <LimitedText label="Details (optional)" value={details} onChangeText={setDetails} max={REPORT_DETAILS_MAX} />
      {error ? <Notice tone="error" text={error} /> : null}
      <View style={styles.actions}>
        <Button label={busy ? 'Sending report' : 'Send report'} compact disabled={busy} onPress={submit} />
        <Button label="Cancel" variant="secondary" compact disabled={busy} accessibilityLabel="Cancel the report" onPress={() => setOpen(false)} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[3], alignSelf: 'stretch' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space[3] },
});
