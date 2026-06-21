import { cn } from "@/lib/utils";

interface EmptyStateProps {
  text?: string;
  icon?: string;
  className?: string;
}

export function EmptyState({ text = "暂无数据", icon = "📭", className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 text-muted-foreground", className)}>
      <div className="text-5xl mb-3">{icon}</div>
      <div className="text-sm font-semibold text-muted-foreground">{text}</div>
    </div>
  );
}
