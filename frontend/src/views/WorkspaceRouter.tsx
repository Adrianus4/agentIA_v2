import React from 'react';
import { useStudio } from '../context/StudioContext';
import { DefinitionConfigView } from './DefinitionConfigView';
import { ArchitectureModelsView } from './ArchitectureModelsView';
import { CodeExplorerView } from './CodeExplorerView';
import { SecurityQualityView } from './SecurityQualityView';
import { DevOpsAndDeliveryView } from './DevOpsAndDeliveryView';

export const WorkspaceRouter: React.FC = () => {
  const { activeTab } = useStudio();

  switch (activeTab) {
    case 0:
      return <DefinitionConfigView />;
    case 1:
      return <ArchitectureModelsView />;
    case 2:
      return <CodeExplorerView />;
    case 3:
      return <SecurityQualityView />;
    case 4:
      return <DevOpsAndDeliveryView />;
    default:
      return <DefinitionConfigView />;
  }
};
