// Builds a frame-accurate timeline from the cue sheet and the audio manifest.
// Pure module: used by the Remotion composition and by tools/export.ts.
import type { Pt } from '../lib/anim.ts';
import type { CharId, CharParams } from '../lib/rig.ts';
import { CUES, type Cue, type CharCue, type MoveTo, type MusicMode, type Overlay, type Target } from './cues.ts';
import {
  BOWL_SPOT,
  HANDOFF_PT,
  INITIAL,
  OFF_LEFT,
  SEAT,
  SIDS,
  type Loc,
  type SId,
  type ShotName,
} from './layout.ts';

export const FPS = 30;

export type Manifest = {
  fps: number;
  lines: Record<
    string,
    { speaker: string; text: string; file: string; duration: number; frames: number; source: string; env: Record<string, number[]> }
  >;
};

export type CharKey = {
  frame: number;
  t: number; // transition frames
  pose: string;
  expr: string;
  look: Target;
  hand: Target | null;
  over: Partial<Omit<CharParams, 'armL' | 'armR'>>;
};
export type Move = { start: number; end: number; from: Pt; to: Pt; hops: number };
export type CharEvent = { type: 'nod' | 'hop' | 'giggle'; frame: number };
export type Speech = { lineId: string; who: CharId[]; start: number; frames: number; file: string; text: string; cue: string };
export type CountMark = { frame: number; id: SId; n: number; who: CharId; groupStart: number; groupEnd: number; wordId: string };
export type Transfer = {
  id: SId;
  from: Loc;
  to: Loc;
  style: 'toss' | 'handoff';
  by: CharId;
  receiver?: CharId;
  start: number;
  end: number;
  // phase boundaries (frames)
  ph: number[];
  cue: string;
};
export type ShotKey = { frame: number; shot: ShotName; ease: number };
export type BadgeKey = { frame: number; who: CharId; n: number | null };
export type OverlaySpan = { kind: Overlay; start: number; end: number };
export type MusicSpan = { mode: MusicMode; start: number; end: number };
export type Sfx = { name: string; frame: number; gain?: number };
export type CueSpan = { id: string; beat: number; start: number; end: number; note: string; say?: string; shot: ShotName };

export type Timeline = {
  fps: number;
  totalFrames: number;
  cues: CueSpan[];
  speech: Speech[];
  counts: CountMark[];
  transfers: Transfer[];
  keys: Record<CharId, CharKey[]>;
  moves: Record<CharId, Move[]>;
  events: Record<CharId, CharEvent[]>;
  shots: ShotKey[];
  badges: BadgeKey[];
  overlays: OverlaySpan[];
  music: { mode: MusicMode; start: number; end: number }[]; // seconds
  sfx: Sfx[];
  bowlPlacedFrame: number;
};

const sec = (s: number) => Math.round(s * FPS);
const asArr = <T,>(x: T | T[] | undefined): T[] => (x === undefined ? [] : Array.isArray(x) ? x : [x]);

const resolveMoveTo = (who: CharId, to: MoveTo): Pt =>
  to === 'seat' ? SEAT[who] : to === 'bowlSpot' ? BOWL_SPOT : to === 'offLeft' ? OFF_LEFT : to;

// Transfer phase durations (seconds)
const TOSS = { pick: 0.3, fly: 0.62 };
const HANDOFF = { reach: 0.5, carry1: 0.85, hold: 0.35, carry2: 0.7, release: 0.45 };

export const buildTimeline = (manifest: Manifest, cues: Cue[] = CUES): Timeline => {
  const tl: Timeline = {
    fps: FPS,
    totalFrames: 0,
    cues: [],
    speech: [],
    counts: [],
    transfers: [],
    keys: { hani: [], mako: [] },
    moves: { hani: [], mako: [] },
    events: { hani: [], mako: [] },
    shots: [],
    badges: [],
    overlays: [],
    music: [],
    sfx: [],
    bowlPlacedFrame: Number.MAX_SAFE_INTEGER,
  };
  const state: Record<CharId, Omit<CharKey, 'frame' | 't'> & { pos: Pt }> = {
    hani: { pose: 'listen', expr: 'neutral', look: 'camera', hand: null, over: {}, pos: SEAT.hani },
    mako: { pose: 'listen', expr: 'neutral', look: 'camera', hand: null, over: {}, pos: SEAT.mako },
  };
  const loc: Record<SId, Loc> = { ...INITIAL };
  let shot: ShotName = 'WIDE';
  let music: MusicMode = 'full';
  let f = 0;

  const line = (id: string) => {
    const l = manifest.lines[id];
    if (!l) throw new Error(`audio manifest has no line ${id} — run \`npm run build:audio\``);
    return l;
  };

  for (const cue of cues) {
    const start = f;
    const lead = sec(cue.lead ?? 0);
    let len = 0;
    const charCues: Record<CharId, CharCue[]> = { hani: asArr(cue.hani).slice(), mako: asArr(cue.mako).slice() };

    // ---- dialogue / counting
    if (cue.say) {
      const l = line(cue.say);
      const who: CharId[] = l.speaker === 'both' ? ['hani', 'mako'] : [l.speaker as CharId];
      tl.speech.push({ lineId: cue.say, who, start: start + lead, frames: l.frames, file: l.file, text: l.text, cue: cue.id });
      len = lead + l.frames + sec(cue.pad ?? 0.55);
    }
    if (cue.count) {
      const { who, ids, every } = cue.count;
      const groupStart = start + lead;
      let last = groupStart;
      const marks: CountMark[] = [];
      ids.forEach((id, i) => {
        const wordId = `N${i + 1}_${who}`;
        const l = line(wordId);
        const fr = groupStart + sec(i * every);
        tl.speech.push({ lineId: wordId, who: [who], start: fr, frames: l.frames, file: l.file, text: l.text, cue: cue.id });
        marks.push({ frame: fr, id, n: i + 1, who, groupStart, groupEnd: 0, wordId });
        tl.sfx.push({ name: `count${i + 1}`, frame: fr + l.frames + 1, gain: 0.32 }); // chime after the word so it never masks it
        last = fr + l.frames;
      });
      const groupEnd = last + sec(0.3);
      marks.forEach((m) => (m.groupEnd = groupEnd));
      tl.counts.push(...marks);
      len = Math.max(len, last - start + sec(cue.pad ?? 0.45));
      // the counter touches each strawberry as it is named
      marks.forEach((m) => {
        charCues[who].push({ at: (m.frame - start) / FPS - 0.12, hand: `tap:${m.id}`, look: `berry:${m.id}`, t: 0.22 });
      });
    }
    if (cue.dur) len = Math.max(len, sec(cue.dur));

    // ---- transfers (also extend the cue if needed)
    for (const tr of cue.transfers ?? []) {
      const s = start + sec(tr.at);
      const from = loc[tr.id];
      let ph: number[];
      if (tr.style === 'toss') {
        ph = [s, s + sec(TOSS.pick), s + sec(TOSS.pick + TOSS.fly)];
        tl.sfx.push({ name: 'pick', frame: ph[1] - 2 }, { name: 'whoosh', frame: ph[1] }, { name: 'plop', frame: ph[2] - 1 });
      } else {
        const h = HANDOFF;
        const a = s;
        const b = a + sec(h.reach);
        const c = b + sec(h.carry1);
        const d = c + sec(h.hold);
        const e = d + sec(h.carry2);
        const g = e + sec(h.release);
        ph = [a, b, c, d, e, g];
        tl.sfx.push({ name: 'pick', frame: b - 1 }, { name: 'tap', frame: c, gain: 0.8 }, { name: 'plop', frame: e - 1 });
      }
      const end = ph[ph.length - 1];
      tl.transfers.push({ id: tr.id, from, to: tr.to, style: tr.style, by: tr.by, receiver: tr.receiver, start: s, end, ph, cue: cue.id });
      loc[tr.id] = tr.to;
      len = Math.max(len, end - start + sec(0.3));
    }

    // ---- character keys / moves / events
    (['hani', 'mako'] as CharId[]).forEach((who) => {
      const list = charCues[who].slice().sort((a, b) => (a.at ?? 0) - (b.at ?? 0));
      for (const cc of list) {
        const at = start + sec(cc.at ?? 0);
        const st = state[who];
        if (cc.pose !== undefined && cc.pose !== st.pose) {
          st.pose = cc.pose;
          st.over = {};
        }
        if (cc.expr !== undefined) st.expr = cc.expr;
        if (cc.look !== undefined) st.look = cc.look;
        if (cc.hand !== undefined) st.hand = cc.hand;
        if (cc.over) st.over = { ...st.over, ...cc.over };
        tl.keys[who].push({
          frame: at,
          t: Math.max(1, sec(cc.t ?? 0.3)),
          pose: st.pose,
          expr: st.expr,
          look: st.look,
          hand: st.hand,
          over: { ...st.over },
        });
        if (cc.move) {
          const to = resolveMoveTo(who, cc.move.to);
          const mv: Move = { start: at, end: at + sec(cc.move.dur), from: st.pos, to, hops: cc.move.hops };
          tl.moves[who].push(mv);
          st.pos = to;
          for (let i = 1; i <= cc.move.hops; i++) {
            tl.sfx.push({ name: 'hop', frame: Math.round(mv.start + ((mv.end - mv.start) * i) / cc.move.hops) - 1, gain: 0.7 });
          }
          len = Math.max(len, mv.end - start);
        }
        if (cc.nod) tl.events[who].push({ type: 'nod', frame: at });
        if (cc.hop) {
          tl.events[who].push({ type: 'hop', frame: at });
          tl.sfx.push({ name: 'hop', frame: at + sec(0.48), gain: 0.6 });
        }
        if (cc.giggle) tl.events[who].push({ type: 'giggle', frame: at });
      }
    });

    for (const s of cue.sfx ?? []) tl.sfx.push({ name: s.name, frame: start + sec(s.at), gain: s.gain });

    // ---- camera
    if (cue.shot) {
      const sh = typeof cue.shot === 'string' ? { name: cue.shot, at: 0, ease: 0 } : cue.shot;
      tl.shots.push({ frame: start + sec(sh.at ?? 0), shot: sh.name, ease: sec(sh.ease ?? 0) });
      shot = sh.name;
    }
    if (cue.badges) {
      for (const who of ['hani', 'mako'] as CharId[]) {
        if (cue.badges[who] !== undefined) tl.badges.push({ frame: start, who, n: cue.badges[who] ?? null });
      }
    }
    if (cue.overlay) {
      const s = start + sec(cue.overlay.at ?? 0);
      tl.overlays.push({ kind: cue.overlay.kind, start: s, end: s + sec(cue.overlay.dur ?? 2) });
    }
    if (cue.music && cue.music !== music) {
      music = cue.music;
    }
    const last = tl.music[tl.music.length - 1];
    if (!last || last.mode !== music) tl.music.push({ mode: music, start: start / FPS, end: 0 });
    if (cue.placeBowl) tl.bowlPlacedFrame = start;

    f = start + Math.max(len, 1);
    tl.cues.push({ id: cue.id, beat: cue.beat, start, end: f, note: cue.note, say: cue.say, shot });
  }
  tl.totalFrames = f;
  tl.music.forEach((m, i) => (m.end = i + 1 < tl.music.length ? tl.music[i + 1].start : f / FPS));
  tl.keys.hani.sort((a, b) => a.frame - b.frame);
  tl.keys.mako.sort((a, b) => a.frame - b.frame);
  tl.sfx.sort((a, b) => a.frame - b.frame);
  return tl;
};

// ───────────────────────────────────────── strawberry state at a frame
export type BerryState = {
  id: SId;
  at: 'bowl' | 'plate' | 'moving';
  loc: Loc; // last settled location (source while moving)
  progress?: number;
};

/** Settled location / motion status of every strawberry at frame f. */
export const berryStates = (tl: Timeline, f: number): BerryState[] =>
  SIDS.map((id) => {
    let cur: Loc = INITIAL[id];
    for (const tr of tl.transfers) {
      if (tr.id !== id) continue;
      if (f >= tr.end) cur = tr.to;
      else if (f >= tr.ph[1] && f < tr.end) {
        // the berry has been lifted from its source
        return { id, at: 'moving' as const, loc: tr.from, progress: (f - tr.start) / (tr.end - tr.start) };
      }
    }
    return { id, at: cur.kind, loc: cur };
  });

export { HANDOFF_PT };
