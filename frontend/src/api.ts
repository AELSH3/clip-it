export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const payload = (await response.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "http_error",
      payload?.error?.message ?? "The request failed.",
    );
  }
  return payload as T;
}

export function uploadVideo(
  file: File,
  title: string,
  onProgress: (fraction: number) => void,
): Promise<import("./types").Video> {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);
    if (title.trim()) body.append("title", title.trim());
    const request = new XMLHttpRequest();
    request.open("POST", "/api/videos");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onerror = () => reject(new ApiError(0, "network", "The upload did not reach the server."));
    request.onload = () => {
      const payload = JSON.parse(request.responseText || "{}") as {
        error?: { code?: string; message?: string };
      };
      if (request.status >= 200 && request.status < 300) {
        resolve(payload as import("./types").Video);
        return;
      }
      reject(new ApiError(request.status, payload.error?.code ?? "http_error", payload.error?.message ?? "Upload failed."));
    };
    request.send(body);
  });
}
