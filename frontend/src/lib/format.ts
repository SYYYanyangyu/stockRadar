// 统一格式化
export const fmtWan = (v: number | null | undefined): string => {
  if (v == null || v === 0) return '-';
  const n = Number(v);
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}亿`;
  return `${n.toFixed(0)}万`;
};

export const fmtYi = (v: number | null | undefined): string => {
  if (!v) return '-';
  const n = Number(v);
  return `${(n / 100000000).toFixed(1)}亿`;
};

export const fmtPct = (v: number | null | undefined): string => {
  if (v == null) return '-';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
};

export const colorPct = (v: number | null | undefined): string => {
  if (v == null) return 'text-muted-foreground';
  return Number(v) >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400';
};

export const colorBg = (v: number | null | undefined): string => {
  if (v == null) return '';
  return Number(v) >= 0 ? 'bg-red-50 dark:bg-red-950' : 'bg-green-50 dark:bg-green-950';
};
