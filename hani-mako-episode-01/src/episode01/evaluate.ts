// Evaluates the whole scene at one frame: camera, strawberries, characters,
// badges and overlays. Pure and deterministic.
import { arcPt, clamp, easeInOut, easeOut, lerp, lerpPt, prog, rand, type Pt } from '../lib/anim.ts';
import {
  BASE,
  EXPRS,
  SPECS,
  lerpArm,
  lerpParams,
  localArm,
  poseFor,
  reachArm,
  type ArmP,
  type CharId,
  type CharParams,
} from '../lib/rig.ts';
import type { Target } from './cues.ts';
import {
  BOWL_CARRY_OFFSET,
  BOWL_REST,
  HANDOFF_PT,
  OFF_LEFT,
  PLATE,
  SHOTS,
  SIDS,
  bowlSlotPos,
  plateSlotPos,
  type Loc,
  type SId,
  type Shot,
} from './layout.ts';
import { berryStates, type CharKey, type Manifest, type Timeline } from './timeline.ts';

export type BerryView = { id: SId; x: number; y: number; rot: number; layer: 'bowl' | 'plate' | 'top'; glow: number; scale: number };
export type TagView = { id: SId; n: number; x: number; y: number; opacity: number; scale: number; who: CharId };
export type BadgeView = { who: CharId; n: number; opacity: number; scale: number };
export type CharView = { p: CharParams; behindBowl: boolean; armsInFront: boolean };
export type SceneView = {
  camera: Shot;
  bowl: Pt;
  berries: BerryView[];
  tags: TagView[];
  badges: BadgeView[];
  chars: Record<CharId, CharView>;
  overlays: { kind: string; p: number; age: number; left: number }[];
  speaking: Record<CharId, boolean>;
};

// ─────────────────────────────── camera
const cameraAt = (tl: Timeline, f: number): Shot => {
  let cur: Shot = SHOTS.WIDE;
  for (const k of tl.shots) {
    if (k.frame > f) break;
    const from = cur;
    const target = SHOTS[k.shot];
    if (k.ease > 0 && f < k.frame + k.ease) {
      const t = easeInOut((f - k.frame) / k.ease);
      cur = { cx: lerp(from.cx, target.cx, t), cy: lerp(from.cy, target.cy, t), z: lerp(from.z, target.z, t) };
      return cur;
    }
    cur = target;
  }
  return cur;
};

// ─────────────────────────────── positions / moves
type PosState = { x: number; y: number; hop: number; squash: number };
const posAt = (tl: Timeline, who: CharId, f: number, start: Pt): PosState => {
  let p: Pt = start;
  for (const m of tl.moves[who]) {
    if (f < m.start) break;
    if (f >= m.end) {
      p = m.to;
      continue;
    }
    const t = prog(f, m.start, m.end);
    if (m.hops > 0) {
      const s = Math.abs(Math.sin(Math.PI * m.hops * t));
      return { x: lerp(m.from.x, m.to.x, t), y: lerp(m.from.y, m.to.y, t), hop: -s * 40, squash: s < 0.25 ? 0.93 : 1.03 };
    }
    const e = easeInOut(t);
    return { x: lerp(m.from.x, m.to.x, e), y: lerp(m.from.y, m.to.y, e), hop: 0, squash: 1 };
  }
  return { x: p.x, y: p.y, hop: 0, squash: 1 };
};

const bowlAt = (tl: Timeline, f: number): Pt => {
  if (f >= tl.bowlPlacedFrame) return BOWL_REST;
  const h = posAt(tl, 'hani', f, OFF_LEFT);
  return { x: h.x + BOWL_CARRY_OFFSET.x, y: h.y + h.hop + BOWL_CARRY_OFFSET.y };
};

// ─────────────────────────────── strawberries
const locPos = (loc: Loc, bowl: Pt): Pt => (loc.kind === 'bowl' ? bowlSlotPos(bowl, loc.slot) : plateSlotPos(loc.owner, loc.slot));

const berryPos = (tl: Timeline, id: SId, f: number, bowl: Pt): { pt: Pt; rot: number; layer: BerryView['layer'] } => {
  const st = berryStates(tl, f).find((b) => b.id === id)!;
  if (st.at !== 'moving') return { pt: locPos(st.loc, bowl), rot: 0, layer: st.at };
  const tr = tl.transfers.find((t) => t.id === id && f >= t.ph[1] && f < t.end)!;
  const src = locPos(tr.from, bowl);
  const dst = locPos(tr.to, bowl);
  if (tr.style === 'toss') {
    const t = prog(f, tr.ph[1], tr.ph[2]);
    const h = 70 + Math.hypot(dst.x - src.x, dst.y - src.y) * 0.22;
    const e = 0.5 - 0.5 * Math.cos(Math.PI * t);
    return { pt: arcPt(src, dst, e, h), rot: Math.sin(t * Math.PI) * 22, layer: 'top' };
  }
  const [, b, c, d, e] = tr.ph;
  if (f < c) return { pt: arcPt(src, HANDOFF_PT, easeInOut(prog(f, b, c)), 46), rot: 0, layer: 'top' };
  if (f < d) return { pt: { x: HANDOFF_PT.x, y: HANDOFF_PT.y - Math.sin(prog(f, c, d) * Math.PI) * 4 }, rot: 0, layer: 'top' };
  if (f < e) return { pt: arcPt(HANDOFF_PT, dst, easeInOut(prog(f, d, e)), 30), rot: 0, layer: 'top' };
  return { pt: dst, rot: 0, layer: 'top' };
};

const movingBerry = (tl: Timeline, f: number, bowl: Pt): Pt | null => {
  const tr = tl.transfers.find((t) => f >= t.start - 6 && f < t.end + 4);
  if (!tr) return null;
  return berryPos(tl, tr.id, Math.max(f, tr.start), bowl).pt;
};

// ─────────────────────────────── characters
const headPos = (who: CharId, pos: PosState): Pt => ({ x: pos.x, y: pos.y + pos.hop + SPECS[who].headC.y });

type Ctx = { tl: Timeline; f: number; bowl: Pt; berries: Record<SId, Pt>; moving: Pt | null; pos: Record<CharId, PosState> };

const targetPt = (t: Target, ctx: Ctx, who: CharId): Pt | 'camera' | 'up' => {
  if (typeof t === 'object') return t;
  switch (t) {
    case 'camera':
    case 'up':
      return t;
    case 'hani':
    case 'mako':
      return headPos(t, ctx.pos[t]);
    case 'bowl':
      return { x: ctx.bowl.x, y: ctx.bowl.y - 10 };
    case 'plateH':
      return { x: PLATE.hani.x, y: PLATE.hani.y - 22 };
    case 'plateM':
      return { x: PLATE.mako.x, y: PLATE.mako.y - 22 };
    case 'offLeft':
      return { x: -200, y: 700 };
    case 'moving':
      return ctx.moving ?? { x: ctx.bowl.x, y: ctx.bowl.y };
    default: {
      const [kind, id] = t.split(':') as ['berry' | 'tap', SId];
      const b = ctx.berries[id];
      void who;
      return kind === 'tap' ? { x: b.x + 4, y: b.y - 30 } : b;
    }
  }
};

const resolveKey = (who: CharId, key: CharKey, ctx: Ctx): CharParams => {
  const spec = SPECS[who];
  const pos = ctx.pos[who];
  const ex = EXPRS[key.expr] ?? EXPRS.neutral;
  const pose = poseFor(who, key.pose);
  let p: CharParams = { ...BASE, ...ex, x: pos.x, y: pos.y, hop: pos.hop, squash: pos.squash };
  if (who === 'mako') p = { ...p, earFold: 0 };
  const arm = (side: 'armL' | 'armR'): ArmP => {
    const a = pose[side];
    if (!a) return BASE[side];
    if ('local' in a) return localArm(spec, side, a.local, a.bend ?? 0);
    return a;
  };
  p.armL = arm('armL');
  p.armR = arm('armR');
  if (pose.lean !== undefined) p.lean = pose.lean;
  if (pose.headTilt !== undefined) p.headTilt = pose.headTilt;
  Object.assign(p, key.over);
  // gaze
  const hp = headPos(who, pos);
  const tp = targetPt(key.look, ctx, who);
  if (tp === 'camera') {
    p.lookX = 0;
    p.lookY = 0.12;
    p.turn = 0;
  } else if (tp === 'up') {
    p.lookX = who === 'hani' ? -0.55 : -0.3;
    p.lookY = -0.9;
    p.turn = who === 'hani' ? -0.2 : 0;
  } else {
    const dx = tp.x - hp.x;
    const dy = tp.y - hp.y;
    p.lookX = clamp(dx / 240, -1, 1);
    p.lookY = clamp(dy / 210, -1, 1) * 0.85;
    p.turn = clamp(dx / 520, -0.65, 0.65);
  }
  // partner-side paw
  if (key.hand) {
    const hp2 = targetPt(key.hand, ctx, who);
    if (typeof hp2 === 'object') {
      // kneeling behind the bowl, Hani uses whichever paw is nearer
      const side = who === 'hani' && pos.y < 880 ? (hp2.x < pos.x ? 'armL' : 'armR') : spec.frontArm;
      p[side] = reachArm(spec, p, side, hp2, side === 'armR' ? -0.15 : 0.15);
    }
  }
  return p;
};

const BLINK = [0.55, 0.1, 0.05, 0.4, 0.85];
const blinkAt = (who: CharId, f: number) => {
  const seed = who === 'hani' ? 1 : 2;
  let start = who === 'hani' ? 40 : 70;
  for (let j = 0; ; j++) {
    const next = start + 84 + Math.floor(rand(j * 7 + seed) * 70);
    if (next > f) break;
    start = next;
  }
  const d = f - start;
  return d >= 0 && d < BLINK.length ? BLINK[d] : 1;
};

const evalChar = (who: CharId, ctx: Ctx, manifest: Manifest): { p: CharParams; speaking: boolean } => {
  const { tl, f } = ctx;
  const spec = SPECS[who];
  const keys = tl.keys[who];
  let ki = -1;
  for (let i = 0; i < keys.length; i++) if (keys[i].frame <= f) ki = i;
  // recursive blend so overlapping transitions never pop
  const valueAt = (i: number, depth: number): CharParams => {
    const b = resolveKey(who, keys[i], ctx);
    if (i === 0 || depth > 4) return b;
    const w = easeInOut((f - keys[i].frame) / keys[i].t);
    return w >= 1 ? b : lerpParams(valueAt(i - 1, depth + 1), b, w);
  };
  let p: CharParams = ki < 0 ? resolveKey(who, keys[0], ctx) : valueAt(ki, 0);
  const pose = poseFor(who, ki >= 0 ? keys[ki].pose : keys[0].pose);

  // transfers: the hand follows the strawberry it is handling
  for (const tr of tl.transfers) {
    if (f < tr.start || f > tr.end + 14) continue;
    let w = 0;
    let target: Pt | null = null;
    const berry = ctx.berries[tr.id];
    if (tr.style === 'toss' && tr.by === who) {
      const [a, b] = tr.ph;
      if (f < b) {
        w = easeOut(prog(f, a, b));
        target = { x: berry.x, y: berry.y + 6 };
      } else {
        w = 1 - easeInOut(prog(f, b, b + 13));
        target = locPos(tr.from, ctx.bowl);
        target = { x: target.x + (berry.x > target.x ? 16 : -16), y: target.y - 22 };
      }
    } else if (tr.style === 'handoff') {
      const [a, b, c, d, e, g] = tr.ph;
      if (tr.by === who) {
        if (f < b) w = easeOut(prog(f, a, b));
        else if (f < d) w = 1;
        else w = 1 - easeInOut(prog(f, d, d + 14));
        target = f < d ? { x: berry.x - 15, y: berry.y + 12 } : { x: HANDOFF_PT.x - 30, y: HANDOFF_PT.y + 10 };
      } else if (tr.receiver === who) {
        const r0 = b + Math.round((c - b) * 0.35);
        if (f < r0) w = 0;
        else if (f < c) w = easeInOut(prog(f, r0, c));
        else if (f < e) w = 1;
        else w = 1 - easeInOut(prog(f, e, g));
        target = f < c ? { x: HANDOFF_PT.x + 15, y: HANDOFF_PT.y + 12 } : { x: berry.x + 15, y: berry.y + 12 };
      }
    }
    if (w > 0 && target) {
      const side: 'armL' | 'armR' = who === 'hani' && p.y < 880 ? (target.x < p.x ? 'armL' : 'armR') : spec.frontArm;
      const dir = clamp((target.x - p.x) / 220, -1, 1);
      p = { ...p, x: p.x + dir * 34 * w, lean: p.lean + dir * 7 * w };
      p[side] = lerpArm(p[side], reachArm(spec, p, side, target, side === 'armR' ? -0.1 : 0.1), w);
    }
  }

  // waving
  if (pose.wave) {
    const s = Math.sin((f / 30) * Math.PI * 2 * 1.6);
    p[pose.wave] = { ...p[pose.wave], angle: p[pose.wave].angle + s * 16 };
  }

  // events
  for (const ev of tl.events[who]) {
    const d = f - ev.frame;
    if (d < 0) continue;
    if (ev.type === 'nod' && d < 24) p.headY += Math.sin(((d % 12) / 12) * Math.PI) * (d < 12 ? 9 : 4.5);
    if (ev.type === 'hop' && d < 16) {
      const t = d / 16;
      p.hop += -Math.sin(Math.PI * t) * 34;
      p.squash *= t < 0.1 || t > 0.9 ? 0.94 : 1.03;
    }
    if (ev.type === 'giggle' && d < 30) {
      const env = Math.sin((d / 30) * Math.PI);
      p.lean += Math.sin(d * 1.3) * 2.4 * env;
      p.headTilt += Math.sin(d * 1.3 + 1) * 2 * env;
    }
  }

  // speech: mouth driven by the clip's loudness envelope
  let speaking = false;
  for (const sp of tl.speech) {
    if (!sp.who.includes(who)) continue;
    const d = f - sp.start;
    if (d < 0 || d >= sp.frames) continue;
    const env = manifest.lines[sp.lineId]?.env[who]?.[d] ?? 0;
    speaking = true;
    p.mouthOpen = Math.max(env * 0.95, 0.04);
    p.mouthRound = 0.15 + rand(Math.floor(d / 4) + sp.start) * 0.55;
    p.headTilt += (env - 0.35) * 2.4;
    p.headY -= env * 2.5;
  }
  if (!speaking && p.mouthRound < 0.5) p.mouthOpen = Math.min(p.mouthOpen, 0.22);

  // blinking (not while eyes are already happy-closed)
  if (p.happyEyes < 0.5) p.eyeOpen *= blinkAt(who, f);

  // ears: gentle sway plus lag while hopping
  const prevHop = posAt(tl, who, f - 1, who === 'hani' ? OFF_LEFT : ctx.pos[who]).hop;
  const vy = p.hop - prevHop;
  p.earL += Math.sin(f / 23) * 1.5 - vy * 0.7;
  p.earR += Math.sin(f / 27 + 1) * 1.5 + vy * 0.7;
  return { p, speaking };
};

// ─────────────────────────────── scene
export const evaluate = (tl: Timeline, manifest: Manifest, f: number): SceneView => {
  const bowl = bowlAt(tl, f);
  const berries = {} as Record<SId, Pt>;
  const bviews: BerryView[] = [];
  for (const id of SIDS) {
    const b = berryPos(tl, id, f, bowl);
    berries[id] = b.pt;
    bviews.push({ id, x: b.pt.x, y: b.pt.y, rot: b.rot, layer: b.layer, glow: 0, scale: 1 });
  }
  // counting highlight + tags
  const tags: TagView[] = [];
  for (const m of tl.counts) {
    if (f < m.frame || f > m.groupEnd + 30) continue;
    const bv = bviews.find((b) => b.id === m.id)!;
    const d = f - m.frame;
    const pulse = d < 22 ? Math.sin((d / 22) * Math.PI) : 0;
    const fade = f > m.groupEnd ? 1 - prog(f, m.groupEnd, m.groupEnd + 30) : 1;
    bv.glow = Math.max(bv.glow, (pulse * 0.75 + 0.25) * fade);
    bv.scale = 1 + pulse * 0.16;
    tags.push({ id: m.id, n: m.n, x: bv.x, y: bv.y - 74, opacity: fade, scale: easeOut(prog(d, 0, 8)) * (1 + pulse * 0.12), who: m.who });
  }
  const pos: Record<CharId, PosState> = {
    hani: posAt(tl, 'hani', f, OFF_LEFT),
    mako: posAt(tl, 'mako', f, { x: 1220, y: 905 }),
  };
  const ctx: Ctx = { tl, f, bowl, berries, moving: movingBerry(tl, f, bowl), pos };
  const h = evalChar('hani', ctx, manifest);
  const m = evalChar('mako', ctx, manifest);
  const haniBehind = h.p.y < 880 || f < tl.bowlPlacedFrame;
  const chars: Record<CharId, CharView> = {
    hani: { p: h.p, behindBowl: haniBehind, armsInFront: haniBehind || f < tl.bowlPlacedFrame },
    mako: { p: m.p, behindBowl: false, armsInFront: false },
  };
  // badges
  const badges: BadgeView[] = [];
  for (const who of ['hani', 'mako'] as CharId[]) {
    const ks = tl.badges.filter((b) => b.who === who && b.frame <= f);
    const cur = ks[ks.length - 1];
    if (!cur) continue;
    const age = f - cur.frame;
    if (cur.n !== null) badges.push({ who, n: cur.n, opacity: prog(age, 0, 6), scale: lerp(0.4, 1, easeOutBack(prog(age, 0, 12))) });
    else {
      const prev = ks[ks.length - 2];
      if (prev && prev.n !== null && age < 12) badges.push({ who, n: prev.n, opacity: 1 - prog(age, 0, 12), scale: 1 - prog(age, 0, 12) * 0.3 });
    }
  }
  const overlays = tl.overlays
    .filter((o) => f >= o.start && f < o.end)
    .map((o) => ({ kind: o.kind, p: prog(f, o.start, o.end), age: f - o.start, left: o.end - f }));
  return {
    camera: cameraAt(tl, f),
    bowl,
    berries: bviews,
    tags,
    badges,
    chars,
    overlays,
    speaking: { hani: h.speaking, mako: m.speaking },
  };
};

const easeOutBack = (t: number) => {
  const s = 1.7;
  const x = t - 1;
  return 1 + (s + 1) * x * x * x + s * x * x;
};

export { lerpPt };
