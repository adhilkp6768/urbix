const configured = process.env.NEXT_PUBLIC_API_URL;
export const API_URL = configured === undefined ? "http://127.0.0.1:8000" : configured;

async function send(path: string, init: RequestInit): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await fetch(`${API_URL}${path}`, init);
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 400 * (attempt + 1)));
    }
  }
  const detail = lastError instanceof Error ? lastError.message : "network error";
  throw new Error(`Could not reach the server (${detail}). Refresh the page.`);
}

async function read<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function apiGet<T>(path: string): Promise<T> {
  return read<T>(await send(path, { cache: "no-store" }));
}

export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  return read<T>(
    await send(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}
