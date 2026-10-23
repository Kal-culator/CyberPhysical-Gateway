# Gateway V2 protocol

HTTP port 8080. All `/api/*` routes require `X-API-Key`. JSON UTF-8 except camera JPEG. `GET /health` is public and identifies `gateway-v2` plus simulation status. No public unlock route exists in real mode.

- `POST /api/access`: `{request_id: UUID, device_id: "door-1", fingerprint_id: integer|null, confidence: integer, force_review: boolean}`. Returns action `OPEN`, `DENY` or `PENDING`, request_id, reason, remaining_seconds (pending/final in-memory request) and simulation flag. ID must be unique per physical scan. Registered access queries MySQL; no payload field itself authorizes opening.
- `GET /api/requests/{id}`: poll pending decision. Pi allows only OPEN/DENY and refuses simulation responses. Deadline is server-enforced; expired approvals cannot revive a request.
- `POST /api/tamper`: `{reason: "MPU_MOTION"|"MPU_OFFLINE"|"FINGERPRINT_OFFLINE"|"LCD_OFFLINE"}`. Cancels pending access for door-1, logs and notifies. LCD_OFFLINE is reserved; current LCD failure handling is local stop, not continuous detection.
- `GET /api/security`: alert sequence, last reason and short inhibit status.
- `POST /api/camera`: JPEG bytes, max 300000 bytes and 1600×1200 dimensions. Updated image held only in memory; no automatic disk archive. Server estimates brightness from sampled pixels.
- `GET /api/events`: latest 50 decision records and camera status. Dashboard renders strings as text, not HTML.
- `POST /api/simulate/decision`: only exists when simulation=true; unavailable in real mode. In-memory simulation SQL is disposable. Pi real mode rejects it before any output action.

Server request IDs are idempotent during the process lifetime; a completed ID found in SQL after restart is denied rather than replaying OPEN. Concurrent pending requests for the single door are refused. Repeated Telegram callbacks are ignored. A successful SQL write is required before the server returns OPEN. Physical pulses are controlled only by the Pi and always bounded.

Telegram uses Java HttpClient over HTTPS, not shell commands. Both callback sender ID and message chat ID must match local configuration. Telegram updates are consumed by exactly one server process. Photo delivery failure does not cancel a successfully sent text approval.

Known limits: one door/device, shared API key, trusted LAN HTTP, no physical position sensor, no durable Pi offline event queue, no automatic service restart, no classification of intentional vs accidental sensor removal. A server can log OPEN even if the Pi loses network or refuses later because of tamper; the dashboard explicitly calls these decisions, not confirmed motion.
