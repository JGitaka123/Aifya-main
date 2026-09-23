export default function ClinicianLoading() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      <div className="flex justify-between items-end border-b pb-4">
        <div>
          <div className="h-8 bg-slate-200 rounded w-56 mb-2" />
          <div className="h-4 bg-slate-100 rounded w-72" />
        </div>
        <div className="text-right">
          <div className="h-3 bg-slate-200 rounded w-40 mb-1" />
          <div className="h-3 bg-slate-200 rounded w-32" />
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 h-64" />
          <div className="bg-white rounded-xl border border-slate-200 p-6 h-48" />
        </div>
        <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 p-6 min-h-[600px]">
          <div className="h-6 bg-slate-200 rounded w-48 mb-6" />
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-4 bg-slate-100 rounded" style={{ width: `${100 - i * 10}%` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
