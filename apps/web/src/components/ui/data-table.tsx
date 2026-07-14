import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
};

export function DataTable<T extends { id: string }>({
  columns,
  data,
  emptyText = "暂无数据",
  onRowClick,
  selectedId,
}: {
  columns: Column<T>[];
  data: T[];
  emptyText?: string;
  onRowClick?: (row: T) => void;
  selectedId?: string;
}) {
  if (data.length === 0) {
    return <div className="px-4 py-8 text-center text-sm text-ink-3">{emptyText}</div>;
  }

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-line-strong">
            {columns.map((col) => (
              <th
                className="px-4 py-2.5 text-label uppercase tracking-wider text-ink-3"
                key={col.key}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {data.map((row) => (
            <tr
              className={cn(
                "transition-colors",
                onRowClick && "cursor-pointer hover:bg-surface",
                selectedId === row.id && "bg-accent-soft",
              )}
              key={row.id}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col) => (
                <td
                  className={cn("px-4 py-2.5 text-sm text-ink-2", col.className)}
                  key={col.key}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
