import React, { useMemo } from 'react';
import { AbsoluteFill } from 'remotion';
import { C } from '../lib/palette';
import { FontLoader } from '../lib/fonts';
import { SceneFrame, getTimeline } from './Episode';

// 1280x720 thumbnail: a real frame from the celebration (3 and 3 on the plates)
// with a short, large title for small-size readability.
export const Thumbnail: React.FC = () => {
  const tl = useMemo(getTimeline, []);
  const cue = tl.cues.find((c) => c.id === 'L26')!;
  const f = cue.start + 6;
  return (
    <AbsoluteFill style={{ backgroundColor: C.cream }}>
      <FontLoader />
      <SceneFrame tl={tl} f={f} width={1280} height={720} camera={{ cx: 960, cy: 800, z: 1.5 }} />
      <div
        style={{
          position: 'absolute',
          top: 26,
          left: 0,
          right: 0,
          textAlign: 'center',
          fontFamily: 'Nunito',
          fontWeight: 900,
          fontSize: 104,
          lineHeight: 1,
          color: C.white,
          WebkitTextStroke: `14px ${C.ink}`,
          paintOrder: 'stroke fill',
          textShadow: '0 7px 0 rgba(46,58,75,0.25)',
        }}
      >
        Chia dâu <span style={{ color: '#FFE27A' }}>bằng nhau!</span>
      </div>
      <div
        style={{
          position: 'absolute',
          top: 150,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            fontFamily: 'Nunito',
            fontWeight: 900,
            fontSize: 40,
            color: C.ink,
            background: 'rgba(255,251,242,0.95)',
            border: `4px solid ${C.ink}`,
            borderRadius: 999,
            padding: '4px 26px',
          }}
        >
          Hani <span style={{ color: C.apricotShade }}>&amp;</span> Mako
        </div>
      </div>
    </AbsoluteFill>
  );
};
