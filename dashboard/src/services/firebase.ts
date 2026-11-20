/**
 * Firebase Realtime Database runtime has been removed per architecture decision (18/11/2026).
 * All runtime state is stored exclusively in MySQL/InnoDB and served via FastAPI REST + WebSocket/SSE.
 */
export const db = null;
