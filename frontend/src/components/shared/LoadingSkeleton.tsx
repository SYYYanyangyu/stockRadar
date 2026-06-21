import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

interface LoadingSkeletonProps {
  rows?: number;
  className?: string;
  variant?: "table" | "card" | "stats";
}

export function LoadingSkeleton({ rows = 5, className, variant = "table" }: LoadingSkeletonProps) {
  if (variant === "stats") {
    return (
      <div className={cn("grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4", className)}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-lg" />
        ))}
      </div>
    );
  }

  if (variant === "card") {
    return (
      <div className={cn("grid grid-cols-2 md:grid-cols-3 gap-3 mb-4", className)}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className={cn("space-y-2 p-4", className)}>
      <Skeleton className="h-8 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
