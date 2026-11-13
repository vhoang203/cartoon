// Reusable cutout rig model shared by Hani and Mako.
// Angles: arms use 0° = hanging straight down, +90° = pointing screen-right,
// -90° = screen-left, ±180° = straight up. Lengths are multiples of the
// character's base arm length.
import { clamp, deg, lerp, rad, type Pt } from './anim.ts';

export type CharId = 'hani' | 'mako';

export type ArmP = { angle: number; len: number; bend: number };

export type CharParams = {
  x: number; // world seat position (bottom centre)
  y: number;
  hop: number; // vertical offset in px (negative = up)
  squash: number; // 1 normal, <1 squashed, >1 stretched
  lean: number; // body rotation in degrees (+ = clockwise / toward screen-right)
  headTilt: number;
  headY: number; // head offset (nods)
  turn: number; // -1..1, shifts the face for a 3/4 feel
  armL: ArmP; // screen-left arm
  armR: ArmP; // screen-right arm
  browY: number; // -1 raised .. +1 lowered
  browTilt: number; // + = worried/soft (inner ends up), - = determined
  eyeOpen: number; // 0 closed .. 1 open .. 1.2 wide
  happyEyes: number; // 0..1 blend to ^ ^ closed happy eyes
  smile: number; // -1..1
  mouthOpen: number; // 0..1 (speech adds on top)
  mouthRound: number; // 0..1 "o" shape
  earL: number; // degrees
  earR: number;
  earFold: number; // Hani's signature folded right-ear tip (degrees)
  blush: number; // 0..1
  lookX: number; // -1..1 pupil direction
  lookY: number;
};

export type CharSpec = {
  id: CharId;
  shoulderL: Pt; // local, relative to seat
  shoulderR: Pt;
  neck: Pt;
  headC: Pt;
  armBase: number;
  frontArm: 'armL' | 'armR'; // arm that is drawn in front of props (toward the partner)
};

export const SPECS: Record<CharId, CharSpec> = {
  hani: {
    id: 'hani',
    shoulderL: { x: -58, y: -108 },
    shoulderR: { x: 58, y: -108 },
    neck: { x: 0, y: -118 },
    headC: { x: 0, y: -190 },
    armBase: 120,
    frontArm: 'armR',
  },
  mako: {
    id: 'mako',
    shoulderL: { x: -66, y: -100 },
    shoulderR: { x: 66, y: -100 },
    neck: { x: 0, y: -116 },
    headC: { x: 0, y: -192 },
    armBase: 112,
    frontArm: 'armL',
  },
};

const A = (angle: number, len = 0.85, bend = 0.15): ArmP => ({ angle, len, bend });

export const BASE: CharParams = {
  x: 0,
  y: 0,
  hop: 0,
  squash: 1,
  lean: 0,
  headTilt: 0,
  headY: 0,
  turn: 0,
  armL: A(-15),
  armR: A(15),
  browY: 0,
  browTilt: 0,
  eyeOpen: 1,
  happyEyes: 0,
  smile: 0.5,
  mouthOpen: 0,
  mouthRound: 0,
  earL: -10,
  earR: 12,
  earFold: 48,
  blush: 0.6,
  lookX: 0,
  lookY: 0,
};

/** Arm spec in a pose: explicit angle, or a local point the paw should reach. */
export type ArmSpec = ArmP | { local: Pt; bend?: number };

export type PoseDef = {
  armL?: ArmSpec;
  armR?: ArmSpec;
  lean?: number;
  headTilt?: number;
  wave?: 'armL' | 'armR'; // procedural waving on this arm
};

// Body/arm poses. "Near" = toward the partner (Hani: right, Mako: left).
// Poses are written for Hani (partner on screen-right) and mirrored for Mako.
const HANI_POSES: Record<string, PoseDef> = {
  listen: { armL: A(38, 0.62, 0.35), armR: A(-38, 0.62, -0.35), headTilt: 3 }, // paws on tummy
  rest: { armL: A(-14, 0.85), armR: A(-38, 0.62, -0.35) },
  speak: { armL: A(-62, 0.82, 0.25), armR: A(55, 0.78, -0.25), headTilt: -2 },
  speakBig: { armL: A(-120, 0.85, 0.2), armR: A(115, 0.85, -0.2), headTilt: -3 },
  point: { armL: A(-14, 0.85), armR: A(70, 1.05, -0.05) },
  think: { armL: A(38, 0.6, 0.35), armR: { local: { x: 26, y: -126 }, bend: -0.6 }, headTilt: 7 },
  surprise: { armL: A(-48, 0.85, 0.3), armR: A(48, 0.85, -0.3), headTilt: -2 },
  happy: { armL: A(-140, 0.9, 0.15), armR: A(140, 0.9, -0.15), headTilt: 0 },
  reach: { armL: A(-14, 0.85), armR: A(60, 1.0, 0) },
  wave: { armL: A(-150, 0.95, 0.2), armR: A(-38, 0.62, -0.35), wave: 'armL' },
  idea: { armL: A(38, 0.6, 0.35), armR: A(168, 0.95, -0.1), headTilt: -4 },
  earFix: { armL: { local: { x: -30, y: -262 }, bend: 0.4 }, armR: A(-38, 0.62, -0.35), headTilt: -6 },
  carryBowl: { armL: { local: { x: -150, y: -44 } }, armR: { local: { x: 150, y: -44 } } },
  ready: { armL: A(-128, 0.82, 0.25), armR: A(128, 0.82, -0.25), headTilt: -2 }, // paws up, clear of the bowl
  open: { armL: A(-60, 0.74, 0.2), armR: A(60, 0.74, -0.2) },
};

const mirrorArm = (a: ArmSpec | undefined): ArmSpec | undefined => {
  if (!a) return a;
  if ('local' in a) return { local: { x: -a.local.x, y: a.local.y }, bend: a.bend === undefined ? undefined : -a.bend };
  return { angle: -a.angle, len: a.len, bend: -a.bend };
};

export const poseFor = (id: CharId, name: string): PoseDef => {
  const p = HANI_POSES[name];
  if (!p) throw new Error(`unknown pose ${name}`);
  if (id === 'hani') return p;
  return {
    armL: mirrorArm(p.armR),
    armR: mirrorArm(p.armL),
    lean: p.lean === undefined ? undefined : -p.lean,
    headTilt: p.headTilt === undefined ? undefined : -p.headTilt,
    wave: p.wave === 'armL' ? 'armR' : p.wave === 'armR' ? 'armL' : undefined,
  };
};

export type ExprDef = Partial<
  Pick<CharParams, 'browY' | 'browTilt' | 'eyeOpen' | 'happyEyes' | 'smile' | 'mouthOpen' | 'mouthRound' | 'earL' | 'earR' | 'blush'>
>;

export const EXPRS: Record<string, ExprDef> = {
  neutral: { browY: 0, browTilt: 0, eyeOpen: 1, happyEyes: 0, smile: 0.35, mouthOpen: 0, mouthRound: 0, earL: -10, earR: 12 },
  smile: { browY: -0.1, browTilt: 0.1, eyeOpen: 1, happyEyes: 0, smile: 0.8, mouthOpen: 0, mouthRound: 0, earL: -9, earR: 11 },
  happy: { browY: -0.45, browTilt: 0.2, eyeOpen: 1, happyEyes: 1, smile: 1, mouthOpen: 0.45, mouthRound: 0, earL: -6, earR: 8, blush: 0.9 },
  delighted: { browY: -0.6, browTilt: 0.15, eyeOpen: 1.1, happyEyes: 0, smile: 1, mouthOpen: 0.55, mouthRound: 0, earL: -4, earR: 6, blush: 0.9 },
  surprise: { browY: -0.95, browTilt: 0.1, eyeOpen: 1.22, happyEyes: 0, smile: 0, mouthOpen: 0.4, mouthRound: 1, earL: -3, earR: 4 },
  think: { browY: 0.15, browTilt: -0.35, eyeOpen: 0.92, happyEyes: 0, smile: 0.1, mouthOpen: 0, mouthRound: 0, earL: -16, earR: 20 },
  curious: { browY: -0.35, browTilt: 0.25, eyeOpen: 1.05, happyEyes: 0, smile: 0.45, mouthOpen: 0, mouthRound: 0, earL: -8, earR: 10 },
  oops: { browY: -0.2, browTilt: 0.75, eyeOpen: 1.05, happyEyes: 0, smile: -0.1, mouthOpen: 0.1, mouthRound: 0.3, earL: -22, earR: 26 },
  calm: { browY: 0.05, browTilt: 0.15, eyeOpen: 0.88, happyEyes: 0, smile: 0.55, mouthOpen: 0, mouthRound: 0, earL: -10, earR: 12 },
  kind: { browY: -0.2, browTilt: 0.45, eyeOpen: 0.95, happyEyes: 0, smile: 0.85, mouthOpen: 0, mouthRound: 0, earL: -9, earR: 11 },
  laugh: { browY: -0.5, browTilt: 0.3, eyeOpen: 1, happyEyes: 1, smile: 1, mouthOpen: 0.6, mouthRound: 0, earL: -8, earR: 10, blush: 1 },
};

/** Shoulder world position for a given param set. */
export const shoulderWorld = (spec: CharSpec, p: CharParams, side: 'armL' | 'armR'): Pt => {
  const s = side === 'armL' ? spec.shoulderL : spec.shoulderR;
  const sx = s.x;
  const sy = s.y * p.squash;
  const r = rad(p.lean);
  return {
    x: p.x + sx * Math.cos(r) - sy * Math.sin(r),
    y: p.y + p.hop + sx * Math.sin(r) + sy * Math.cos(r),
  };
};

/** Angle/len so that the paw reaches the world point (clamped to a believable reach). */
export const reachArm = (spec: CharSpec, p: CharParams, side: 'armL' | 'armR', target: Pt, bend = 0): ArmP => {
  const s = shoulderWorld(spec, p, side);
  const dx = target.x - s.x;
  const dy = target.y - s.y;
  const worldAngle = deg(Math.atan2(dx, dy));
  const len = clamp(Math.hypot(dx, dy) / spec.armBase, 0.42, 1.55);
  return { angle: worldAngle - p.lean, len, bend };
};

/** Resolve a local-space arm target into angle/len. */
export const localArm = (spec: CharSpec, side: 'armL' | 'armR', local: Pt, bend = 0): ArmP => {
  const s = side === 'armL' ? spec.shoulderL : spec.shoulderR;
  const dx = local.x - s.x;
  const dy = local.y - s.y;
  return { angle: deg(Math.atan2(dx, dy)), len: clamp(Math.hypot(dx, dy) / spec.armBase, 0.3, 1.62), bend };
};

/** Shortest-path angle interpolation. */
const lerpAngle = (a: number, b: number, t: number) => {
  let d = ((b - a + 540) % 360) - 180;
  return a + d * t;
};
export const lerpArm = (a: ArmP, b: ArmP, t: number): ArmP => ({
  angle: lerpAngle(a.angle, b.angle, t),
  len: lerp(a.len, b.len, t),
  bend: lerp(a.bend, b.bend, t),
});

export const lerpParams = (a: CharParams, b: CharParams, t: number): CharParams => {
  const out = { ...a } as CharParams;
  (Object.keys(a) as (keyof CharParams)[]).forEach((k) => {
    const va = a[k];
    const vb = b[k];
    if (typeof va === 'number' && typeof vb === 'number') (out as Record<string, unknown>)[k] = lerp(va, vb, t);
  });
  out.armL = lerpArm(a.armL, b.armL, t);
  out.armR = lerpArm(a.armR, b.armR, t);
  return out;
};

/** Paw position in local (unrotated) character space. */
export const pawLocal = (spec: CharSpec, side: 'armL' | 'armR', arm: ArmP, squash = 1): Pt => {
  const s = side === 'armL' ? spec.shoulderL : spec.shoulderR;
  const L = arm.len * spec.armBase;
  return { x: s.x + Math.sin(rad(arm.angle)) * L, y: s.y * squash + Math.cos(rad(arm.angle)) * L };
};
