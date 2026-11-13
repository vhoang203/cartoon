// Episode 01 cue sheet — the storyboard in executable form.
//
// Each cue lasts as long as its dialogue (from the generated audio manifest)
// plus `lead`/`pad`, or `dur` seconds, whichever is longer. Character cues
// are keyframes: values persist until changed. `at` = seconds from cue start.
// Change a line in dialogue.json or a number here and re-run `npm run build`.
import type { Pt } from '../lib/anim';
import type { CharId, CharParams } from '../lib/rig';
import type { Loc, SId, ShotName } from './layout';

export type Target =
  | 'hani'
  | 'mako'
  | 'bowl'
  | 'plateH'
  | 'plateM'
  | 'camera'
  | 'up'
  | 'offLeft'
  | 'moving' // the strawberry currently being moved
  | `berry:${SId}`
  | `tap:${SId}` // just above a strawberry (for touching while counting)
  | Pt;

export type MoveTo = 'seat' | 'bowlSpot' | 'offLeft' | Pt;

export type CharCue = {
  at?: number;
  pose?: string;
  expr?: string;
  look?: Target;
  hand?: Target | null; // the partner-side paw reaches toward this target (null = back to pose)
  over?: Partial<Omit<CharParams, 'armL' | 'armR'>>; // numeric overrides; cleared by a new pose unless re-given
  t?: number; // transition seconds (default 0.3)
  move?: { to: MoveTo; dur: number; hops: number };
  nod?: boolean;
  hop?: boolean;
  giggle?: boolean;
};

export type TransferCue = {
  id: SId;
  to: Loc;
  style: 'toss' | 'handoff';
  by: CharId;
  receiver?: CharId;
  at: number;
};

export type MusicMode = 'full' | 'light' | 'quiet' | 'silent' | 'warm' | 'finale';
export type Overlay = 'title' | 'end' | 'think' | 'equal';

export type Cue = {
  id: string;
  beat: 1 | 2 | 3 | 4 | 5 | 6;
  note: string; // storyboard description (English)
  say?: string; // dialogue line id
  count?: { who: CharId; ids: SId[]; every: number };
  lead?: number;
  pad?: number;
  dur?: number;
  shot?: ShotName | { name: ShotName; at?: number; ease?: number };
  hani?: CharCue | CharCue[];
  mako?: CharCue | CharCue[];
  transfers?: TransferCue[];
  placeBowl?: boolean;
  sfx?: { name: string; at: number; gain?: number }[];
  badges?: Partial<Record<CharId, number | null>>;
  music?: MusicMode;
  overlay?: { kind: Overlay; at?: number; dur?: number };
};

const plateH = (slot: number): Loc => ({ kind: 'plate', owner: 'hani', slot });
const plateM = (slot: number): Loc => ({ kind: 'plate', owner: 'mako', slot });

export const CUES: Cue[] = [
  // ───────────────────────────── Beat 1 — the picnic begins
  {
    id: 'open',
    beat: 1,
    note: 'Wide garden, series title. Mako sits on the blanket and straightens the right-hand plate, then hears Hani coming.',
    dur: 4.8,
    shot: 'WIDE',
    music: 'full',
    overlay: { kind: 'title', at: 0.2, dur: 4.3 },
    hani: { move: { to: 'offLeft', dur: 0, hops: 0 }, pose: 'carryBowl', expr: 'delighted', look: 'mako' },
    mako: [
      { pose: 'listen', expr: 'calm', look: 'plateM' },
      { at: 1.0, hand: { x: 1080, y: 925 }, t: 0.45 },
      { at: 2.5, hand: null, t: 0.45 },
      { at: 3.6, look: 'offLeft', expr: 'curious', t: 0.25 },
    ],
  },
  {
    id: 'enter',
    beat: 1,
    note: 'Hani hops in from the left carrying a bowl of exactly six strawberries and kneels behind the bowl spot. Mako waves.',
    dur: 3.7,
    hani: { move: { to: 'bowlSpot', dur: 3.3, hops: 5 }, look: 'mako' },
    mako: [{ at: 0.6, pose: 'wave', expr: 'smile', look: 'hani' }],
    shot: { name: 'TWO', at: 1.8, ease: 1.8 },
  },
  {
    id: 'L01',
    beat: 1,
    say: 'L01',
    placeBowl: true,
    note: 'Hani sets the bowl down in the middle of the blanket: "Mako ơi! Mình mang dâu tới rồi nè!"',
    hani: { pose: 'ready', expr: 'delighted', look: 'mako' },
    mako: { pose: 'listen', expr: 'smile', look: 'hani' },
  },
  {
    id: 'L01b',
    beat: 1,
    say: 'L01b',
    note: 'Mako, curious: "Ồ! Có bao nhiêu quả dâu vậy Hani?"',
    mako: [{ pose: 'speak', expr: 'curious', look: 'bowl' }, { at: 1.2, look: 'hani' }],
    hani: { look: 'bowl', expr: 'smile' },
  },
  {
    id: 'countH0',
    beat: 1,
    count: { who: 'hani', ids: ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'], every: 0.85 },
    note: 'Detail view. Hani, kneeling behind the bowl, touches and counts the strawberries: "Một, hai, ba, bốn, năm, sáu." Six separate, clearly countable strawberries.',
    shot: { name: 'TABLE', ease: 0.8 },
    lead: 0.9,
    pad: 0.3,
    hani: { pose: 'ready', expr: 'curious' },
    mako: { pose: 'listen', look: 'bowl', expr: 'calm' },
  },
  {
    id: 'L05',
    beat: 1,
    say: 'L05',
    note: 'Mako, delighted: "Ồ, sáu quả dâu chín đỏ!"',
    mako: { pose: 'open', expr: 'delighted', look: 'bowl' },
    hani: { hand: null, pose: 'ready', expr: 'delighted', look: 'mako' },
    lead: 0.2,
    pad: 0.6,
  },
  {
    id: 'L02',
    beat: 1,
    say: 'L02',
    note: 'Mako invites Hani to sit, gesturing toward the left-hand spot.',
    shot: 'TWO',
    mako: [{ pose: 'speak', expr: 'smile', look: 'hani' }, { at: 0.9, hand: { x: 1060, y: 860 }, look: { x: 720, y: 860 } }],
    hani: [{ pose: 'listen', expr: 'smile', look: 'mako' }],
    pad: 0.2,
  },
  {
    id: 'sit',
    beat: 1,
    note: 'Hani hops to the left seat. On landing, the loose curl bounces down over one eye (personality beat).',
    dur: 1.9,
    hani: [
      { move: { to: 'seat', dur: 1.0, hops: 2 }, look: { x: 700, y: 900 } },
      { at: 1.0, over: { earFold: 150, earR: 26 }, expr: 'surprise', t: 0.16, look: 'up' },
    ],
    mako: [{ hand: null, pose: 'listen', look: 'hani', expr: 'curious' }, { at: 1.25, expr: 'laugh' }],
    sfx: [{ name: 'boing', at: 1.0, gain: 0.9 }],
  },
  {
    id: 'L03',
    beat: 1,
    say: 'L03',
    note: 'Mako giggles and points at Hani\'s curl: "Hì hì, tóc của Hani rơi xuống mắt rồi kìa."',
    mako: [{ expr: 'laugh', giggle: true, hand: { x: 1030, y: 690 }, look: { x: 690, y: 690 } }, { at: 1.6, expr: 'smile', look: 'hani' }],
    hani: { expr: 'oops', look: 'up' },
    pad: 0.25,
  },
  {
    id: 'L04',
    beat: 1,
    say: 'L04',
    note: 'Hani pushes the curl back with a hand — it springs back beside the temple: "Tóc mình đang vui đó mà!"',
    hani: [
      { pose: 'earFix', t: 0.35, over: { earFold: 150, earR: 26 } },
      { at: 0.55, over: { earFold: 48, earR: 12 }, t: 0.3 },
      { at: 0.95, pose: 'speak', expr: 'delighted', look: 'mako' },
    ],
    mako: [{ hand: null, pose: 'listen', expr: 'smile' }, { at: 1.4, expr: 'laugh' }],
    sfx: [{ name: 'boing', at: 0.6, gain: 0.6 }],
    pad: 0.8,
  },
  {
    id: 'L06',
    beat: 1,
    say: 'L06',
    note: 'Hani proposes the goal: "Mako ơi, mình chia để mỗi bạn có số dâu bằng nhau nhé!"',
    shot: 'TWO',
    hani: [{ pose: 'speak', expr: 'curious', look: 'mako' }, { at: 1.5, pose: 'open' }],
    mako: { pose: 'listen', expr: 'calm', look: 'hani' },
    lead: 0.2,
    pad: 0.35,
  },
  {
    id: 'L07',
    beat: 1,
    say: 'L07',
    note: 'Mako agrees and names the plates, pointing left then right: "Ừ! Đĩa này của Hani, đĩa này của mình."',
    mako: [
      { nod: true, expr: 'smile', pose: 'speak' },
      { at: 0.5, hand: 'plateH', look: 'plateH' },
      { at: 1.45, hand: 'plateM', look: 'plateM' },
    ],
    hani: [{ pose: 'listen' }, { at: 0.55, look: 'plateH' }, { at: 1.5, look: 'plateM' }],
    pad: 0.4,
  },
  {
    id: 'L07b',
    beat: 1,
    say: 'L07b',
    note: 'Explicit agreement on the goal: "Hai đĩa, số dâu bằng nhau nhé."',
    mako: [{ hand: null, pose: 'open', look: 'hani' }, { at: 1.6, pose: 'listen' }],
    hani: [{ look: 'mako' }, { at: 0.6, nod: true, expr: 'delighted' }],
    pad: 0.7,
  },
  // ───────────────────────────── Beat 2 — a small mistake
  {
    id: 'L08',
    beat: 2,
    say: 'L08',
    note: 'Hani, eager: "Để mình chia cho! Mình chia nhanh lắm!"',
    hani: { pose: 'speakBig', expr: 'delighted', over: { earL: -2, earR: 5 } },
    mako: { pose: 'listen', expr: 'smile', look: 'hani' },
    pad: 0.2,
  },
  {
    id: 'toBowl',
    beat: 2,
    note: 'Hani hops to kneel behind the bowl.',
    dur: 1.15,
    hani: { move: { to: 'bowlSpot', dur: 0.9, hops: 2 }, pose: 'ready', look: 'bowl', expr: 'delighted' },
  },
  {
    id: 'share',
    beat: 2,
    note: 'Quick sharing, one strawberry at a time, each with a visible arc from bowl to plate: S1→Hani, S5→Mako, S2→Hani, S6→Mako, S3→Hani, S4→Hani (Hani forgets to alternate at the end). Bowl ends empty.',
    dur: 6.4,
    transfers: [
      { id: 'S1', to: plateH(0), style: 'toss', by: 'hani', at: 0.3 },
      { id: 'S5', to: plateM(1), style: 'toss', by: 'hani', at: 1.25 },
      { id: 'S2', to: plateH(1), style: 'toss', by: 'hani', at: 2.2 },
      { id: 'S6', to: plateM(2), style: 'toss', by: 'hani', at: 3.15 },
      { id: 'S3', to: plateH(2), style: 'toss', by: 'hani', at: 4.1 },
      { id: 'S4', to: plateH(3), style: 'toss', by: 'hani', at: 4.85 },
    ],
    hani: { look: 'moving', expr: 'delighted' },
    mako: { look: 'moving', expr: 'curious' },
  },
  {
    id: 'toSeat',
    beat: 2,
    note: 'Hani hops back to the left seat.',
    dur: 1.2,
    hani: { move: { to: 'seat', dur: 0.95, hops: 2 }, look: 'mako', pose: 'listen' },
    mako: { look: 'hani', expr: 'calm' },
  },
  {
    id: 'L09',
    beat: 2,
    say: 'L09',
    note: 'Hani, pleased, gestures at the empty bowl: "Xong rồi! Bát hết dâu rồi nè."',
    hani: [{ pose: 'speak', expr: 'happy', look: 'mako' }, { at: 0.7, hand: { x: 850, y: 815 }, look: 'bowl', expr: 'delighted' }],
    mako: { look: 'bowl' },
    pad: 1.2,
  },
  // ───────────────────────────── Beat 3 — they notice
  {
    id: 'L10',
    beat: 3,
    say: 'L10',
    note: 'Mako looks from plate to plate, thoughtful: "Ơ... để mình xem nào."',
    music: 'light',
    hani: { hand: null, pose: 'listen', look: 'mako', expr: 'smile' },
    mako: [{ pose: 'think', expr: 'think', look: 'plateH' }, { at: 0.9, look: 'plateM' }],
    pad: 0.5,
  },
  {
    id: 'countM1',
    beat: 3,
    count: { who: 'mako', ids: ['S5', 'S6'], every: 1.0 },
    note: 'Detail view. Mako touches and counts own plate: "Một, hai." Each strawberry lights up once with a number tag.',
    shot: { name: 'TABLE', ease: 1.0 },
    lead: 1.0,
    pad: 0.4,
    mako: { pose: 'listen', expr: 'calm' },
    hani: { look: 'plateM' },
  },
  {
    id: 'L11',
    beat: 3,
    say: 'L11',
    note: 'Total badge "2" appears under Mako\'s plate: "Đĩa của mình có hai quả."',
    badges: { mako: 2 },
    mako: { hand: null, look: 'hani', expr: 'calm' },
    pad: 0.6,
  },
  {
    id: 'L12',
    beat: 3,
    say: 'L12',
    note: 'Mako gestures toward Hani\'s plate: "Còn đĩa của Hani thì sao?"',
    mako: [{ expr: 'curious', look: 'plateH' }, { at: 0.4, hand: 'plateH' }, { at: 1.6, hand: null }],
    hani: { look: 'plateH' },
    pad: 0.45,
  },
  {
    id: 'countH1',
    beat: 3,
    count: { who: 'hani', ids: ['S1', 'S2', 'S3', 'S4'], every: 1.0 },
    note: 'Hani counts own plate, touching each strawberry once: "Một, hai, ba, bốn."',
    lead: 0.35,
    pad: 0.35,
    hani: { expr: 'curious' },
    mako: { look: 'plateH', expr: 'calm' },
  },
  {
    id: 'L13',
    beat: 3,
    say: 'L13',
    note: 'Badge "4" appears under Hani\'s plate: "Đĩa của mình có bốn quả!"',
    badges: { hani: 4 },
    hani: { hand: null, expr: 'delighted', look: 'mako' },
    pad: 0.5,
  },
  {
    id: 'notice',
    beat: 3,
    note: 'Reaction pause: Hani\'s eyes go from the 4 to the 2 and back; ears rise; realisation.',
    dur: 2.0,
    hani: [
      { look: 'plateH', expr: 'curious' },
      { at: 0.5, look: 'plateM' },
      { at: 0.95, look: 'plateH' },
      { at: 1.25, expr: 'surprise', look: 'plateM', t: 0.15 },
    ],
  },
  {
    id: 'L14',
    beat: 3,
    say: 'L14',
    note: 'Two-shot. Mild surprise, then a slightly sheepish droop: "Ôi! Bốn quả và hai quả. Không bằng nhau rồi."',
    shot: 'TWO',
    hani: [{ pose: 'surprise', expr: 'surprise', look: 'mako' }, { at: 1.4, pose: 'listen', expr: 'oops' }],
    mako: { look: 'hani', expr: 'calm' },
    pad: 0.9,
  },
  {
    id: 'L15',
    beat: 3,
    say: 'L15',
    note: 'Mako leans in kindly: "Không sao đâu Hani. Mình cùng sửa nhé!" Hani brightens.',
    mako: [{ pose: 'speak', expr: 'kind', over: { lean: -4 } }, { at: 1.3, nod: true }],
    hani: [{ look: 'mako' }, { at: 1.2, expr: 'smile' }],
    pad: 0.8,
  },
  // ───────────────────────────── Beat 4 — invite the viewer
  {
    id: 'L16',
    beat: 4,
    say: 'L16',
    note: 'Mako close-up, talking to the viewer: "Các bạn ơi, làm thế nào để hai đĩa có số dâu bằng nhau nhỉ?"',
    shot: 'MAKO_CU',
    music: 'quiet',
    mako: { pose: 'open', expr: 'curious', look: 'camera' },
    hani: { look: 'camera', expr: 'curious' },
    lead: 0.2,
    pad: 0.5,
  },
  {
    id: 'L16b',
    beat: 4,
    say: 'L16b',
    note: 'Hani echoes the invitation to the viewer: "Các bạn thử nghĩ xem nào!"',
    shot: 'TWO',
    hani: { pose: 'open', expr: 'delighted', look: 'camera' },
    mako: { pose: 'listen', expr: 'smile', look: 'camera' },
    pad: 0.3,
  },
  {
    id: 'think',
    beat: 4,
    note: 'VIEWER PAUSE (~4.8 s): detail view holds the clear 4-vs-2 arrangement with total badges. Both think quietly; music drops to ambience. Question bubbles.',
    dur: 5.0,
    shot: { name: 'TABLE', ease: 0.9 },
    music: 'silent',
    overlay: { kind: 'think', at: 0.7, dur: 4.0 },
    hani: [
      { pose: 'think', expr: 'think', look: 'plateH' },
      { at: 1.7, look: 'plateM' },
      { at: 3.0, look: 'plateH' },
    ],
    mako: [
      { pose: 'think', expr: 'think', look: 'plateM', over: { headTilt: -6 } },
      { at: 1.2, look: 'plateH' },
      { at: 2.6, look: 'plateM' },
    ],
  },
  {
    id: 'L17',
    beat: 4,
    say: 'L17',
    note: 'Two-shot. A soft "idea" chime; Hani perks up: "A! Mình biết rồi!"',
    shot: 'TWO',
    music: 'light',
    sfx: [{ name: 'idea', at: 0.0 }],
    lead: 0.25,
    hani: { pose: 'idea', expr: 'delighted', look: 'mako', hop: true, over: { earL: -2, earR: 4 } },
    mako: { pose: 'listen', expr: 'curious', look: 'hani' },
    pad: 0.25,
  },
  {
    id: 'L18',
    beat: 4,
    say: 'L18',
    note: 'Hani touches the rightmost strawberry on their plate, then gestures to Mako: "Mình đưa một quả cho Mako nhé?"',
    hani: [{ pose: 'listen', hand: 'tap:S4', look: 'berry:S4', expr: 'curious' }, { at: 1.0, hand: null, pose: 'open', look: 'mako' }],
    mako: [{ look: 'berry:S4' }, { at: 1.0, look: 'hani' }],
    pad: 0.3,
  },
  {
    id: 'L19',
    beat: 4,
    say: 'L19',
    note: 'Mako nods: "Ý hay đó! Bạn thử đi."',
    mako: [{ nod: true, pose: 'open', expr: 'smile' }],
    hani: { expr: 'delighted', pose: 'listen' },
    pad: 0.35,
  },
  // ───────────────────────────── Beat 5 — solve and verify
  {
    id: 'move',
    beat: 5,
    note: 'Detail view, NO CUT: Hani picks up S4 from their plate and hands it across; Mako receives it and places it on the right-hand plate. Exactly one strawberry moves.',
    shot: { name: 'TABLE', ease: 0.8 },
    music: 'warm',
    badges: { hani: null, mako: null },
    dur: 4.3,
    transfers: [{ id: 'S4', to: plateM(0), style: 'handoff', by: 'hani', receiver: 'mako', at: 1.0 }],
    hani: { pose: 'listen', look: 'moving', expr: 'curious' },
    mako: { pose: 'listen', look: 'moving', expr: 'calm' },
  },
  {
    id: 'L20',
    beat: 5,
    say: 'L20',
    note: 'Mako, happy: "Cảm ơn Hani!"',
    mako: { expr: 'happy', look: 'hani' },
    hani: { expr: 'smile', look: 'mako' },
    pad: 0.35,
  },
  {
    id: 'L21',
    beat: 5,
    say: 'L21',
    note: 'Hani invites the viewer to count along: "Mình đếm lại nhé. Các bạn đếm cùng nha!"',
    hani: [{ pose: 'speak', expr: 'delighted', look: 'plateH' }, { at: 0.9, look: 'camera', pose: 'open' }],
    mako: [{ expr: 'smile' }, { at: 1.0, look: 'camera' }],
    pad: 0.45,
  },
  {
    id: 'countH2',
    beat: 5,
    count: { who: 'hani', ids: ['S1', 'S2', 'S3'], every: 1.3 },
    note: 'Slow count-along on Hani\'s plate: "Một, hai, ba."',
    lead: 0.45,
    pad: 0.7,
    hani: { pose: 'listen', expr: 'curious' },
    mako: { look: 'plateH' },
  },
  {
    id: 'L22',
    beat: 5,
    say: 'L22',
    note: 'Badge "3" under Hani\'s plate: "Đĩa mình có ba quả!"',
    badges: { hani: 3 },
    hani: { hand: null, expr: 'delighted', look: 'mako' },
    pad: 0.4,
  },
  {
    id: 'countM2',
    beat: 5,
    count: { who: 'mako', ids: ['S4', 'S5', 'S6'], every: 1.3 },
    note: 'Slow count-along on Mako\'s plate: "Một, hai, ba."',
    lead: 0.35,
    pad: 0.7,
    mako: { expr: 'calm' },
    hani: { look: 'plateM' },
  },
  {
    id: 'L23',
    beat: 5,
    say: 'L23',
    note: 'Badge "3" under Mako\'s plate: "Đĩa mình cũng có ba quả!"',
    badges: { mako: 3 },
    mako: { hand: null, expr: 'delighted', look: 'hani' },
    pad: 0.4,
  },
  {
    id: 'L24',
    beat: 5,
    say: 'L24',
    note: 'Hani, gesturing to both plates: "Mỗi bạn có ba quả."',
    hani: { pose: 'open', expr: 'delighted', look: 'camera' },
    mako: { look: 'hani' },
    pad: 0.25,
  },
  {
    id: 'L25',
    beat: 5,
    say: 'L25',
    note: 'Mako confirms the result; a gentle sparkle around both plates: "Hai đĩa bằng nhau rồi!"',
    mako: { pose: 'open', expr: 'delighted', look: 'camera' },
    hani: { look: 'mako', pose: 'listen' },
    sfx: [{ name: 'sparkle', at: 0.9 }],
    overlay: { kind: 'equal', at: 0.8, dur: 2.0 },
    pad: 1.4,
  },
  // ───────────────────────────── Beat 6 — a satisfying ending
  {
    id: 'L26',
    beat: 6,
    say: 'L26',
    note: 'Two-shot, celebration: "Hoan hô! Mình cùng nhau làm được rồi!" One happy hop.',
    shot: 'TWO',
    music: 'finale',
    hani: { pose: 'happy', expr: 'happy', look: 'mako', hop: true },
    mako: [{ expr: 'laugh', look: 'hani' }, { at: 0.35, pose: 'happy' }],
    pad: 0.3,
  },
  {
    id: 'highfive',
    beat: 6,
    note: 'Both scoot in and high-five above the empty bowl.',
    dur: 1.6,
    hani: [
      { move: { to: { x: 745, y: 905 }, dur: 0.35, hops: 0 }, pose: 'listen', hand: { x: 960, y: 690 }, expr: 'delighted', look: { x: 960, y: 690 }, t: 0.35 },
      { at: 0.95, hand: null, move: { to: 'seat', dur: 0.4, hops: 0 }, look: 'mako', expr: 'happy' },
    ],
    mako: [
      { move: { to: { x: 1175, y: 905 }, dur: 0.35, hops: 0 }, pose: 'listen', hand: { x: 960, y: 690 }, expr: 'delighted', look: { x: 960, y: 690 }, t: 0.35 },
      { at: 0.95, hand: null, move: { to: 'seat', dur: 0.4, hops: 0 }, look: 'hani', expr: 'happy' },
    ],
    sfx: [{ name: 'tap', at: 0.42, gain: 1.4 }],
  },
  {
    id: 'L26b',
    beat: 6,
    say: 'L26b',
    note: 'Mako, warmly, looking over the prepared picnic: "Bữa picnic của tụi mình sẵn sàng rồi!"',
    mako: { pose: 'open', expr: 'delighted', look: 'plateM' },
    hani: { pose: 'listen', expr: 'happy', look: 'mako' },
    pad: 0.4,
  },
  {
    id: 'L26c',
    beat: 6,
    say: 'L26c',
    note: 'Hani thanks the viewer: "Cảm ơn các bạn đã cùng đếm với tụi mình!"',
    hani: { pose: 'open', expr: 'delighted', look: 'camera' },
    mako: { pose: 'listen', expr: 'smile', look: 'camera' },
    pad: 0.4,
  },
  {
    id: 'L27',
    beat: 6,
    say: 'L27',
    note: 'Both together, to the viewer (memorable closing line): "Chia đều nhau, ai cũng vui!" Camera eases back.',
    shot: { name: 'WIDE2', ease: 2.4 },
    hani: { pose: 'open', expr: 'delighted', look: 'camera' },
    mako: { pose: 'open', expr: 'delighted', look: 'camera' },
    lead: 0.2,
    pad: 0.5,
  },
  {
    id: 'L28',
    beat: 6,
    say: 'L28',
    note: 'Hani waves: "Tạm biệt các bạn!"',
    hani: { pose: 'wave', expr: 'delighted', look: 'camera' },
    mako: { pose: 'listen', expr: 'smile' },
    pad: 0.15,
  },
  {
    id: 'L29',
    beat: 6,
    say: 'L29',
    note: 'Mako waves too: "Hẹn gặp lại nhé!"',
    mako: { pose: 'wave', expr: 'delighted', look: 'camera' },
    pad: 0.2,
  },
  {
    id: 'end',
    beat: 6,
    note: 'Short end card over the scene; both plates still show 3 and 3.',
    dur: 4.0,
    overlay: { kind: 'end', at: 0.1, dur: 3.9 },
    hani: [{ at: 1.6, pose: 'listen', expr: 'happy' }],
    mako: [{ at: 2.0, pose: 'listen', expr: 'happy' }],
  },
];
