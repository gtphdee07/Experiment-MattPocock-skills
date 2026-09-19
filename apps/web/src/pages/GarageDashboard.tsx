import { useEffect, useState } from 'react';
import Card from '../components/Card';
import { ConfirmDeleteButton } from '../components/form/ConfirmDeleteButton';
import TruckProfileForm from '../components/garage/TruckProfileForm';
import TrailerProfileForm from '../components/garage/TrailerProfileForm';
import { useAppTheme } from '../theme/ThemeContext';
import * as api from '../api';
import type { TrailerProfile, TrailerProfileIn, TruckProfile, TruckProfileIn } from '../types';

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  padding: '12px 0',
  borderBottom: '1px solid rgba(0,0,0,0.08)',
} as const;

/** Signed-in Account's Garage: every Truck/Trailer Profile (Story 9/14),
 * add/edit/delete for both (Story 10/12/13/14/15). */
export default function GarageDashboard() {
  const { theme } = useAppTheme();
  const [trucks, setTrucks] = useState<TruckProfile[] | null>(null);
  const [trailers, setTrailers] = useState<TrailerProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [addingTruck, setAddingTruck] = useState(false);
  const [editingTruckId, setEditingTruckId] = useState<number | null>(null);
  const [addingTrailer, setAddingTrailer] = useState(false);
  const [editingTrailerId, setEditingTrailerId] = useState<number | null>(null);

  async function loadAll() {
    try {
      const [truckList, trailerList] = await Promise.all([api.listTrucks(), api.listTrailers()]);
      setTrucks(truckList);
      setTrailers(trailerList);
    } catch {
      setLoadError('Could not load your Garage. Please try again.');
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function handleCreateTruck(payload: TruckProfileIn) {
    const created = await api.createTruck(payload);
    setTrucks((prev) => (prev ? [...prev, created] : [created]));
    setAddingTruck(false);
  }

  async function handleUpdateTruck(id: number, payload: TruckProfileIn) {
    const updated = await api.updateTruck(id, payload);
    setTrucks((prev) => (prev ? prev.map((t) => (t.id === id ? updated : t)) : prev));
    setEditingTruckId(null);
  }

  async function handleDeleteTruck(id: number) {
    try {
      await api.deleteTruck(id);
    } catch {
      // Story 30: a stale delete (already gone) still leaves a clean state -
      // drop it locally rather than leaving a dead row behind.
      setActionError('That Truck Profile was already removed.');
    } finally {
      setTrucks((prev) => (prev ? prev.filter((t) => t.id !== id) : prev));
    }
  }

  async function handleCreateTrailer(payload: TrailerProfileIn) {
    const created = await api.createTrailer(payload);
    setTrailers((prev) => (prev ? [...prev, created] : [created]));
    setAddingTrailer(false);
  }

  async function handleUpdateTrailer(id: number, payload: TrailerProfileIn) {
    const updated = await api.updateTrailer(id, payload);
    setTrailers((prev) => (prev ? prev.map((t) => (t.id === id ? updated : t)) : prev));
    setEditingTrailerId(null);
  }

  async function handleDeleteTrailer(id: number) {
    try {
      await api.deleteTrailer(id);
    } catch {
      setActionError('That Trailer Profile was already removed.');
    } finally {
      setTrailers((prev) => (prev ? prev.filter((t) => t.id !== id) : prev));
    }
  }

  return (
    <div>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.8rem' }}>Your Garage</h1>
      {loadError && <p role="alert" style={{ color: '#a8402f' }}>{loadError}</p>}
      {actionError && <p role="alert" style={{ color: '#a8402f' }}>{actionError}</p>}

      <Card theme={theme}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>Truck Profiles</h2>
          {!addingTruck && (
            <button
              onClick={() => setAddingTruck(true)}
              style={{ border: 'none', background: 'transparent', color: theme.linkStrong, fontWeight: 700, cursor: 'pointer' }}
            >
              + Add Truck
            </button>
          )}
        </div>

        {addingTruck && (
          <div style={{ marginTop: 16 }}>
            <TruckProfileForm
              submitLabel="Add Truck"
              onSubmit={handleCreateTruck}
              onCancel={() => setAddingTruck(false)}
            />
          </div>
        )}

        {trucks === null ? (
          <p style={{ color: theme.text2 }}>Loading…</p>
        ) : trucks.length === 0 ? (
          <p style={{ color: theme.text2, marginTop: 12 }}>No Truck Profiles yet.</p>
        ) : (
          <div style={{ marginTop: 12 }}>
            {trucks.map((truck) =>
              editingTruckId === truck.id ? (
                <div key={truck.id} style={{ padding: '14px 0', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
                  <TruckProfileForm
                    initial={truck}
                    submitLabel="Save changes"
                    onSubmit={(payload) => handleUpdateTruck(truck.id, payload)}
                    onCancel={() => setEditingTruckId(null)}
                  />
                </div>
              ) : (
                <div key={truck.id} style={rowStyle}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{truck.nickname}</div>
                    <div style={{ fontSize: '0.8rem', color: theme.text2 }}>
                      GVWR {truck.gvwr} · Front GAWR {truck.front_gawr} · Rear GAWR {truck.rear_gawr}
                      {truck.gcwr != null ? ` · GCWR ${truck.gcwr}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => setEditingTruckId(truck.id)}
                      style={{ border: `1.5px solid ${theme.border}`, background: 'transparent', color: theme.text, borderRadius: 999, padding: '6px 14px', cursor: 'pointer' }}
                    >
                      Edit
                    </button>
                    <ConfirmDeleteButton theme={theme} label="Delete" onConfirm={() => void handleDeleteTruck(truck.id)} />
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </Card>

      <Card theme={theme}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: '1.25rem' }}>Trailer Profiles</h2>
          {!addingTrailer && (
            <button
              onClick={() => setAddingTrailer(true)}
              style={{ border: 'none', background: 'transparent', color: theme.linkStrong, fontWeight: 700, cursor: 'pointer' }}
            >
              + Add Trailer
            </button>
          )}
        </div>

        {addingTrailer && (
          <div style={{ marginTop: 16 }}>
            <TrailerProfileForm
              submitLabel="Add Trailer"
              onSubmit={handleCreateTrailer}
              onCancel={() => setAddingTrailer(false)}
            />
          </div>
        )}

        {trailers === null ? (
          <p style={{ color: theme.text2 }}>Loading…</p>
        ) : trailers.length === 0 ? (
          <p style={{ color: theme.text2, marginTop: 12 }}>No Trailer Profiles yet.</p>
        ) : (
          <div style={{ marginTop: 12 }}>
            {trailers.map((trailer) =>
              editingTrailerId === trailer.id ? (
                <div key={trailer.id} style={{ padding: '14px 0', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
                  <TrailerProfileForm
                    initial={trailer}
                    submitLabel="Save changes"
                    onSubmit={(payload) => handleUpdateTrailer(trailer.id, payload)}
                    onCancel={() => setEditingTrailerId(null)}
                  />
                </div>
              ) : (
                <div key={trailer.id} style={rowStyle}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{trailer.nickname}</div>
                    <div style={{ fontSize: '0.8rem', color: theme.text2 }}>
                      GVWR {trailer.gvwr} · GAWR {trailer.gawr} · Axles {trailer.axle_count}
                      {trailer.uvw != null ? ` · UVW ${trailer.uvw}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => setEditingTrailerId(trailer.id)}
                      style={{ border: `1.5px solid ${theme.border}`, background: 'transparent', color: theme.text, borderRadius: 999, padding: '6px 14px', cursor: 'pointer' }}
                    >
                      Edit
                    </button>
                    <ConfirmDeleteButton theme={theme} label="Delete" onConfirm={() => void handleDeleteTrailer(trailer.id)} />
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
