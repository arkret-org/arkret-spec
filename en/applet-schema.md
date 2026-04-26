# Applet Schema

Defines Applet registration, namespace patterns, transaction endpoint, query actor, query space, protocol metadata, and bridge error event.

Core endpoint:

```text
PUT /api/v1/applet/transactions/{txn_id}
```

Transactions are idempotent. Applets must validate source service DID, HTTP message signature, and event signatures.
