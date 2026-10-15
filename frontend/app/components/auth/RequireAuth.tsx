"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

// Shows its children only to a signed-in student; everyone else is sent to /login.
export default function RequireAuth({
  children,
}: {
  children: React.ReactNode;
}) {
  const { state } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (state.status === "signedOut") {
      router.replace("/login");
    }
  }, [state.status, router]);

  if (state.status !== "signedIn") {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-faint">
          Loading…
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
