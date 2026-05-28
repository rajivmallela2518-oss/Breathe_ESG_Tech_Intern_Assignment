export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
