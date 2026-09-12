import React from 'react';
import { ExamIIOLogo, ExamIIOLogoProps } from './ExamIIOLogo';

export type VigilisLogoProps = ExamIIOLogoProps;

export const VigilisLogo: React.FC<VigilisLogoProps> = (props) => {
  return <ExamIIOLogo {...props} showSubtitle={false} />;
};

export default VigilisLogo;

