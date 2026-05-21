import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
}

export default function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center py-12 text-muted-foreground">
      <Icon className="h-12 w-12 mb-4 opacity-40" />
      <p className="text-lg font-medium">{title}</p>
      {description && <p className="text-sm mt-1">{description}</p>}
    </div>
  );
}
