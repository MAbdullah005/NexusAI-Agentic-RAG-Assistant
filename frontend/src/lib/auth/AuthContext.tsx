"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api } from "../api/client";
import { getAccessToken, setAccessToken, removeAccessToken } from "./token";
import type { LoginRequest, SignupRequest, User } from "../../types/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginRequest) => Promise<User>;
  signup: (data: SignupRequest) => Promise<{ message: string }>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const router = useRouter();
  const pathname = usePathname();

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return null;
    }

    try {
      const userData = await api.getMe();
      setUser(userData);
      return userData;
    } catch (err) {
      console.warn("Failed to fetch current user with existing token:", err);
      removeAccessToken();
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (credentials: LoginRequest): Promise<User> => {
    const response = await api.login(credentials);
    setAccessToken(response.access_token);
    const userData = await api.getMe();
    setUser(userData);
    return userData;
  };

  const signup = async (data: SignupRequest): Promise<{ message: string }> => {
    return api.signup(data);
  };

  const logout = () => {
    removeAccessToken();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        login,
        signup,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

