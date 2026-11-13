// World layout for Episode 01 (world units = pixels at camera zoom 1).
import type { Pt } from '../lib/anim';
import type { CharId } from '../lib/rig';

export type SId = 'S1' | 'S2' | 'S3' | 'S4' | 'S5' | 'S6';
export const SIDS: SId[] = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'];

export type Loc = { kind: 'bowl'; slot: number } | { kind: 'plate'; owner: CharId; slot: number };

export const SEAT: Record<CharId, Pt> = { hani: { x: 700, y: 905 }, mako: { x: 1220, y: 905 } };
export const BOWL_SPOT: Pt = { x: 960, y: 850 }; // Hani kneels behind the bowl to share
export const OFF_LEFT: Pt = { x: -300, y: 905 };
export const BOWL_REST: Pt = { x: 960, y: 800 };
export const BOWL_CARRY_OFFSET: Pt = { x: 0, y: -50 }; // relative to Hani while carrying

// Hani's plate stays screen-left, Mako's plate stays screen-right.
export const PLATE: Record<CharId, Pt> = { hani: { x: 800, y: 935 }, mako: { x: 1120, y: 935 } };
export const PLATE_SLOTS: Record<CharId, number[]> = {
  hani: [-75, -25, 25, 75],
  mako: [-50, 0, 50],
};
export const BERRY_ON_PLATE_DY = -14;
export const BERRY_IN_BOWL_DY = -8;
export const BOWL_SLOTS = [-125, -75, -25, 25, 75, 125];

export const INITIAL: Record<SId, Loc> = {
  S1: { kind: 'bowl', slot: 0 },
  S2: { kind: 'bowl', slot: 1 },
  S3: { kind: 'bowl', slot: 2 },
  S4: { kind: 'bowl', slot: 3 },
  S5: { kind: 'bowl', slot: 4 },
  S6: { kind: 'bowl', slot: 5 },
};

export const BADGE_POS: Record<CharId, Pt> = { hani: { x: 800, y: 1016 }, mako: { x: 1120, y: 1016 } };
export const THOUGHT_POS: Record<CharId, Pt> = { hani: { x: 548, y: 640 }, mako: { x: 1372, y: 640 } };
export const HANDOFF_PT: Pt = { x: 968, y: 852 };

export type Shot = { cx: number; cy: number; z: number };
export const SHOTS = {
  WIDE: { cx: 960, cy: 580, z: 1.0 },
  WIDE2: { cx: 960, cy: 690, z: 1.18 },
  TWO: { cx: 960, cy: 735, z: 1.42 },
  TABLE: { cx: 960, cy: 812, z: 1.85 },
  HANI_CU: { cx: 800, cy: 735, z: 1.8 },
  MAKO_CU: { cx: 1110, cy: 680, z: 1.8 },
} satisfies Record<string, Shot>;
export type ShotName = keyof typeof SHOTS;

export const bowlSlotPos = (bowl: Pt, slot: number): Pt => ({ x: bowl.x + BOWL_SLOTS[slot], y: bowl.y + BERRY_IN_BOWL_DY });
export const plateSlotPos = (owner: CharId, slot: number): Pt => ({
  x: PLATE[owner].x + PLATE_SLOTS[owner][slot],
  y: PLATE[owner].y + BERRY_ON_PLATE_DY,
});
