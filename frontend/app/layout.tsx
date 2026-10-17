import type { Metadata } from "next";
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

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${hanken.variable} antialiased`}
    >
      <body className="flex min-h-dvh flex-col">
        <AuthProvider>
          <Header />
          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </AuthProvider>
      </body>
    </html>
  );
}
