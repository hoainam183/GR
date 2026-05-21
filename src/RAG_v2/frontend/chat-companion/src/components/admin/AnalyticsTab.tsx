import React, { Suspense } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import QueryAnalyticsSection from './QueryAnalyticsSection';

const AgentAnalyticsSection = React.lazy(() => import('./AgentAnalyticsSection'));

export default function AnalyticsTab() {
  return (
    <div className="space-y-8">
      <QueryAnalyticsSection />
      <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
        <AgentAnalyticsSection />
      </Suspense>
    </div>
  );
}
