import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { reportCommunityContent } from '@/api/client';
import type { ReportCreate, ReportReason, ReportTarget } from '@/api/types';
import { communityError, REPORT_DETAILS_MAX, REPORT_REASONS, REPORT_SENT } from '@/components/community-copy';
import { Choice } from '@/components/form';
import { LimitedText, tooLong } from '@/components/limited-text';
import { Button, Notice } from '@/components/states';
import { space } from '@/theme';

/**
 * "Report" on a pick, a comment or a profile: a button that opens the form in place. A reason, optional
 * details, then `POST /v1/community/reports`. The confirmation is neutral and says the reported person is
 * not told who sent it.
 */
export function ReportControl({ targetType, targetId, what }: { targetType: ReportTarget; targetId: string; what: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>('spam');
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit() {
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
