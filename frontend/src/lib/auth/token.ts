const TOKEN_KEY = "nexusai_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    localStorage.setItem(TOKEN_KEY, token);
    // Also set standard session cookie for SSR if needed
    document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=604800; SameSite=Lax`;
  } catch (err) {
    console.error("Failed to store token", err);
  }
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    localStorage.removeItem(TOKEN_KEY);
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`;
  } catch (err) {
    console.error("Failed to clear token", err);
  }
}

// Aliases for idiomatic imports
export const getAccessToken = getStoredToken;
export const setAccessToken = setStoredToken;
export const removeAccessToken = clearStoredToken;
