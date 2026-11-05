import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { TopBar } from "@/components/TopBar";
import { SiteFooter } from "@/components/SiteFooter";
import { PageBackdrop } from "@/components/PageBackdrop";
import { FlowBar, FlowRail } from "@/components/FlowRail";
import { SessionProvider } from "@/lib/session";

import "./globals.css";

export const metadata: Metadata = {
  title: "VoicePath",
  description:
    "Describe the work you have done, in your own language. VoicePath finds "
    + "the openings and training near you that fit it, and says why.",
};

export const viewport: Viewport = {
  // The browser's own bar matches the page, light or dark.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f3ec" },
    { media: "(prefers-color-scheme: dark)", color: "#14120e" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Anek covers Tamil and Devanagari, so a Tamil headline has the same
            weight and presence as an English one instead of dropping to a
            system face at a different optical size. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600&family=Instrument+Sans:wght@400;500;600&family=Anek+Tamil:wght@400;500;600&family=Anek+Devanagari:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <SessionProvider>
          {/* Behind everything, on every screen including admin -- a plainer
              page is still a page, and the marks are quiet enough that the
              line between the two surfaces stays where it was. */}
          <PageBackdrop />
          <FlowRail />
          <div className="relative z-10 flex min-h-dvh flex-col">
            <TopBar />
            {/* Under the header, in the document, for every width the rail in
                the gutter cannot fit. Renders nothing off the flow. */}
            <FlowBar />
            <main className="flex flex-1 flex-col">{children}</main>
            <SiteFooter />
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}
