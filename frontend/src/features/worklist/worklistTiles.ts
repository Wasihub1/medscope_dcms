/**
 * Prompt 10E Part 8: the /worklist Bento tiles are filters.
 * Pure mapping logic (no React) so it can be checked on its own.
 *
 * - Clicking a tile applies the same filter as the matching status tab.
 * - Clicking the active tile again clears it (back to "All Tasks").
 * - The "Urgent STAT" tile toggles the urgent-only switch and keeps the status filter.
 * Tiles never carry money (technician-safe counts from /worklist/summary only).
 */
export type WorklistTileId =
  | 'ALL'
  | 'URGENT'
  | 'SAMPLE_PENDING'
  | 'IN_PROGRESS'
  | 'AWAITING_DOCTOR'
  | 'REJECTED'
  | 'LATE'
  | 'READY'
  | 'UNASSIGNED'
  | 'COMPLETED';

export interface WorklistFilterState {
  statusFilter: string;
  urgentOnly: boolean;
}

export interface WorklistTileDef {
  id: WorklistTileId;
  label: string;
  /** Summary field holding the tile count */
  countKey: string;
  /** Status filter the tile applies (null = the urgent toggle) */
  status: string | null;
}

export const WORKLIST_TILES: WorklistTileDef[] = [
  { id: 'ALL', label: 'Room Queue', countKey: 'total_assigned', status: 'ALL' },
  { id: 'URGENT', label: 'Urgent STAT', countKey: 'urgent_count', status: null },
  { id: 'SAMPLE_PENDING', label: 'Sample Pending', countKey: 'sample_pending_count', status: 'SAMPLE_PENDING' },
  { id: 'IN_PROGRESS', label: 'In Progress', countKey: 'in_progress_count', status: 'IN_PROGRESS' },
  { id: 'AWAITING_DOCTOR', label: 'Doctor Queue', countKey: 'awaiting_doctor_count', status: 'AWAITING_DOCTOR' },
  { id: 'REJECTED', label: 'Rejected / Spoil', countKey: 'rejected_count', status: 'REJECTED' },
  { id: 'LATE', label: 'Late Tasks', countKey: 'late_count', status: 'LATE' },
  { id: 'READY', label: 'Ready Reports', countKey: 'ready_count', status: 'READY' },
  { id: 'UNASSIGNED', label: 'Unassigned', countKey: 'unassigned_count', status: 'UNASSIGNED' },
  { id: 'COMPLETED', label: 'Completed', countKey: 'completed_count', status: 'COMPLETED' },
];

export const CLEARED_FILTERS: WorklistFilterState = { statusFilter: 'ALL', urgentOnly: false };

const tileById = (id: WorklistTileId): WorklistTileDef => {
  const t = WORKLIST_TILES.find((x) => x.id === id);
  if (!t) throw new Error(`Unknown worklist tile ${id}`);
  return t;
};

/** Whether a tile shows as active for the current filters (keeps tiles and tabs in sync). */
export const isTileActive = (id: WorklistTileId, state: WorklistFilterState): boolean => {
  const t = tileById(id);
  if (t.status === null) return state.urgentOnly;
  if (t.id === 'ALL') return state.statusFilter === 'ALL' && !state.urgentOnly;
  return state.statusFilter === t.status;
};

/** Next filter state after clicking a tile (click again = clear). */
export const applyTile = (id: WorklistTileId, state: WorklistFilterState): WorklistFilterState => {
  const t = tileById(id);
  if (t.status === null) return { ...state, urgentOnly: !state.urgentOnly };
  if (t.id === 'ALL') return { ...CLEARED_FILTERS };
  if (state.statusFilter === t.status) return { ...state, statusFilter: 'ALL' };
  return { ...state, statusFilter: t.status };
};

export const tileCount = (summary: Record<string, unknown> | null | undefined, id: WorklistTileId): number => {
  const v = summary ? summary[tileById(id).countKey] : 0;
  return typeof v === 'number' ? v : 0;
};
