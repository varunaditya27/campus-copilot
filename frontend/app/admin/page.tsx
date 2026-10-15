"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { sectionsFor } from "@/lib/adminSections";
import { useAuth } from "../components/auth/AuthProvider";

// The dashboard's front door: go to the first section this role may use.
export default function AdminIndex() {
  const { state } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (state.status === "signedIn") {
      const first = sectionsFor(state.user.role)[0];
      if (first) router.replace(first.href);
    }
  }, [state, router]);
  return null;
}
