import React from 'react';
import {Composition, AbsoluteFill} from 'remotion';
import config from '../case.config.json';
// Replace this placeholder with your implementation. It is not a reference solution.
const Main: React.FC = () => <AbsoluteFill style={{background:'#101015',color:'#fff',alignItems:'center',justifyContent:'center',fontSize:48,fontFamily:'sans-serif'}}>Replace this starter</AbsoluteFill>;
export const Root: React.FC = () => <Composition id="Main" component={Main} width={config.width} height={config.height} fps={config.fps} durationInFrames={config.duration_frames} />;
