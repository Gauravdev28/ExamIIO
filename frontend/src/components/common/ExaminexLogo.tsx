import React from 'react';
import { VigilisLogo, VigilisLogoProps } from './VigilisLogo';

export type ExaminexLogoProps = VigilisLogoProps;

export const ExaminexLogo: React.FC<ExaminexLogoProps> = (props) => (
  <VigilisLogo {...props} />
);

export default ExaminexLogo;
