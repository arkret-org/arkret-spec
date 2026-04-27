# Media and Blob

Blob service provides content-addressed storage. Media profile defines metadata, thumbnails, authenticated download, encrypted attachments, and retention.

Required metadata:

- `blob_ref`
- `sha256`
- `size`
- `media_type`
- `created_by`
- `created_at`
- optional `encryption`

Blob services must verify digest and authorization before serving protected content.

## Authenticated Download

Protected content MUST use authenticated download by default. Public blobs MAY allow anonymous reads, but private Spaces, controlled organizations, E2EE attachments, and any media with access policy MUST require authentication.

Download requests SHOULD support:

```text
Authorization: Bearer <session_token>
X-Contrix-Wait-For: <sync_token>
Range: bytes=<start>-<end>
```

Rules:

- `X-Contrix-Wait-For` lets clients avoid a race where they have received a blob reference before the Blob service has materialized authorization. The service SHOULD wait until its local authorization frontier covers the token, otherwise return `stale_frontier` or `temporarily_unavailable`.
- Download authorization MUST bind actor DID, device/session, Space id, blob ref, purpose, and expiry. Private media MUST NOT be authorized only by unguessable URLs.
- Blob services MAY return short-lived signed download URLs or `307/308` redirects to object storage, but redirect tokens MUST be short-lived, single-blob, single-purpose, revocable, and visibility-preserving.
- Clients MUST recompute the content hash after following redirects and compare it with `blob_ref` / `sha256`.
- Range requests MUST use the same authorization context and must not leak invisible blob size, MIME, or existence.

Private or controlled blob responses MUST use conservative cache headers such as `Cache-Control: private, no-store`. Public immutable blobs MAY use long-lived caching only when the content address contains a strong hash and metadata does not leak private Space information.

Thumbnails, OCR text, transcodes, and media probe metadata are derived content. Server-generated private plaintext previews require the service to be listed in `plaintext_visible_services`; E2EE attachment previews SHOULD be generated and encrypted client-side or kept local.

