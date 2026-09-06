import type { Metadata } from "next";
import { JetBrains_Mono, Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-body",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

const SITE = "https://kuchup.com";
const OG_IMAGE = `${SITE}/og-default.png`;
const LOGO = `${SITE}/static/icons/kuchup-bird.png`;

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    template: "%s | Relocation Jobs",
    default: "Relocation Jobs | Visa-Sponsored Software Roles in Europe",
  },
  description:
    "Find visa-sponsored software jobs in Europe. Search relocation-friendly roles in Germany, Netherlands, UK, Portugal, and Ireland — then track and tailor applications.",
  alternates: {
    canonical: `${SITE}/`,
  },
  icons: {
    icon: [{ url: "/static/icons/kuchup-bird.svg", type: "image/svg+xml" }],
    apple: [{ url: "/static/icons/apple-touch-icon.png" }],
  },
  openGraph: {
    title: "Relocation Jobs",
    description:
      "Find visa-sponsored engineering roles in Europe — before they're gone.",
    url: `${SITE}/`,
    siteName: "Relocation Jobs",
    type: "website",
    locale: "en_GB",
    images: [
      {
        url: OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "Kuchup — visa-sponsored software jobs in Europe",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Relocation Jobs",
    description:
      "Find visa-sponsored engineering roles in Europe — before they're gone.",
    images: [OG_IMAGE],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        name: "Relocation Jobs",
        alternateName: "KUCHUP",
        url: `${SITE}/`,
        logo: LOGO,
        description:
          "Curated visa-sponsored software engineering roles across Europe.",
        sameAs: ["https://github.com/AminMortezaie/relocation-jobs"],
      },
      {
        "@type": "WebSite",
        name: "Relocation Jobs",
        url: `${SITE}/`,
        description:
          "Find visa-sponsored software engineering roles in Germany, Netherlands, UK, Portugal, and Ireland.",
      },
      {
        "@type": "SoftwareApplication",
        name: "Kuchup",
        alternateName: "Relocation Jobs",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        url: `${SITE}/`,
        description:
          "Search and track visa-sponsored software engineering roles in Europe; tailor applications with Claude or Cursor via MCP.",
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "USD",
          description: "Public preview is free; signed-in Free includes a board company cap and MCP daily quota.",
        },
      },
    ],
  };

  return (
    <html lang="en" className={`${manrope.variable} ${jetbrains.variable}`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Lexend:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={manrope.className}>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
      </body>
    </html>
  );
}
