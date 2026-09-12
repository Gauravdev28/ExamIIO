import React from 'react';
import { VigilisLogo, VigilisLogoProps } from './VigilisLogo';

export type ExamIOLogoProps = VigilisLogoProps;

export const ExamIOLogo: React.FC<ExamIOLogoProps> = (props) => {
  return <VigilisLogo {...props} />;
};

export default ExamIOLogo;
