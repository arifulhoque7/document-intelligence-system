import { ChevronLeft, ChevronRight } from "lucide-react";
import { TableFooter } from "./TableToolbar";
import { Button } from "./ui/button";

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <TableFooter>
      <span className="font-mono text-xs">
        {from}-{to} of {total}
      </span>
      <nav aria-label="Pagination" className="flex items-center gap-2">
        <Button size="compact" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft aria-hidden /> Previous
        </Button>
        <span className="font-mono text-xs">
          {page} / {pages}
        </span>
        <Button size="compact" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight aria-hidden />
        </Button>
      </nav>
    </TableFooter>
  );
}
