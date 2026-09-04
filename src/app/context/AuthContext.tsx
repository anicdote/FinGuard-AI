/**
 * FinGuard AI — Authentication Context
 *
 * Authentication flow:
 *
 * 1. User enters email + password.
 * 2. Backend validates the credentials.
 * 3. Backend creates a biometric challenge.
 * 4. Frontend polls that challenge.
 * 5. Backend communicates with the local Arduino/R307S sensor.
 * 6. After successful fingerprint verification, backend returns JWTs.
 * 7. Frontend stores the JWTs and loads the current user.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  authApi,
  tokenStore,
} from "../services/api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface User {
  _id: string;
  email: string;
  name: string;
  role:
    | "admin"
    | "manager"
    | "officer"
    | "analyst";
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;

  beginLogin: (
    email: string,
    password: string,
  ) => Promise<any>;

  checkLoginChallenge: (
    challengeId: string,
  ) => Promise<any>;

  logout: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────────────────────────

const AuthContext =
  createContext<AuthContextValue | null>(
    null,
  );

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<User | null>(null);

  const [loading, setLoading] =
    useState(true);

  // ─────────────────────────────────────────────────────────────────────────
  // Restore existing authenticated session
  // ─────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    let mounted = true;

    async function restoreSession() {
      if (!tokenStore.access) {
        if (mounted) {
          setLoading(false);
        }

        return;
      }

      try {
        const currentUser =
          await authApi.me();

        if (mounted) {
          setUser(currentUser);
        }
      } catch (error) {
        console.warn(
          "Unable to restore FinGuard session:",
          error,
        );

        tokenStore.clear();

        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void restoreSession();

    return () => {
      mounted = false;
    };
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Start password authentication + biometric challenge
  // ─────────────────────────────────────────────────────────────────────────

  const beginLogin = useCallback(
    async (
      email: string,
      password: string,
    ) => {
      return authApi.beginLogin(
        email,
        password,
      );
    },
    [],
  );

  // ─────────────────────────────────────────────────────────────────────────
  // Poll biometric challenge
  // ─────────────────────────────────────────────────────────────────────────
  //
  // IMPORTANT:
  //
  // The current backend implementation returns:
  //
  //   challenge_id
  //   purpose
  //   status
  //   message
  //   expires_at
  //
  // and challenge_token is null.
  //
  // Therefore this frontend function intentionally accepts ONLY the
  // challenge ID.
  //
  // The browser never communicates directly with the Arduino.
  // It polls the backend, which handles the local fingerprint service.
  // ─────────────────────────────────────────────────────────────────────────

  const checkLoginChallenge =
    useCallback(
      async (challengeId: string) => {
        const challenge =
          await authApi.checkLoginChallenge(
            challengeId,
          );

        /*
         * authApi.checkLoginChallenge()
         * stores the JWTs when the backend reports
         * successful biometric authentication.
         *
         * Once the access token exists, load the
         * authenticated user into React state.
         */
        if (
          challenge?.accessToken
        ) {
          try {
            const currentUser =
              await authApi.me();

            setUser(currentUser);
          } catch (error) {
            console.error(
              "Biometric login succeeded but user profile could not be loaded:",
              error,
            );

            throw error;
          }
        }

        /*
         * Be defensive in case a backend response
         * reaches the frontend without snake_case
         * normalization.
         */
        if (
          challenge?.access_token
        ) {
          try {
            const currentUser =
              await authApi.me();

            setUser(currentUser);
          } catch (error) {
            console.error(
              "Biometric login succeeded but user profile could not be loaded:",
              error,
            );

            throw error;
          }
        }

        return challenge;
      },
      [],
    );

  // ─────────────────────────────────────────────────────────────────────────
  // Logout
  // ─────────────────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);

    if (
      typeof window !==
      "undefined"
    ) {
      window.location.href =
        "/login";
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Context
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        beginLogin,
        checkLoginChallenge,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used within AuthProvider",
    );
  }

  return context;
}