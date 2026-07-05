import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ejnar — Ejerskifteforsikring",
  description: "Praksisdatabase for Ankenævnet for Forsikrings afgørelser om ejerskifteforsikring.",
};

const FONT_STACK =
  "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="da" className="h-full antialiased" style={{ fontFamily: FONT_STACK }}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
