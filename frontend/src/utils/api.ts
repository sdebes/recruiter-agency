export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });

  const text = await response.text();

  if (!response.ok) {
    let errorMessage = `HTTP Error: ${response.status}`;
    try {
      const errorJson = JSON.parse(text);
      errorMessage = errorJson.detail || errorMessage;
    } catch {
      errorMessage = text || errorMessage;
    }
    throw new Error(errorMessage);
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`Unexpected response: ${text.slice(0, 100)}`);
  }
}
