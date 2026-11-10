"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  onSessionExpired,
  registerAccount,
} from "@/lib/api";
import { clearOfflineData } from "@/lib/offline";
import { removePushSubscription } from "@/lib/push";
import type {
  CurrentUser,
  LoginRequest,
  RegisterAccountRequest,
} from "@/lib/types";

type AuthState =
  | { status: "loading" }
  | { status: "signedOut" }
  | { status: "signedIn"; user: CurrentUser };

interface AuthContextValue {
  state: AuthState;
  login: (body: LoginRequest) => Promise<void>;
  register: (body: RegisterAccountRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return value;
}

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    // The backend decides who is signed in (from HttpOnly cookies the page
    // cannot read), so ask it, and listen for the session ending later.
    onSessionExpired(() => {
      void clearOfflineData();
      setState({ status: "signedOut" });
    });
    getCurrentUser().then(
      (user) => setState({ status: "signedIn", user }),
      () => setState({ status: "signedOut" }),
    );
    return () => onSessionExpired(null);
  }, []);

  const login = useCallback(async (body: LoginRequest) => {
    const user = await loginRequest(body);
    await clearOfflineData(); // nothing kept for the previous person may stay readable
    setState({ status: "signedIn", user });
  }, []);

  const register = useCallback(async (body: RegisterAccountRequest) => {
    const user = await registerAccount(body);
    await clearOfflineData();
    setState({ status: "signedIn", user });
  }, []);

  const logout = useCallback(async () => {
    await removePushSubscription(); // while still signed in, so the server can forget this browser
    try {
      await logoutRequest();
    } finally {
      // Even if the request failed, stop showing the user as signed in.
      await clearOfflineData();
      setState({ status: "signedOut" });
    }
  }, []);

  const value = useMemo(
    () => ({ state, login, register, logout }),
    [state, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
