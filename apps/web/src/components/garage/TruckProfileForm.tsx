import { useState } from 'react';
import { NumberField, TextField } from '../form/Field';
import { PrimaryButton, SecondaryButton } from '../form/Button';
import { useAppTheme } from '../../theme/ThemeContext';
import { validatePositive } from '../../validation';
import { ApiError } from '../../api';
import type { TruckProfile, TruckProfileIn } from '../../types';

interface Props {
  initial?: TruckProfile;
  onSubmit: (payload: TruckProfileIn) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}

/** Add/edit form for a Truck Profile (issue #30 Story 10/12): GVWR, Front
 * GAWR, Rear GAWR, optional GCWR, optional Nickname. Shared between "add
 * new" and "edit existing" - the only difference is `initial`/`submitLabel`. */
export default function TruckProfileForm({ initial, onSubmit, onCancel, submitLabel }: Props) {
  const { theme } = useAppTheme();
  const [gvwr, setGvwr] = useState(initial ? String(initial.gvwr) : '');
  const [frontGawr, setFrontGawr] = useState(initial ? String(initial.front_gawr) : '');
  const [rearGawr, setRearGawr] = useState(initial ? String(initial.rear_gawr) : '');
  const [gcwr, setGcwr] = useState(initial?.gcwr != null ? String(initial.gcwr) : '');
  const [nickname, setNickname] = useState(initial?.nickname ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const errors = {
    gvwr: validatePositive(gvwr, 'GVWR'),
    frontGawr: validatePositive(frontGawr, 'Front GAWR'),
    rearGawr: validatePositive(rearGawr, 'Rear GAWR'),
    gcwr: validatePositive(gcwr, 'GCWR', false),
  };
  const [touched, setTouched] = useState(false);
  const hasErrors = Object.values(errors).some(Boolean);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await onSubmit({
        gvwr: Number(gvwr),
        front_gawr: Number(frontGawr),
        rear_gawr: Number(rearGawr),
        gcwr: gcwr.trim() === '' ? null : Number(gcwr),
        nickname: nickname.trim() === '' ? null : nickname.trim(),
      });
    } catch (err) {
      // Story 30: acting on a Profile that isn't actually the caller's
      // (a stale edit form left open after it was deleted elsewhere) shows
      // a clear message, not a broken page.
      if (err instanceof ApiError && err.status === 404) {
        setFormError('This Truck Profile no longer exists - it may have been deleted.');
      } else {
        setFormError('Could not save this Truck Profile. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <NumberField theme={theme} label="GVWR (lb)" value={gvwr} onChange={setGvwr} error={touched ? errors.gvwr : null} />
        <NumberField theme={theme} label="GCWR (lb) — optional" value={gcwr} onChange={setGcwr} error={touched ? errors.gcwr : null} />
        <NumberField theme={theme} label="Front GAWR (lb)" value={frontGawr} onChange={setFrontGawr} error={touched ? errors.frontGawr : null} />
        <NumberField theme={theme} label="Rear GAWR (lb)" value={rearGawr} onChange={setRearGawr} error={touched ? errors.rearGawr : null} />
      </div>
      <TextField theme={theme} label="Nickname — optional" value={nickname} onChange={setNickname} placeholder="e.g. Addie" />
      {formError && <p role="alert" style={{ margin: 0, fontSize: '0.85rem', color: '#a8402f' }}>{formError}</p>}
      <div style={{ display: 'flex', gap: 10 }}>
        <SecondaryButton theme={theme} type="button" onClick={onCancel} style={{ flex: 'none', width: 110 }}>
          Cancel
        </SecondaryButton>
        <PrimaryButton theme={theme} type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </PrimaryButton>
      </div>
    </form>
  );
}
