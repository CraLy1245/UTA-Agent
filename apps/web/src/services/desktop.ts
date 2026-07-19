type DesktopBackend = {
  api_base_url: string;
  ws_base_url: string;
  data_root: string;
  has_secure_api_key: boolean;
};

declare global {
  interface Window {
    __SURVIVAL_DESKTOP_BACKEND__?: DesktopBackend;
    __TAURI_INTERNALS__?: unknown;
  }
}

export async function initializeDesktopBackend(): Promise<void> {
  if (!window.__TAURI_INTERNALS__) return;
  const { invoke } = await import("@tauri-apps/api/core");
  window.__SURVIVAL_DESKTOP_BACKEND__ =
    await invoke<DesktopBackend>("desktop_backend");
}

export function apiBaseUrl(): string {
  return (
    window.__SURVIVAL_DESKTOP_BACKEND__?.api_base_url ??
    import.meta.env.VITE_API_BASE_URL ??
    "/api"
  ).replace(/\/$/, "");
}

export function desktopWsBaseUrl(): string | undefined {
  return window.__SURVIVAL_DESKTOP_BACKEND__?.ws_base_url;
}

export function isDesktopRuntime(): boolean {
  return Boolean(window.__TAURI_INTERNALS__);
}

export function desktopHasSecureApiKey(): boolean {
  return window.__SURVIVAL_DESKTOP_BACKEND__?.has_secure_api_key ?? false;
}

export async function storeDesktopApiKey(value: string): Promise<void> {
  if (!isDesktopRuntime()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("store_desktop_api_key", { value });
  if (window.__SURVIVAL_DESKTOP_BACKEND__) {
    window.__SURVIVAL_DESKTOP_BACKEND__.has_secure_api_key = true;
  }
}
