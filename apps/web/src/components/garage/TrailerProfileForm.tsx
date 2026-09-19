import { useState } from 'react';
import { NumberField, TextField } from '../form/Field';
import { PrimaryButton, SecondaryButton } from '../form/Button';
import { useAppTheme } from '../../theme/ThemeContext';
import { validatePositive, validatePositiveInt } from '../../validation';
import { ApiError } from '../../api';
import type { TrailerProfile, TrailerProfileIn } from '../../types';

interface Props {
  initial?: TrailerProfile;
  onSubmit: (payload: TrailerProfileIn) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}

/** Add/edit form for a Trailer Profile (issue #30 Story 14): GVWR, GAWR,
 * Axle Count, optional UVW, optional Nickname - mirrors
 * `TruckProfileForm` exactly, per Trailer Profile's own field set. */
export default function TrailerProfileForm({ initial, onSubmit, onCancel, submitLabel }: Props) {
  const { theme } = useAppTheme();
  const [gvwr, setGvwr] = useState(initial ? String(initial.gvwr) : '');
  const [gawr, setGawr] = useState(initial ? String(initial.gawr) : '');
  const [axleCount, setAxleCount] = useState(initial ? String(initial.axle_count) : '2');
  const [uvw, setUvw] = useState(initial?.uvw != null ? String(initial.uvw) : '');
  const [nickname, setNickname] = useState(initial?.nickname ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const errors = {
    gvwr: validatePositive(gvwr, 'GVWR'),
    gawr: validatePositive(gawr, 'GAWR'),
    axleCount: validatePositiveInt(axleCount, 'Axle Count'),
    uvw: validatePositive(uvw, 'UVW', false),
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
        gawr: Number(gawr),
        axle_count: Number(axleCount),
        uvw: uvw.trim() === '' ? null : Number(uvw),
        nickname: nickname.trim() === '' ? null : nickname.trim(),
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setFormError('This Trailer Profile no longer exists - it may have been deleted.');
      } else {
        setFormError('Could not save this Trailer Profile. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <NumberField theme={theme} label="GVWR (lb)" value={gvwr} onChange={setGvwr} error={touched ? errors.gvwr : null} />
        <NumberField theme={theme} label="GAWR per axle (lb)" value={gawr} onChange={setGawr} error={touched ? errors.gawr : null} />
        <NumberField theme={theme} label="Axle Count" value={axleCount} onChange={setAxleCount} error={touched ? errors.axleCount : null} />
        <NumberField theme={theme} label="UVW (lb) — optional" value={uvw} onChange={setUvw} error={touched ? errors.uvw : null} />
      </div>
      <TextField theme={theme} label="Nickname — optional" value={nickname} onChange={setNickname} placeholder="e.g. Goose" />
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
