import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/Card';
import { NumberField, TextField } from '../components/form/Field';
import { PrimaryButton, SecondaryButton } from '../components/form/Button';
import WeighEventResult from '../components/WeighEventResult';
import { useAppTheme } from '../theme/ThemeContext';
import { validatePositive } from '../validation';
import * as api from '../api';
import { ApiError } from '../api';
import type {
  ReusableSoloTicket,
  SoloTicketIn,
  TrailerProfile,
  TruckProfile,
  WeighEventOut,
} from '../types';

type Step = 'pick' | 'combined' | 'solo' | 'result';
type SoloMode = 'none' | 'reuse' | 'fresh';

export default function WeighEventNew() {
  const { theme } = useAppTheme();

  const [trucks, setTrucks] = useState<TruckProfile[] | null>(null);
  const [trailers, setTrailers] = useState<TrailerProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [step, setStep] = useState<Step>('pick');
  const [truckId, setTruckId] = useState<number | ''>('');
  const [trailerId, setTrailerId] = useState<number | ''>('');

  // Story 19: told upfront whether a reusable Solo weight is available.
  const [reusable, setReusable] = useState<ReusableSoloTicket | null | undefined>(undefined);

  // Combined Ticket
  const [steer, setSteer] = useState('');
  const [drive, setDrive] = useState('');
  const [trailerAxle, setTrailerAxle] = useState('');
  const [gross, setGross] = useState('');
  const [reweighReference, setReweighReference] = useState('');

  // Solo Ticket
  const [soloMode, setSoloMode] = useState<SoloMode>('none');
  const [reuseAdjusted, setReuseAdjusted] = useState(false);
  const [reuseGross, setReuseGross] = useState('');
  const [soloSteer, setSoloSteer] = useState('');
  const [soloDrive, setSoloDrive] = useState('');
  const [soloGross, setSoloGross] = useState('');
  const [soloReweighReference, setSoloReweighReference] = useState('');
  const [soloTimeGapHours, setSoloTimeGapHours] = useState('');

  const [confirmLinkNeeded, setConfirmLinkNeeded] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<WeighEventOut | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [truckList, trailerList] = await Promise.all([api.listTrucks(), api.listTrailers()]);
        setTrucks(truckList);
        setTrailers(trailerList);
      } catch {
        setLoadError('Could not load your Garage. Please try again.');
      }
    })();
  }, []);

  async function chooseProfiles() {
    if (truckId === '' || trailerId === '') return;
    setReusable(undefined);
    try {
      const found = await api.getReusableSoloTicket(Number(truckId));
      setReusable(found);
      setReuseGross(found ? String(found.gross) : '');
    } catch {
      setReusable(null);
    }
    setStep('combined');
  }

  const combinedErrors = {
    steer: validatePositive(steer, 'Steer Axle'),
    drive: validatePositive(drive, 'Drive Axle'),
    trailerAxle: validatePositive(trailerAxle, 'Trailer Axle group'),
    gross: validatePositive(gross, 'Gross Weight'),
  };
  const combinedValid = !Object.values(combinedErrors).some(Boolean);
  const [combinedTouched, setCombinedTouched] = useState(false);

  const freshSoloErrors = {
    steer: validatePositive(soloSteer, 'Solo Steer Axle'),
    drive: validatePositive(soloDrive, 'Solo Drive Axle'),
    gross: validatePositive(soloGross, 'Solo Gross Weight'),
  };
  const [soloTouched, setSoloTouched] = useState(false);
  const soloValid =
    soloMode === 'none' ||
    (soloMode === 'reuse' && (!reuseAdjusted || validatePositive(reuseGross, 'Adjusted weight') === null)) ||
    (soloMode === 'fresh' && !Object.values(freshSoloErrors).some(Boolean));

  function buildSoloPayload(): SoloTicketIn | null {
    if (soloMode === 'none') return null;
    if (soloMode === 'reuse') {
      if (!reusable) return null;
      return {
        kind: 'reused',
        from_timestamp: reusable.from_timestamp,
        gross: reuseAdjusted ? Number(reuseGross) : reusable.gross,
        adjusted: reuseAdjusted,
      };
    }
    return {
      kind: 'fresh',
      steer: Number(soloSteer),
      drive: Number(soloDrive),
      gross: Number(soloGross),
      reweigh_reference: soloReweighReference.trim() === '' ? null : soloReweighReference.trim(),
      time_gap_hours: soloTimeGapHours.trim() === '' ? null : Number(soloTimeGapHours),
    };
  }

  async function submitWeighEvent(opts: { confirmLink?: boolean; dropSolo?: boolean } = {}) {
    if (truckId === '' || trailerId === '') return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createWeighEvent({
        truck_id: Number(truckId),
        trailer_id: Number(trailerId),
        combined: {
          steer: Number(steer),
          drive: Number(drive),
          trailer_axle: Number(trailerAxle),
          gross: Number(gross),
          reweigh_reference: reweighReference.trim() === '' ? null : reweighReference.trim(),
        },
        solo: opts.dropSolo ? null : buildSoloPayload(),
        confirm_solo_link: Boolean(opts.confirmLink),
      });
      setResult(created);
      setConfirmLinkNeeded(false);
      setStep('result');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const detail = err.detail as { reason?: string } | null;
        if (detail && detail.reason === 'solo_link_unconfirmed') {
          setConfirmLinkNeeded(true);
          return;
        }
      }
      if (err instanceof ApiError && err.status === 404) {
        setSubmitError('That Truck or Trailer Profile could not be found.');
        return;
      }
      setSubmitError('Could not save this Weigh Event. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  function onSoloSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSoloTouched(true);
    if (!soloValid) return;
    void submitWeighEvent();
  }

  if (loadError) {
    return <p role="alert" style={{ color: '#a8402f' }}>{loadError}</p>;
  }

  if (trucks === null || trailers === null) {
    return <p style={{ color: theme.text2 }}>Loading…</p>;
  }

  // Story 17: no confusing empty picker - a clear prompt to add one first.
  if (trucks.length === 0 || trailers.length === 0) {
    return (
      <Card theme={theme}>
        <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.3rem' }}>
          Add a Truck and Trailer Profile first
        </h2>
        <p style={{ color: theme.text2 }}>
          You need at least one Truck Profile and one Trailer Profile in your Garage before you can
          record a Weigh Event.
        </p>
        <Link to="/garage" style={{ color: theme.linkStrong, fontWeight: 700 }}>
          Go to your Garage
        </Link>
      </Card>
    );
  }

  if (step === 'result' && result) {
    return (
      <Card theme={theme}>
        <WeighEventResult event={result} />
        <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
          <Link to="/weigh-events" style={{ color: theme.linkStrong, fontWeight: 700 }}>
            View history
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.8rem' }}>New Weigh Event</h1>

      {step === 'pick' && (
        <Card theme={theme}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.2rem' }}>
            Pick a Truck and Trailer
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
            <div>
              <label htmlFor="weigh-event-truck" style={{ fontWeight: 600, fontSize: '0.85rem', color: theme.text2 }}>Truck Profile</label>
              <select
                id="weigh-event-truck"
                value={truckId}
                onChange={(e) => setTruckId(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ display: 'block', width: '100%', height: 44, marginTop: 6, borderRadius: 10, border: `1.5px solid ${theme.border}` }}
              >
                <option value="">Select a Truck…</option>
                {trucks.map((t) => (
                  <option key={t.id} value={t.id}>{t.nickname}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="weigh-event-trailer" style={{ fontWeight: 600, fontSize: '0.85rem', color: theme.text2 }}>Trailer Profile</label>
              <select
                id="weigh-event-trailer"
                value={trailerId}
                onChange={(e) => setTrailerId(e.target.value === '' ? '' : Number(e.target.value))}
                style={{ display: 'block', width: '100%', height: 44, marginTop: 6, borderRadius: 10, border: `1.5px solid ${theme.border}` }}
              >
                <option value="">Select a Trailer…</option>
                {trailers.map((t) => (
                  <option key={t.id} value={t.id}>{t.nickname}</option>
                ))}
              </select>
            </div>
          </div>
          <PrimaryButton
            theme={theme}
            full
            style={{ marginTop: 22 }}
            disabled={truckId === '' || trailerId === ''}
            onClick={() => void chooseProfiles()}
          >
            Next
          </PrimaryButton>
        </Card>
      )}

      {step === 'combined' && (
        <Card theme={theme}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.2rem' }}>Combined Ticket</h2>
          <p style={{ color: theme.text2, fontSize: '0.9rem' }}>
            The CAT Scale Ticket from weighing the Tow Vehicle and Trailer hitched together.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <NumberField theme={theme} label="Steer Axle (lb)" value={steer} onChange={setSteer} error={combinedTouched ? combinedErrors.steer : null} />
            <NumberField theme={theme} label="Drive Axle (lb)" value={drive} onChange={setDrive} error={combinedTouched ? combinedErrors.drive : null} />
            <NumberField theme={theme} label="Trailer Axle group (lb)" value={trailerAxle} onChange={setTrailerAxle} error={combinedTouched ? combinedErrors.trailerAxle : null} />
            <NumberField theme={theme} label="Gross Weight (lb)" value={gross} onChange={setGross} error={combinedTouched ? combinedErrors.gross : null} />
          </div>
          <TextField theme={theme} label="Reweigh Reference — optional" value={reweighReference} onChange={setReweighReference} />
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <SecondaryButton theme={theme} type="button" style={{ flex: 'none', width: 110 }} onClick={() => setStep('pick')}>
              Back
            </SecondaryButton>
            <PrimaryButton
              theme={theme}
              onClick={() => {
                setCombinedTouched(true);
                if (combinedValid) setStep('solo');
              }}
            >
              Next
            </PrimaryButton>
          </div>
        </Card>
      )}

      {step === 'solo' && !confirmLinkNeeded && (
        <Card theme={theme}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.2rem' }}>Solo Ticket</h2>

          {reusable === undefined && <p style={{ color: theme.text2 }}>Checking for a reusable Solo weight…</p>}
          {reusable === null && (
            <p style={{ color: theme.text2, fontSize: '0.88rem' }}>
              No reusable Solo weight is on file for this Truck Profile.
            </p>
          )}
          {reusable && (
            <p style={{ color: theme.text2, fontSize: '0.88rem' }}>
              A past Solo weight is available: <strong>{reusable.gross} lb</strong> from{' '}
              {new Date(reusable.from_timestamp).toLocaleString()}.
            </p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
            <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input type="radio" checked={soloMode === 'none'} onChange={() => setSoloMode('none')} />
              Skip the Solo Ticket
            </label>
            {reusable && (
              <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input type="radio" checked={soloMode === 'reuse'} onChange={() => setSoloMode('reuse')} />
                Reuse the past Solo weight
              </label>
            )}
            <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input type="radio" checked={soloMode === 'fresh'} onChange={() => setSoloMode('fresh')} />
              Enter a new Solo Ticket
            </label>
          </div>

          {soloMode === 'reuse' && reusable && (
            <div style={{ marginTop: 14 }}>
              <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input type="checkbox" checked={reuseAdjusted} onChange={(e) => setReuseAdjusted(e.target.checked)} />
                Something has changed since then (adjust the weight)
              </label>
              {reuseAdjusted && (
                <div style={{ marginTop: 10, maxWidth: 220 }}>
                  <NumberField
                    theme={theme}
                    label="Adjusted Solo Gross Weight (lb)"
                    value={reuseGross}
                    onChange={setReuseGross}
                    error={soloTouched ? validatePositive(reuseGross, 'Adjusted weight') : null}
                  />
                </div>
              )}
            </div>
          )}

          {soloMode === 'fresh' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 14 }}>
              <NumberField theme={theme} label="Solo Steer Axle (lb)" value={soloSteer} onChange={setSoloSteer} error={soloTouched ? freshSoloErrors.steer : null} />
              <NumberField theme={theme} label="Solo Drive Axle (lb)" value={soloDrive} onChange={setSoloDrive} error={soloTouched ? freshSoloErrors.drive : null} />
              <NumberField theme={theme} label="Solo Gross Weight (lb)" value={soloGross} onChange={setSoloGross} error={soloTouched ? freshSoloErrors.gross : null} />
              <NumberField theme={theme} label="Hours between weighings — optional" value={soloTimeGapHours} onChange={setSoloTimeGapHours} />
              <div style={{ gridColumn: '1 / -1' }}>
                <TextField theme={theme} label="Reweigh Reference — optional" value={soloReweighReference} onChange={setSoloReweighReference} />
              </div>
            </div>
          )}

          {submitError && <p role="alert" style={{ color: '#a8402f', fontSize: '0.85rem' }}>{submitError}</p>}

          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <SecondaryButton theme={theme} type="button" style={{ flex: 'none', width: 110 }} onClick={() => setStep('combined')}>
              Back
            </SecondaryButton>
            <PrimaryButton theme={theme} disabled={submitting} onClick={(e) => onSoloSubmit(e as unknown as React.FormEvent)}>
              {submitting ? 'Saving…' : 'See results'}
            </PrimaryButton>
          </div>
        </Card>
      )}

      {confirmLinkNeeded && (
        <Card theme={theme}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.2rem' }}>Confirm Solo Ticket link</h2>
          <p style={{ color: theme.text2 }}>
            This Solo Ticket's Reweigh Reference doesn't match the Combined Ticket's. Are they from
            the same weigh trip?
          </p>
          {submitError && <p role="alert" style={{ color: '#a8402f', fontSize: '0.85rem' }}>{submitError}</p>}
          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <SecondaryButton
              theme={theme}
              type="button"
              disabled={submitting}
              onClick={() => void submitWeighEvent({ dropSolo: true })}
            >
              No, save Combined Ticket only
            </SecondaryButton>
            <PrimaryButton theme={theme} disabled={submitting} onClick={() => void submitWeighEvent({ confirmLink: true })}>
              Yes, they belong together
            </PrimaryButton>
          </div>
        </Card>
      )}
    </div>
  );
}
