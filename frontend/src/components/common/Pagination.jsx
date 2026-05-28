export default function Pagination({ page, count, pageSize = 50, onChange }) {
  const total = Math.ceil(count / pageSize);
  if (total <= 1) return null;
  return (
    <div className="flex items-center justify-between py-3 text-sm text-gray-600">
      <span>{count} total rows</span>
      <div className="flex gap-2">
        <button
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
          className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100"
        >
          Previous
        </button>
        <span className="px-3 py-1">
          {page} / {total}
        </span>
        <button
          disabled={page === total}
          onClick={() => onChange(page + 1)}
          className="px-3 py-1 rounded border disabled:opacity-40 hover:bg-gray-100"
        >
          Next
        </button>
      </div>
    </div>
  );
}
