export default function EmptyState({ message = "No data." }) {
  return (
    <div className="text-center py-16 text-sm text-gray-400">{message}</div>
  );
}
