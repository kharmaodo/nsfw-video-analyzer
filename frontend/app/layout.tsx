import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NSFW Video Analyzer",
  description: "Centre de contrôle pour la collecte et l’analyse échantillonnée de vidéos.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className="antialiased">{children}</body>
    </html>
  );
}
