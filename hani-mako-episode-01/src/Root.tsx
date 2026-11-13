import React from 'react';
import { Composition, Still } from 'remotion';
import { Episode01, getTimeline } from './episode01/Episode';
import { Thumbnail } from './episode01/Thumbnail';

const tl = getTimeline();
const TEST_START = tl.cues.find((c) => c.id === 'L08')!.start;
const TEST_END = tl.cues.find((c) => c.id === 'L09')!.start + 30;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Episode01" component={Episode01} durationInFrames={tl.totalFrames} fps={30} width={1920} height={1080} />
    <Composition
      id="TestClip"
      component={Episode01}
      defaultProps={{ startFrame: TEST_START }}
      durationInFrames={TEST_END - TEST_START}
      fps={30}
      width={1920}
      height={1080}
    />
    <Composition id="EpisodeSilent" component={Episode01} defaultProps={{ withAudio: false }} durationInFrames={tl.totalFrames} fps={30} width={1920} height={1080} />
    <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} />
  </>
);
