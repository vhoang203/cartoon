// Small deterministic animation helpers (no randomness at render time).
export type Pt = { x: number; y: number };

export const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const easeInOut = (t: number) => {
  const x = clamp(t, 0, 1);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
export const easeOut = (t: number) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
export const easeIn = (t: number) => Math.pow(clamp(t, 0, 1), 3);
export const easeOutBack = (t: number, s = 1.6) => {
  const x = clamp(t, 0, 1) - 1;
  return 1 + (s + 1) * x * x * x + s * x * x;
};
/** 0..1 progress of f within [a, b). */
export const prog = (f: number, a: number, b: number) => (b <= a ? (f >= b ? 1 : 0) : clamp((f - a) / (b - a), 0, 1));

/** Deterministic pseudo-random in [0,1) from an integer seed. */
export const rand = (seed: number) => {
  let x = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
};

export const lerpPt = (a: Pt, b: Pt, t: number): Pt => ({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) });
/** Point along a parabolic arc from a to b that rises by h at the midpoint. */
export const arcPt = (a: Pt, b: Pt, t: number, h: number): Pt => ({
  x: lerp(a.x, b.x, t),
  y: lerp(a.y, b.y, t) - Math.sin(Math.PI * clamp(t, 0, 1)) * h,
});
export const dist = (a: Pt, b: Pt) => Math.hypot(b.x - a.x, b.y - a.y);
export const deg = (r: number) => (r * 180) / Math.PI;
export const rad = (d: number) => (d * Math.PI) / 180;
