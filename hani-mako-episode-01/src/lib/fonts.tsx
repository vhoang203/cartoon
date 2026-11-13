import React from 'react';
import { continueRender, delayRender, staticFile } from 'remotion';

// Nunito (SIL OFL 1.1) bundled locally in public/fonts — supports Vietnamese.
let loaded = false;
export const FontLoader: React.FC = () => {
  const [handle] = React.useState(() => (loaded ? null : delayRender('Loading Nunito')));
  React.useEffect(() => {
    if (handle === null) return;
    const face = new FontFace('Nunito', `url(${staticFile('fonts/Nunito.ttf')}) format('truetype')`, { weight: '200 1000' });
    face
      .load()
      .then((f) => {
        (document.fonts as unknown as { add: (x: FontFace) => void }).add(f);
        loaded = true;
        continueRender(handle);
      })
      .catch((e) => {
        console.error(e);
        continueRender(handle);
      });
  }, [handle]);
  return null;
};
