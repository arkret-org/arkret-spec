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

