import React from 'react';
import { LlmProvider } from './context/LlmContext';
import { StudioProvider } from './context/StudioContext';
import { AppLayout } from './components/layout/AppLayout';

export const App: React.FC = () => {
  return (
    <LlmProvider>
      <StudioProvider>
        <AppLayout />
      </StudioProvider>
    </LlmProvider>
  );
};

export default App;
