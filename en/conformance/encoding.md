# Encoding, IDs, Hashes, Signatures

Contrix canonical JSON uses UTF-8, sorted object keys, no insignificant whitespace, valid JSON numbers, RFC 3339 UTC timestamps, and snake_case fields.

Default digest:

```text
sha256:<lowercase_hex_digest>
```

Default ID:

```text
cx:<kind>:<ulid>
```

Default proof is detached JWS bound to payload hash, actor DID, verification method, audience/domain where applicable, and creation time.

## Rank

Ordered-list rank values MUST use the `cx.rank.lexofractional.v1` profile unless a Space schema explicitly declares another rank profile.

Rules:

- The alphabet is fixed to ASCII `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`.
- Rank values MUST be 1..128 characters and every character MUST be in that alphabet.
- Ordering MUST be lexicographic by the fixed alphabet; when one rank is a prefix of another, the shorter rank sorts first.
- `rank_between(left, right)` MUST return a rank strictly between the two boundaries; either boundary MAY be null to represent the beginning or end of the container.
- The midpoint algorithm compares characters left to right. Missing left characters have value `-1`; missing right characters have value `alphabet_length`. If `right_value - left_value > 1`, append `floor((left_value + right_value) / 2)` and stop; otherwise copy the current left character and continue. If the left character is missing and there is no gap, copy the first alphabet character and continue.
- Reducers MUST reject ranks longer than 128 characters. Clients SHOULD request or submit `cx.container.rebalance` when dense inserts would exceed that limit.
- Rebalance assignment generation MUST use the untrimmed canonical ordered set. Sort active edges by reducer order, choose the smallest width `w` where `alphabet_length^w >= 2 * (item_count + 1)`, then assign item `i` the fixed-width base62 encoding of `floor(i * alphabet_length^w / (item_count + 1))`.
- Rebalance assignments MUST cover all active edges in the container and MUST NOT add, delete, or move edges. A CAS mismatch rejects the entire operation without partial application.

