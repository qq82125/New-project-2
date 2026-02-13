import 'server-only';

import fs from 'node:fs';

// API base URL for Server Components / Route Handlers.
//
// In Docker Compose production builds, Next.js may inline env vars at build time.
// If API_BASE_URL is missing during `next build`, falling back to localhost breaks
// because "localhost" points to the web container, not the host.
export function apiBase(): string {
  const fromEnv = process.env.API_BASE_URL;
  if (fromEnv) return fromEnv;

  // Prefer NEXT_PUBLIC_ var if present (useful for `next start` outside Docker).
  const fromPublicEnv = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (fromPublicEnv) return fromPublicEnv;

  // Only default to the Docker Compose service name when we are actually running in Docker.
  // Otherwise, `http://api:8000` will fail DNS resolution and crash Server Components.
  const isDocker = fs.existsSync('/.dockerenv');
  if (process.env.NODE_ENV === 'production' && isDocker) return 'http://api:8000';

  return 'http://localhost:8000';
}
