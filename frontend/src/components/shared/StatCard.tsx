import { Card, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  color: string;
  sub?: string;
  icon?: React.ReactNode;
  small?: boolean;
  className?: string;
}

export function StatCard({ label, value, color, sub, icon, small, className }: StatCardProps) {
  return (
    <Card className={cn(className)}>
      <CardContent className="p-3">
        <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
          {icon}
          {label}
        </div>
        <div className={cn(
          "font-bold tracking-tight",
          small ? "text-base" : "text-2xl",
          color
        )}>
          {value}
        </div>
        {sub && (
          <div className="text-xs text-muted-foreground mt-1">{sub}</div>
        )}
      </CardContent>
    </Card>
  );
}
