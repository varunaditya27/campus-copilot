import { SerwistProvider } from "@serwist/turbopack/react";
import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk } from "next/font/google";
import AuthProvider from "./components/auth/AuthProvider";
import Header from "./components/layout/Header";
import "./globals.css";

const hanken = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Campus Copilot",
  description:
    "An agentic campus assistant — grounded answers, live tools, and human-confirmed actions.",
};

export const viewport: Viewport = {
  themeColor: "#ecebe7",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${hanken.variable} antialiased`}
    >
      <body className="flex min-h-dvh flex-col">
        <SerwistProvider
          swUrl="/serwist/sw.js"
          disable={process.env.NODE_ENV === "development"}
        >
          <AuthProvider>
            <Header />
            <div className="flex min-h-0 flex-1 flex-col">{children}</div>
          </AuthProvider>
        </SerwistProvider>
      </body>
    </html>
  );
}
