import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h1 className="text-6xl font-bold text-slate-300 mb-4">404</h1>
      <h2 className="text-2xl font-semibold text-slate-700 mb-2">Page Not Found</h2>
      <p className="text-slate-500 mb-8 max-w-md">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        href="/"
        className="px-6 py-2.5 bg-medical-blue text-white rounded-lg font-medium hover:bg-medical-blue-dark transition-colors"
      >
        Return to Dashboard
      </Link>
    </div>
  );
}
