"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(password);
      router.replace("/kendelser");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kunne ikke logge ind.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex-1 flex items-center justify-center px-4">
      <form onSubmit={submit} className="card w-full max-w-sm p-8">
        <div className="text-center mb-8">
          <div className="text-2xl font-extrabold tracking-tight text-ink">
            EJNAR<span className="text-accent">.</span>
          </div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-ink-3 mt-2">
            Ejerskifteforsikring · Ankenævnet for Forsikrings praksis
          </div>
        </div>
        <label className="block text-xs font-semibold text-ink-2 mb-1.5" htmlFor="pw">
          Adgangskode
        </label>
        <input
          id="pw"
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Indtast adgangskode…"
          className="w-full rounded-lg border border-line px-3.5 py-2.5 text-sm outline-none
                     focus:ring-2 focus:ring-accent/40 focus:border-accent bg-paper text-ink"
        />
        {error && <p className="text-sm text-bad mt-3">{error}</p>}
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full mt-5 rounded-lg bg-accent text-white font-semibold text-sm py-2.5
                     hover:bg-accent-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Logger ind…" : "Log ind →"}
        </button>
        <p className="text-center text-[10.5px] text-ink-3 mt-5">
          Adgang kræver kode · kontakt administratoren
        </p>
      </form>
    </main>
  );
}
