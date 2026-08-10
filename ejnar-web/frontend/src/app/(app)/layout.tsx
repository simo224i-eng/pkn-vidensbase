"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuthStatus } from "@/lib/useAuth";
import { FilterProvider } from "@/lib/FilterContext";
import { logout } from "@/lib/api";

const TABS = [
  { href: "/kendelser", label: "Kendelser" },
  { href: "/statistik", label: "Statistik" },
  { href: "/assistent", label: "AI Assistent" },
  { href: "/sagsmapper", label: "Sagsmapper" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const status = useAuthStatus();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      // Tag den ønskede side med til login, så delte links (fx en kendelse)
      // lander rigtigt EFTER login i stedet for på forsiden.
      const next = pathname && pathname !== "/" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <main className="flex-1 flex items-center justify-center">
        <div className="text-sm text-ink-3">Indlæser…</div>
      </main>
    );
  }

  return (
    <FilterProvider>
      <div className="min-h-screen flex flex-col">
        <header className="border-b border-line bg-paper sticky top-0 z-30">
          <div className="max-w-6xl mx-auto px-5 flex items-center justify-between h-14">
            <div className="flex items-center gap-8">
              <Link href="/kendelser" className="font-extrabold tracking-tight text-ink text-[17px]">
                EJNAR<span className="text-accent">.</span>
              </Link>
              <nav className="flex gap-1">
                {TABS.map((t) => {
                  const active = pathname?.startsWith(t.href);
                  return (
                    <Link
                      key={t.href}
                      href={t.href}
                      className={`px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors ${
                        active ? "bg-accent-50 text-accent-700" : "text-ink-3 hover:text-ink hover:bg-surface"
                      }`}
                    >
                      {t.label}
                    </Link>
                  );
                })}
              </nav>
            </div>
            <button
              onClick={() => logout().then(() => router.replace("/login"))}
              className="text-[12px] text-ink-3 hover:text-ink font-medium"
            >
              Log ud
            </button>
          </div>
        </header>
        <main className="flex-1 max-w-6xl w-full mx-auto px-5 py-6">{children}</main>
      </div>
    </FilterProvider>
  );
}
