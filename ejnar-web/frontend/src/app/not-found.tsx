import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1 flex items-center justify-center px-4 py-24">
      <div className="text-center">
        <div className="text-[44px] font-extrabold tracking-tight text-ink">
          404<span className="text-accent">.</span>
        </div>
        <h1 className="text-[15px] font-semibold text-ink mt-1 mb-1.5">Siden findes ikke</h1>
        <p className="text-[13px] text-ink-3 max-w-sm mb-6">
          Linket kan være forældet — hvis det pegede på en kendelse, kan den være
          udgået af registret ved en dataopdatering.
        </p>
        <Link
          href="/kendelser"
          className="inline-block rounded-lg bg-accent text-white font-semibold text-[13px] px-4 py-2 hover:bg-accent-700"
        >
          Til kendelserne →
        </Link>
      </div>
    </main>
  );
}
