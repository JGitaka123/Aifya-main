export default function Loading() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      <div className="h-10 bg-slate-200 rounded-lg w-64" />
      <div className="h-4 bg-slate-200 rounded w-96" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div className="h-6 bg-slate-200 rounded w-32" />
            <div className="h-4 bg-slate-100 rounded w-full" />
            <div className="h-4 bg-slate-100 rounded w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}
