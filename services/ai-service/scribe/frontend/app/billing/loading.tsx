export default function BillingLoading() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      <div className="h-8 bg-slate-200 rounded w-48 mb-1" />
      <div className="h-4 bg-slate-100 rounded w-80" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 h-20" />
        ))}
      </div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-4 border-b bg-slate-50 h-12" />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="px-6 py-4 border-b flex gap-8">
            <div className="h-4 bg-slate-100 rounded w-20" />
            <div className="h-4 bg-slate-100 rounded w-28" />
            <div className="h-4 bg-slate-100 rounded w-20" />
            <div className="h-4 bg-slate-100 rounded w-16" />
            <div className="h-4 bg-slate-100 rounded w-24" />
          </div>
        ))}
      </div>
    </div>
  );
}
