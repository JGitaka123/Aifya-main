"use client";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Items per page selector */
  pageSize?: number;
  pageSizeOptions?: number[];
  onPageSizeChange?: (size: number) => void;
  /** Total item count for display */
  totalItems?: number;
}

export default function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  pageSize,
  pageSizeOptions = [10, 25, 50, 100],
  onPageSizeChange,
  totalItems,
}: PaginationProps) {
  if (totalPages <= 1 && !totalItems) return null;

  // Generate page numbers with ellipsis
  const getPageNumbers = (): (number | "...")[] => {
    const pages: (number | "...")[] = [];
    const delta = 2;

    for (let i = 1; i <= totalPages; i++) {
      if (i === 1 || i === totalPages || (i >= currentPage - delta && i <= currentPage + delta)) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== "...") {
        pages.push("...");
      }
    }

    return pages;
  };

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-3">
      {/* Info */}
      <div className="text-sm text-slate-500">
        {totalItems !== undefined && (
          <span>
            Showing page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
            {" "}({totalItems.toLocaleString()} items)
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {/* Page size selector */}
        {onPageSizeChange && pageSize && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="px-2 py-1.5 border rounded-md text-sm text-slate-600 focus:outline-none focus:ring-2 focus:ring-medical-blue"
            aria-label="Items per page"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        )}

        {/* Page buttons */}
        <nav className="flex items-center gap-1" aria-label="Pagination">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className="px-2.5 py-1.5 text-sm border rounded-md text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            aria-label="Previous page"
          >
            &lsaquo;
          </button>

          {getPageNumbers().map((page, i) =>
            page === "..." ? (
              <span key={`ellipsis-${i}`} className="px-2 py-1 text-slate-400 text-sm">
                ...
              </span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  currentPage === page
                    ? "bg-medical-blue text-white font-medium"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
                aria-current={currentPage === page ? "page" : undefined}
              >
                {page}
              </button>
            )
          )}

          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="px-2.5 py-1.5 text-sm border rounded-md text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            aria-label="Next page"
          >
            &rsaquo;
          </button>
        </nav>
      </div>
    </div>
  );
}
