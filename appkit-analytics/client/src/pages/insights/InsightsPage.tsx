import { GenieChat } from '@databricks/appkit-ui/react';

// Full-page version (currently not routed, kept for future use)
export function InsightsPage() {
  return (
    <div className="h-[calc(100vh-5rem)]">
      <GenieChat alias="default" />
    </div>
  );
}

// Compact version for the inline push-panel on the Dashboard
export function InsightsDrawer() {
  return (
    <div className="h-full">
      <GenieChat alias="default" />
    </div>
  );
}
