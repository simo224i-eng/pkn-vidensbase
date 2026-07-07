"use client";

// Error boundary for alle app-sider — en uventet render-/datafejl må aldrig
// efterlade juristen med en blank skærm. NB: Next 16 giver `unstable_retry`
// (ikke `reset` som tidligere versioner).
export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <div className="flex items-center justify-center py-24 px-4">
      <div className="text-center max-w-md">
        <div className="text-2xl mb-2">⚠️</div>
        <h2 className="text-[15px] font-semibold text-ink mb-1.5">Noget gik galt</h2>
        <p className="text-[13px] text-ink-3 mb-1">
          Siden kunne ikke vises. Prøv igen — sker det gentagne gange, så genindlæs
          hele siden eller log ind på ny.
        </p>
        {error.digest && (
          <p className="text-[10.5px] text-ink-3 mb-4">Fejl-id: {error.digest}</p>
        )}
        <button
          onClick={() => unstable_retry()}
          className="rounded-lg bg-accent text-white font-semibold text-[13px] px-4 py-2 hover:bg-accent-700"
        >
          Prøv igen
        </button>
      </div>
    </div>
  );
}
