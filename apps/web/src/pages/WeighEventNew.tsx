import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/Card';
import { NumberField, TextField } from '../components/form/Field';
import { PrimaryButton, SecondaryButton } from '../components/form/Button';
import TruckProfileForm from '../components/garage/TruckProfileForm';
import TrailerProfileForm from '../components/garage/TrailerProfileForm';
import WeighEventResult from '../components/WeighEventResult';
import { useAppTheme } from '../theme/ThemeContext';
import { validatePositive } from '../validation';
import * as api from '../api';
import { ApiError } from '../api';
import type {
  ReusableSoloTicket,
  SoloTicketIn,
  TrailerProfile,
  TrailerProfileIn,
  TruckProfile,
  TruckProfileIn,
  WeighEventOut,
} from '../types';

type Step = 'pick' | 'combined' | 'solo' | 'result';
type SoloMode = 'none' | 'reuse' | 'fresh';

// Issue #45 / ADR 0017: a One-Off Truck/Trailer, or a brand-new Profile
// added inline - two extra `<select>` options above the real saved-Profile
// list. Distinct string sentinels (never numeric) so they can never be
// confused with a real Profile's `id`.
type PickerMode = 'pick' | 'oneoff' | 'addnew';
const ONE_OFF_SENTINEL = '__one_off__';
const ADD_NEW_SENTINEL = '__add_new__';

export default function WeighEventNew() {
  const { theme } = useAppTheme();

  const [trucks, setTrucks] = useState<TruckProfile[] | null>(null);
  const [trailers, setTrailers] = useState<TrailerProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [step, setStep] = useState<Step>('pick');
  const [truckMode, setTruckMode] = useState<PickerMode>('pick');
  const [trailerMode, setTrailerMode] = useState<PickerMode>('pick');
  const [truckId, setTruckId] = useState<number | ''>('');
  const [trailerId, setTrailerId] = useState<number | ''>('');
  // Holds a One-Off Truck/Trailer's raw rating fields locally - never sent
  // to `api.createTruck`/`createTrailer`, only inlined on the eventual
  // `POST /weigh-events` call (issue #45's own Implementation Decisions).
  const [oneOffTruck, setOneOffTruck] = useState<TruckProfileIn | null>(null);
  const [oneOffTrailer, setOneOffTrailer] = useState<TrailerProfileIn | null>(null);

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

  function handleTruckSelectChange(value: string) {
    if (value === ONE_OFF_SENTINEL) {
      setTruckMode('oneoff');
      setTruckId('');
    } else if (value === ADD_NEW_SENTINEL) {
      setTruckMode('addnew');
      setTruckId('');
    } else {
      setTruckMode('pick');
      setOneOffTruck(null);
      setTruckId(value === '' ? '' : Number(value));
    }
  }

  function handleTrailerSelectChange(value: string) {
    if (value === ONE_OFF_SENTINEL) {
      setTrailerMode('oneoff');
      setTrailerId('');
    } else if (value === ADD_NEW_SENTINEL) {
      setTrailerMode('addnew');
      setTrailerId('');
    } else {
      setTrailerMode('pick');
      setOneOffTrailer(null);
      setTrailerId(value === '' ? '' : Number(value));
    }
  }

  async function handleOneOffTruckSubmit(payload: TruckProfileIn): Promise<void> {
    setOneOffTruck(payload);
  }

  async function handleAddNewTruckSubmit(payload: TruckProfileIn): Promise<void> {
    const created = await api.createTruck(payload);
    setTrucks((prev) => (prev ? [...prev, created] : [created]));
    setTruckMode('pick');
    setTruckId(created.id);
  }

  async function handleOneOffTrailerSubmit(payload: TrailerProfileIn): Promise<void> {
    setOneOffTrailer(payload);
  }

  async function handleAddNewTrailerSubmit(payload: TrailerProfileIn): Promise<void> {
    const created = await api.createTrailer(payload);
    setTrailers((prev) => (prev ? [...prev, created] : [created]));
    setTrailerMode('pick');
    setTrailerId(created.id);
  }

  const truckReady =
    truckMode === 'pick' ? truckId !== '' : truckMode === 'oneoff' ? oneOffTruck !== null : false;
  const trailerReady =
    trailerMode === 'pick'
      ? trailerId !== ''
      : trailerMode === 'oneoff'
        ? oneOffTrailer !== null
        : false;

  const truckSelectValue =
    truckMode === 'oneoff' ? ONE_OFF_SENTINEL : truckMode === 'addnew' ? ADD_NEW_SENTINEL : String(truckId);
  const trailerSelectValue =
    trailerMode === 'oneoff'
      ? ONE_OFF_SENTINEL
      : trailerMode === 'addnew'
        ? ADD_NEW_SENTINEL
        : String(trailerId);

  async function chooseProfiles() {
    if (!truckReady || !trailerReady) return;
    setReusable(undefined);
    if (truckMode === 'pick') {
      try {
        const found = await api.getReusableSoloTicket(Number(truckId));
        setReusable(found);
        setReuseGross(found ? String(found.gross) : '');
      } catch {
        setReusable(null);
      }
    } else {
      // Story 8: a One-Off Truck has no history - never call the
      // reusable-Solo-Ticket endpoint, and behave as if it resolved to
      // null (no reusable Solo weight, no network delay/checking state).
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
    if (!truckReady || !trailerReady) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createWeighEvent({
        ...(truckMode === 'pick' ? { truck_id: Number(truckId) } : { truck: oneOffTruck! }),
        ...(trailerMode === 'pick' ? { trailer_id: Number(trailerId) } : { trailer: oneOffTrailer! }),
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
                value={truckSelectValue}
                onChange={(e) => handleTruckSelectChange(e.target.value)}
                style={{ display: 'block', width: '100%', height: 44, marginTop: 6, borderRadius: 10, border: `1.5px solid ${theme.border}` }}
              >
                <option value="">Select a Truck…</option>
                <option value={ONE_OFF_SENTINEL}>Enter a one-off Truck</option>
                <option value={ADD_NEW_SENTINEL}>Add new Truck to my Garage</option>
                {trucks.map((t) => (
                  <option key={t.id} value={t.id}>{t.nickname}</option>
                ))}
              </select>
              {truckMode === 'oneoff' && (
                <div style={{ marginTop: 12 }}>
                  <TruckProfileForm
                    submitLabel="Use this Truck"
                    onSubmit={handleOneOffTruckSubmit}
                    onCancel={() => handleTruckSelectChange('')}
                  />
                  {oneOffTruck && (
                    <p style={{ fontSize: '0.8rem', color: theme.text2, marginTop: 8 }}>
                      One-off Truck ready.
                    </p>
                  )}
                </div>
              )}
              {truckMode === 'addnew' && (
                <div style={{ marginTop: 12 }}>
                  <TruckProfileForm
                    submitLabel="Add Truck"
                    onSubmit={handleAddNewTruckSubmit}
                    onCancel={() => handleTruckSelectChange('')}
                  />
                </div>
              )}
            </div>
            <div>
              <label htmlFor="weigh-event-trailer" style={{ fontWeight: 600, fontSize: '0.85rem', color: theme.text2 }}>Trailer Profile</label>
              <select
                id="weigh-event-trailer"
                value={trailerSelectValue}
                onChange={(e) => handleTrailerSelectChange(e.target.value)}
                style={{ display: 'block', width: '100%', height: 44, marginTop: 6, borderRadius: 10, border: `1.5px solid ${theme.border}` }}
              >
                <option value="">Select a Trailer…</option>
                <option value={ONE_OFF_SENTINEL}>Enter a one-off Trailer</option>
                <option value={ADD_NEW_SENTINEL}>Add new Trailer to my Garage</option>
                {trailers.map((t) => (
                  <option key={t.id} value={t.id}>{t.nickname}</option>
                ))}
              </select>
              {trailerMode === 'oneoff' && (
                <div style={{ marginTop: 12 }}>
                  <TrailerProfileForm
                    submitLabel="Use this Trailer"
                    onSubmit={handleOneOffTrailerSubmit}
                    onCancel={() => handleTrailerSelectChange('')}
                  />
                  {oneOffTrailer && (
                    <p style={{ fontSize: '0.8rem', color: theme.text2, marginTop: 8 }}>
                      One-off Trailer ready.
                    </p>
                  )}
                </div>
              )}
              {trailerMode === 'addnew' && (
                <div style={{ marginTop: 12 }}>
                  <TrailerProfileForm
                    submitLabel="Add Trailer"
                    onSubmit={handleAddNewTrailerSubmit}
                    onCancel={() => handleTrailerSelectChange('')}
                  />
                </div>
              )}
            </div>
          </div>
          <PrimaryButton
            theme={theme}
            full
            style={{ marginTop: 22 }}
            disabled={!truckReady || !trailerReady}
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
