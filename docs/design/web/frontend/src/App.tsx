import { useState } from 'react';
import type { CSSProperties } from 'react';
import Header from './components/Header';
import Footer from './components/Footer';
import ResultBox from './components/ResultBox';
import { LIGHT, DARK, ORANGE, GREEN, BANNER, BANNER_MESSAGE } from './theme';
import type { Mode } from './theme';
import type { TruckForm, TrailerForm, CombinedForm, SoloForm, EvaluateResponse } from './types';
import { evaluate } from './api';

const inputStyle = (theme: typeof LIGHT): CSSProperties => ({
  height: 50, padding: '0 14px', borderRadius: 12, border: `1.5px solid ${theme.border}`,
  background: theme.surfaceSunken, color: theme.text, fontSize: '1rem', width: '100%', boxSizing: 'border-box',
});
const labelStyle = (theme: typeof LIGHT): CSSProperties => ({ fontWeight: 600, fontSize: '0.85rem', color: theme.text2 });

export default function App() {
  const [step, setStep] = useState(0);
  const [mode, setMode] = useState<Mode>('light');
  const theme = mode === 'dark' ? DARK : LIGHT;

  const [truck, setTruck] = useState<TruckForm>({ gvwr: '', frontGawr: '', rearGawr: '', gcwr: '' });
  const [trailer, setTrailer] = useState<TrailerForm>({ gvwr: '', gawr: '', axleCount: '2', uvw: '' });
  const [combined, setCombined] = useState<CombinedForm>({ steer: '', drive: '', trailerAxle: '', gross: '' });
  const [hasSolo, setHasSolo] = useState(false);
  const [solo, setSolo] = useState<SoloForm>({ steer: '', drive: '', gross: '' });
  const [timeGapHours, setTimeGapHours] = useState('');

  const [result, setResult] = useState<EvaluateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const num = (v: string) => { const f = parseFloat(v); return v !== '' && isFinite(f) ? f : null; };

  const valid0 = (num(truck.gvwr) ?? 0) > 0 && (num(truck.frontGawr) ?? 0) > 0 && (num(truck.rearGawr) ?? 0) > 0;
  const valid1 = (num(trailer.gvwr) ?? 0) > 0 && (num(trailer.gawr) ?? 0) > 0;
  const valid2 = (num(combined.steer) ?? 0) > 0 && (num(combined.drive) ?? 0) > 0 && (num(combined.trailerAxle) ?? 0) > 0 && (num(combined.gross) ?? 0) > 0;
  const valid3 = !hasSolo || ((num(solo.steer) ?? 0) > 0 && (num(solo.drive) ?? 0) > 0 && (num(solo.gross) ?? 0) > 0);

  async function submitAndSeeResults() {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        truck: { gvwr: num(truck.gvwr), front_gawr: num(truck.frontGawr), rear_gawr: num(truck.rearGawr), gcwr: num(truck.gcwr) },
        trailer: { gvwr: num(trailer.gvwr), gawr: num(trailer.gawr), axle_count: Math.round(num(trailer.axleCount) ?? 1), uvw: num(trailer.uvw) },
        combined: { steer: num(combined.steer), drive: num(combined.drive), trailer_axle: num(combined.trailerAxle), gross: num(combined.gross) },
        solo: hasSolo ? { steer: num(solo.steer), drive: num(solo.drive), gross: num(solo.gross) } : null,
        time_gap_hours: hasSolo ? num(timeGapHours) : null,
      };
      const res = await evaluate(payload);
      setResult(res);
      setStep(4);
    } catch {
      setError('Could not reach the evaluation service. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function startOver() {
    setStep(0); setResult(null); setError(null);
    setTruck({ gvwr: '', frontGawr: '', rearGawr: '', gcwr: '' });
    setTrailer({ gvwr: '', gawr: '', axleCount: '2', uvw: '' });
    setCombined({ steer: '', drive: '', trailerAxle: '', gross: '' });
    setHasSolo(false); setSolo({ steer: '', drive: '', gross: '' }); setTimeGapHours('');
  }

  const segColor = (i: number) => (step >= i ? ORANGE : theme.border);

  return (
    <div style={{ minHeight: '100vh', background: theme.page, color: theme.text, fontFamily: 'var(--font-body)', transition: 'background .15s' }}>
      <Header theme={theme} mode={mode} onToggleTheme={() => setMode(m => (m === 'light' ? 'dark' : 'light'))} />

      {step === 0 && (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '8px 32px 44px', textAlign: 'center' }}>
          <h1 style={{ margin: '0 0 14px', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '2.4rem', lineHeight: 1.15 }}>Know before you tow.</h1>
          <p style={{ margin: '0 auto', maxWidth: 560, fontSize: '1.05rem', color: theme.text2, lineHeight: 1.55 }}>
            Enter your rig's ratings and a CAT Scale weigh ticket to see whether the Tow Vehicle and Trailer are within every legal weight limit. Fully offline — nothing is saved.
          </p>
        </div>
      )}

      <main style={{ maxWidth: 560, margin: '0 auto', padding: '0 24px 64px' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: segColor(i) }} />
          ))}
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.75rem', color: theme.text2, marginTop: 6 }}>Step {step + 1} of 5</div>

        <div style={{ marginTop: 20, background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: 24, padding: '36px 40px', boxShadow: '0 12px 40px rgba(0,0,0,0.06)' }}>
          {step === 0 && (
            <>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Tow Vehicle ratings</h2>
              <p style={{ margin: '8px 0 22px', fontSize: '0.92rem', color: theme.text2, lineHeight: 1.55 }}>From the Tow Vehicle's certification label, plus its GCWR from the owner's manual (never printed on a tag).</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={labelStyle(theme)}>GVWR (lb)</label>
                  <input type="number" inputMode="decimal" placeholder="e.g. 10000" value={truck.gvwr} onChange={e => setTruck({ ...truck, gvwr: e.target.value })} style={inputStyle(theme)} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={labelStyle(theme)}>GCWR (lb) — optional</label>
                  <input type="number" inputMode="decimal" placeholder="leave blank if not on file" value={truck.gcwr} onChange={e => setTruck({ ...truck, gcwr: e.target.value })} style={inputStyle(theme)} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={labelStyle(theme)}>Front GAWR (lb)</label>
                  <input type="number" inputMode="decimal" placeholder="e.g. 4500" value={truck.frontGawr} onChange={e => setTruck({ ...truck, frontGawr: e.target.value })} style={inputStyle(theme)} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={labelStyle(theme)}>Rear GAWR (lb)</label>
                  <input type="number" inputMode="decimal" placeholder="e.g. 6500" value={truck.rearGawr} onChange={e => setTruck({ ...truck, rearGawr: e.target.value })} style={inputStyle(theme)} />
                </div>
              </div>
              <button disabled={!valid0} onClick={() => setStep(1)} style={{ marginTop: 26, width: '100%', height: 50, borderRadius: 999, border: 'none', background: ORANGE, color: '#fff', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', cursor: 'pointer', opacity: valid0 ? 1 : 0.5 }}>Next</button>
            </>
          )}

          {step === 1 && (
            <>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Trailer ratings</h2>
              <p style={{ margin: '8px 0 22px', fontSize: '0.92rem', color: theme.text2, lineHeight: 1.55 }}>From the Trailer's certification label. GAWR is the single per-axle figure; Axle Count multiplies it into a group rating comparable to the Trailer Axle reading on a CAT Scale Ticket.</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>GVWR (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 9500" value={trailer.gvwr} onChange={e => setTrailer({ ...trailer, gvwr: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>GAWR per axle (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 5200" value={trailer.gawr} onChange={e => setTrailer({ ...trailer, gawr: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Axle Count</label><input type="number" min={1} max={10} step={1} value={trailer.axleCount} onChange={e => setTrailer({ ...trailer, axleCount: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>UVW (lb) — optional</label><input type="number" inputMode="decimal" placeholder="leave blank if unknown" value={trailer.uvw} onChange={e => setTrailer({ ...trailer, uvw: e.target.value })} style={inputStyle(theme)} /></div>
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 26 }}>
                <button onClick={() => setStep(0)} style={{ width: 120, height: 50, flex: 'none', borderRadius: 999, border: `2px solid ${GREEN}`, background: 'transparent', color: theme.linkStrong, fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}>Back</button>
                <button disabled={!valid1} onClick={() => setStep(2)} style={{ flex: 1, height: 50, borderRadius: 999, border: 'none', background: ORANGE, color: '#fff', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', cursor: 'pointer', opacity: valid1 ? 1 : 0.5 }}>Next</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Combined Ticket</h2>
              <p style={{ margin: '8px 0 22px', fontSize: '0.92rem', color: theme.text2, lineHeight: 1.55 }}>The CAT Scale Ticket from weighing the Tow Vehicle and Trailer hitched together.</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Steer Axle (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 4300" value={combined.steer} onChange={e => setCombined({ ...combined, steer: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Drive Axle (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 6100" value={combined.drive} onChange={e => setCombined({ ...combined, drive: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Trailer Axle group (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 9200" value={combined.trailerAxle} onChange={e => setCombined({ ...combined, trailerAxle: e.target.value })} style={inputStyle(theme)} /></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Gross Weight (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 19600" value={combined.gross} onChange={e => setCombined({ ...combined, gross: e.target.value })} style={inputStyle(theme)} /></div>
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 26 }}>
                <button onClick={() => setStep(1)} style={{ width: 120, height: 50, flex: 'none', borderRadius: 999, border: `2px solid ${GREEN}`, background: 'transparent', color: theme.linkStrong, fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}>Back</button>
                <button disabled={!valid2} onClick={() => setStep(3)} style={{ flex: 1, height: 50, borderRadius: 999, border: 'none', background: ORANGE, color: '#fff', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', cursor: 'pointer', opacity: valid2 ? 1 : 0.5 }}>Next</button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Solo Ticket (optional)</h2>
              <p style={{ margin: '8px 0 18px', fontSize: '0.92rem', color: theme.text2, lineHeight: 1.55 }}>If you also weighed the Tow Vehicle alone on the same trip, add that ticket: it lets the Trailer GVWR check run off the Derived Trailer Weight. Skip it and that one check is reported as Not Evaluated.</p>
              <label style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', padding: 14, borderRadius: 12, background: theme.surfaceSunken }}>
                <input type="checkbox" checked={hasSolo} onChange={() => setHasSolo(v => !v)} style={{ width: 20, height: 20, accentColor: ORANGE, flex: 'none' }} />
                <span style={{ fontSize: '0.92rem' }}>I also weighed the truck alone</span>
              </label>
              {hasSolo ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Solo Steer Axle (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 4300" value={solo.steer} onChange={e => setSolo({ ...solo, steer: e.target.value })} style={inputStyle(theme)} /></div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Solo Drive Axle (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 6200" value={solo.drive} onChange={e => setSolo({ ...solo, drive: e.target.value })} style={inputStyle(theme)} /></div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Solo Gross Weight (lb)</label><input type="number" inputMode="decimal" placeholder="e.g. 10500" value={solo.gross} onChange={e => setSolo({ ...solo, gross: e.target.value })} style={inputStyle(theme)} /></div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}><label style={labelStyle(theme)}>Hours between weighings — optional</label><input type="number" inputMode="decimal" placeholder="leave blank if unknown" value={timeGapHours} onChange={e => setTimeGapHours(e.target.value)} style={inputStyle(theme)} /></div>
                </div>
              ) : (
                <p style={{ margin: '10px 0 0', fontSize: '0.8rem', color: theme.text2 }}>Leave the box above unchecked to go straight to the results.</p>
              )}
              {error && <p style={{ marginTop: 14, fontSize: '0.85rem', color: '#a8402f' }}>{error}</p>}
              <div style={{ display: 'flex', gap: 12, marginTop: 26 }}>
                <button onClick={() => setStep(2)} style={{ width: 120, height: 50, flex: 'none', borderRadius: 999, border: `2px solid ${GREEN}`, background: 'transparent', color: theme.linkStrong, fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}>Back</button>
                <button disabled={!valid3 || loading} onClick={submitAndSeeResults} style={{ flex: 1, height: 50, borderRadius: 999, border: 'none', background: ORANGE, color: '#fff', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', cursor: 'pointer', opacity: valid3 ? 1 : 0.5 }}>{loading ? 'Checking…' : 'See results'}</button>
              </div>
            </>
          )}

          {step === 4 && result && (
            <>
              <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.5rem' }}>Rig Evaluation</h2>
              <div style={{ marginTop: 16, padding: '16px 18px', borderRadius: 14, background: BANNER[mode][result.overall_status].bg, color: BANNER[mode][result.overall_status].text, fontSize: '0.95rem', lineHeight: 1.5, fontWeight: 500 }}>
                {BANNER_MESSAGE[result.overall_status]}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 20 }}>
                {result.checks.map((c, i) => <ResultBox key={i} check={c} />)}
              </div>
              {result.time_gap_hours != null && result.time_gap_exceeds_threshold && (
                <div style={{ marginTop: 16, padding: '14px 16px', borderRadius: 12, background: theme.infoBg, color: theme.infoText, fontSize: '0.85rem', lineHeight: 1.55 }}>
                  Time-Gap Warning (advisory): the two physical weighings were about {Math.abs(result.time_gap_hours)} hours apart. The Trailer may have gained or lost weight in between, so the Trailer GVWR box above is less reliable. This never changes the pass / fail results.
                </div>
              )}
              {result.time_gap_hours != null && !result.time_gap_exceeds_threshold && (
                <p style={{ margin: '14px 0 0', fontSize: '0.75rem', color: theme.text2 }}>The two physical weighings were about {Math.abs(result.time_gap_hours)} hours apart — within the Time-Gap threshold.</p>
              )}
              <p style={{ margin: '18px 0 0', fontSize: '0.72rem', color: theme.text2, lineHeight: 1.55 }}>{result.disclaimer}</p>
              <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
                <button onClick={() => setStep(3)} style={{ flex: 1, height: 50, borderRadius: 999, border: `2px solid ${GREEN}`, background: 'transparent', color: theme.linkStrong, fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}>Back</button>
                <button onClick={startOver} style={{ flex: 1, height: 50, borderRadius: 999, border: `1.5px solid ${theme.border}`, background: 'transparent', color: theme.text, fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer' }}>Start over</button>
              </div>
            </>
          )}
        </div>
      </main>

      <Footer theme={theme} />
    </div>
  );
}
