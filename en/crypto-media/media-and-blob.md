# Media And Blob

## 1. Goal

The Blob service provides content-addressed storage. The media profile defines MIME metadata, thumbnails, authenticated download, encrypted attachments, and retention policy on top of blobs.

## 2. Blob Metadata

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "sha256": "hex...",
  "size": 1234,
  "media_type": "image/png",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "filename": "photo.png",
  "encryption": null
}
```

Fields:

| Field | Type | Required | Meaning and constraints |
| --- | --- | --- | --- |
| `blob_ref` | `string` | required | Content address, normally containing a strong hash. |
| `sha256` | `string` | required | Server-computed content hash. |
| `size` | `int` | required | Byte size. |
| `media_type` | `string` | optional | Declared or corrected MIME type. Defaults to `application/octet-stream`. |
| `created_by` | `did` | required | Uploading Actor or service DID. |
| `created_at` | `datetime` | required | Server receive time. |
| `filename` | `string` | optional | User-provided or server-generated filename; never used as a storage path. |
| `encryption` | `object/null` | required | Encrypted attachment metadata or `null`. |

Upload rules:

- Upload `Content-Type` is optional and defaults to `application/octet-stream`.
- Clients SHOULD provide an accurate `Content-Type`, but servers MUST treat declared MIME and filenames as untrusted metadata.
- If the declared MIME type is clearly wrong or dangerous, services MAY downgrade `media_type` to `application/octet-stream` and record a safety marker.
- Filenames MUST be sanitized for control characters, path separators, and excessive length, and must not affect `blob_ref` or storage paths.

## 3. Encrypted Attachment

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "encrypted": true,
  "alg": "xchacha20_poly1305",
  "key_ref": "mls_epoch:42",
  "nonce": "base64url...",
  "ciphertext_digest": "sha256:...",
  "cleartext_sha256": "hex...",
  "size": 1234,
  "media_type": "image/png"
}
```

## 4. Thumbnail

Thumbnail descriptor:

```json
{
  "source_blob_ref": "cx:blob:sha256:...",
  "thumbnail_blob_ref": "cx:blob:sha256:...",
  "width": 320,
  "height": 180,
  "media_type": "image/webp"
}
```

## 5. Authenticated Download

```text
GET /api/v1/blob/get?blob_ref=<ref>
```

Request fields:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| `blob_ref` | query | `string` | required | Content-addressed blob reference. |
| `Authorization` | header | `bearer token` or `device proof` | required for private blobs | Caller authentication. |
| `Range` | header | `string` | optional | Byte range request. |
| `X-Contrix-Wait-For` | header | `token` | optional | Wait for authorization materialization to reach a sync token. |

Response fields / headers:

| Field | Location | Type | Required | Meaning and constraints |
| --- | --- | --- | --- | --- |
| body | response | `bytes` | required for GET | Blob bytes. |
| `Content-Length` | header | `int` | optional | Content length when visible. |
| `Digest` | header | `string` | optional | Content digest. |
| `Cache-Control` | header | `string` | required | Cache policy; private content must be conservative. |
| `Content-Type` | header | `string` | required when visible | MIME type; must not leak invisible resources. |
| `Content-Disposition` | header | `string` | required when visible | `inline` or `attachment`, optionally with sanitized `filename`. |
| `Content-Range` | header | `string` | required for range responses | Returned byte range. |
| `Accept-Ranges` | header | `string` | optional | Services MAY return `bytes` when Range is supported. |
| `Location` | header | `url` | required for redirect | Short-lived download URL or object-store URL. |

Services MUST check actor authorization, Space visibility, retention / legal hold, and unsafe media policy before serving protected content.

Retention and erasure rules:

- Blob deletion MUST be authorized by Space policy, object ownership, account lifecycle, retention expiry, or a signed compliance decision.
- A blob under legal hold MUST NOT be physically deleted; services may hide it from normal views through redaction or policy.
- When a blob is erased, the service SHOULD retain only a minimal receipt: `blob_ref`, digest, size class if policy allows, erasure reason, executing service DID, time, and signature.
- Derived thumbnails, previews, transcodes, search text, embeddings, and notification snippets MUST be deleted or re-minimized when their source blob or source event is redacted or erased.
- E2EE attachment key destruction is an erasure mechanism for future access, but it does not revoke plaintext already downloaded or decrypted by authorized recipients.

Protected content MUST use authenticated download by default. Public blobs MAY allow anonymous reads, but private Spaces, controlled organizations, E2EE attachments, and any media with access policy MUST require authentication.

Rules:

- `X-Contrix-Wait-For` avoids a race where the client has a blob reference before the Blob service has materialized authorization. On timeout, return `stale_frontier` or `temporarily_unavailable`.
- Download authorization MUST bind actor DID, device/session, Space id, blob ref, purpose, and expiry. Private media MUST NOT be authorized only by unguessable URLs.
- Protected downloads MUST NOT accept session tokens, access tokens, or long-lived capabilities in query strings. Browser clients should use `Authorization`, service-worker proxying, or device-bound proof.
- Blob services MAY return short-lived signed download URLs or `307/308` redirects to object storage, but redirect tokens MUST be short-lived, single-blob, single-purpose, revocable, and visibility-preserving.
- `Location` values must not be cached long-term. If bytes are not fetched immediately, callers SHOULD request `/api/v1/blob/get` again for a fresh authorization context.
- Clients MUST recompute the content hash after following redirects and compare it with `blob_ref` / `sha256`.
- Range and HEAD requests MUST use the same authorization context and must not leak invisible blob size, MIME, filename, or existence.
- For invisible blobs, services SHOULD return the same `not_found` behavior as missing resources and avoid `Content-Length`, `Content-Type`, `Content-Disposition`, and `Accept-Ranges`.

### 5.1 Content-Type And Content-Disposition

When a resource is visible to the caller, download and HEAD responses MUST return `Content-Type`. The value SHOULD be the blob `media_type`, with these allowed safety corrections:

- Add charset for `text/*`.
- Return `application/octet-stream` when MIME is unknown or absent.
- Return `application/octet-stream` when the declared MIME is clearly wrong or dangerous.

Visible downloads and thumbnails MUST return `Content-Disposition`:

- Original downloads MUST use `inline` or `attachment`.
- Thumbnails SHOULD use `inline` and MAY use a server-generated filename.
- If a sanitized `filename` exists, `Content-Disposition` SHOULD include it. Otherwise omit filename.
- Services SHOULD only use `inline` for safe types and use `attachment` for other types.

Recommended safe inline types:

```text
text/css
text/plain
text/csv
application/json
application/ld+json
image/jpeg
image/gif
image/png
image/apng
image/webp
image/avif
video/mp4
video/webm
video/ogg
video/quicktime
audio/mp4
audio/webm
audio/aac
audio/mpeg
audio/ogg
audio/wave
audio/wav
audio/x-wav
audio/x-pn-wav
audio/flac
audio/x-flac
```

`text/html`, `text/javascript`, `image/svg+xml`, and unknown script-like content must not be inline by default.

### 5.2 Caching

Private or controlled blob responses MUST use conservative cache headers:

```text
Cache-Control: private, no-store
```

If the service explicitly allows client caching, it MAY use `private, max-age=<n>`, but the cache must remain bound to user / device authorization and must not be shared by proxies.

Public immutable blobs MAY use:

```text
Cache-Control: public, immutable, max-age=31536000
```

This is allowed only when the content address contains a strong hash and metadata does not leak private Space information.

### 5.3 Thumbnails And Previews

Thumbnails, OCR text, transcodes, and media probe metadata are derived content.

- E2EE attachment thumbnails SHOULD be generated and encrypted client-side or kept local.
- Services generating private plaintext thumbnails MUST be listed in `plaintext_visible_services`.
- Preview URLs, size, MIME, filename, and unsafe markers must follow Space policy and capability rules and cannot bypass body authorization.
- Thumbnails must bind source blob, generation parameters, generating service DID, and visibility. Deletion, redaction, retention, or legal-hold changes must re-evaluate derived content with the source content.

## 6. Asset Privacy Policy

Private asset download can leak IP address, online time, service relationships, blob size, and download frequency. Spaces SHOULD declare `cx.space.asset_privacy_policy`.

Download modes:

| Value | Meaning |
| --- | --- |
| `direct` | Client downloads directly from Blob/object storage. Suitable for public content or an explicitly accepted trust domain. |
| `provider_proxy` | A trusted media proxy fetches bytes to hide source storage details. |
| `ohttp_relay` | OHTTP or equivalent oblivious relay reduces the ability to observe both caller identity and target blob. |
| `client_mirror` | Client chooses among authorized mirrors and verifies content by hash. |

Private Spaces, E2EE attachments, and minimal-metadata Spaces SHOULD default to `provider_proxy` or `ohttp_relay`, not direct download. When `direct_download_allowed=false`, clients MUST NOT bypass proxy policy by following direct external URLs. Proxies do not gain plaintext access; E2EE attachments remain ciphertext.

The policy SHOULD be referenced by `cx.space.policy_components.asset` and included in the MLS-bound `policy_root`.

## 7. Safety

Blob services SHOULD validate declared size, compute digest server-side, reject digest mismatch, store MIME metadata as untrusted, support malware scanning metadata, support unsafe flags, and support garbage-collection grace periods.

## 8. Lifecycle

A blob MAY be garbage-collected if there are no live Entity references, the grace period has elapsed, it is not under legal hold, and policy permits deletion.
