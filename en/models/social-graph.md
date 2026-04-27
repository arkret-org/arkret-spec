# Social Graph and Feed Draft

## 1. Scope

Contrix supports social publication, follow/contact relationships, timelines, circles, and organization announcements, while keeping them as object-graph and view extensions rather than replacing the protocol root model.

The scope includes:

- public feed, similar to public broadcast models
- circle feed, similar to limited-audience peer model
- organization feed for announcements and official activity
- follow/contact/circle relations
- audience policy, forwarding, replies, search, deletion, and E2EE boundaries

## 2. Core Principles

Social capabilities must follow:

- DID / Principal remains the identity root.
- Post / Feed / Circle / Profile are Object / Relation / View constructs, not protocol roots.
- Discoverable does not mean interactable; readable does not imply reply/forward/index.
- Circle content must be authorized by audience policy; hiding in UI is not a valid privacy mechanism.
- Organization feed officiality MUST be proven by Organization DID or `cx.space.organization` endorsement.

## 3. Standard Entity Types

### 3.1 `social_post`

`social_post` is content projected into timelines.

```json
{
  "entity_type": "social_post",
  "author": "did:uuid:alice",
  "content": {
    "format": "contrix.richtext.v1",
    "body": "Ship notes for today"
  },
  "attachments": [],
  "audience_ref": "cx:audience:public",
  "reply_policy": "followers",
  "reshare_policy": "public_allowed",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 3.2 `social_feed`

`social_feed` is an entry feed object or timeline source, such as personal homepage, organization announcement, or project updates.

```json
{
  "entity_type": "social_feed",
  "owner": "did:web:acme.example",
  "feed_kind": "organization_announcement",
  "discoverability": "public",
  "default_audience": "public"
}
```

### 3.3 `social_circle`

`social_circle` defines a recipient set managed by a poster.

```json
{
  "entity_type": "social_circle",
  "owner": "did:uuid:alice",
  "circle_id": "cx:circle:close-friends",
  "visibility": "private",
  "membership_policy": "owner_managed",
  "member_refs": [
    "did:uuid:bob",
    "did:uuid:carol"
  ]
}
```

Circle membership SHOULD be minimally disclosed by default.

## 4. Standard Relations

| Relation | Meaning |
| --- | --- |
| `follows` | A subscribes to B’s public or allowlisted feed. |
| `contact` | A has contact relation to B, used for presence, DM, and circle preselection. |
| `circle_member` | An actor is a member of a specific circle. |
| `blocks_social` | Social-layer blocking relation, usually mapped to personal blocklist. |
| `reposts` | A re-posts B’s post. |
| `quotes` | A quotes B’s post and adds extra content. |
| `likes` | A provides lightweight feedback. |
| `replies_to` | A post replies to another post. |

Follow is often asymmetric; contact is usually bidirectional or mutually confirmed. Circle audience is not equivalent to the follow graph.

## 5. Audience Policy

`cx.social.audience_policy` defines read/interact/index boundaries of each feed or post:

```json
{
  "type": "cx.social.audience_policy",
  "audience_id": "cx:audience:close-friends",
  "owner": "did:uuid:alice",
  "mode": "circle",
  "readers": {
    "circle_refs": ["cx:circle:close-friends"],
    "actor_refs": [],
    "claim_selectors": []
  },
  "interaction": {
    "reply": "readers_only",
    "react": "readers_only",
    "reshare": "disabled",
    "quote": "disabled"
  },
  "indexing": {
    "public_search": false,
    "directory_preview": false,
    "external_crawlers": false
  },
  "snapshot_at_publish": true
}
```

`mode` values:

- `public`: visible for public search/feed index.
- `followers`: visible to followers.
- `contacts`: visible to contacts.
- `circle`: visible to specific circle members.
- `organization`: visible to organization claim / membership holders.
- `space_members`: visible to members of a specified Space.
- `direct`: explicit actor allowlist.
- `private`: visible only to author-owned devices.

`snapshot_at_publish=true` freezes audience at publish time. Removing someone later does not grant access to already-published historical content unless retention / encryption model says otherwise. Privacy-sensitive circle posts SHOULD use publish-time snapshots.

## 6. Public Broadcast Model

Public feed profile should use:

- `social_feed.discoverability=public`
- `audience_policy.mode=public`
- `indexing.public_search=true`
- `reshare_policy` enabled for repost / quote if desired

Public feed distribution can be materialized from Directory / Index / Relay / AppView.

## 7. Circle Feed Model

Circle feed must be enforced at protocol level.

Circle feed SHOULD use:

- `audience_policy.mode=circle` or `contacts`
- `snapshot_at_publish=true`
- `indexing.public_search=false`
- `reshare=disabled`
- `quote=disabled`
- `reply=readers_only`

Visibility rules:

- Subjects outside snapshots MUST NOT discover post content from directory / index / relay preview.
- If E2EE is used, payload SHOULD be encrypted to snapshot device set or MLS group.
- Index services MAY index encrypted metadata only and must not expose plain text, attachments, comment, or reaction sets.
- Comments/reactions inherit original audience and must not widen it.

## 8. Organization Social Feed

Organization feeds MAY include announcements, hiring, logs, and member activity.

They MUST satisfy:

1. Owner is Organization DID or service/actor DID delegated by Organization DID.
2. Officiality is proven by Organization DID signature.
3. If `official Space` is claimed, verify `cx.space.organization`.
4. Directory visibility for official marks MUST verify source organization authority.

Audience for organization feeds may be:

- `public`
- `organization`
- `space_members`
- `claim_selectors`

Organization member list and read-marker states are not public by default.

## 9. Feed Space Recommendation

Implementations MAY create dedicated Spaces:

- personal public Space
- personal circle Space
- organization announcement Space
- community Space

Public broadcast may be emitted directly from author Principal Repo and materialized by Index/AppView; circle and internal organization feeds should use Space membership / MLS or audience snapshots for privacy and replay.

## 10. Moderation and Blocking

Social layer must reuse moderation and personal blocklist:

- Author MAY block actor from reply/quote/DM and social interaction.
- Space/Organization moderation MAY quarantine, hide, deny interaction, or remove from feed.
- Directory and public index MUST apply discoverability + audience + moderation checks.
- Historical interactions of blocked actors are filtered based on blocklist and policy context.

## 11. Federation and Portability

Public social content SHOULD be portable:

- post is stored in author Principal Repo
- feed projection is materialized by authorized indexes
- follow graph can be exported/imported
- handle change should not alter historical author DID

Restricted circle content MUST prioritize privacy:

- export must preserve audience policy and encryption status
- circle membership must not be exported in plaintext to unauthorized receiver
- external migration must not leak fresh post keys to old external services

## 12. Security Requirements

Implementations MUST prevent:

- existence leak through search ranking, recommendation, or error side-channel
- audience-size inference from reactions/replies
- private DID / pairwise DID / private handle leakage in indexes
- organization internal feeds being marked as public
- confusing follow/contact/circle relation semantics
- repost or quote widening audiences incorrectly

## 13. Conformance

`cx.profile.social.v1` SHOULD test:

- public post indexing
- follower timeline projection
- circle audience snapshot
- unauthorized circle invisibility
- reply/reaction audience inheritance
- repost disable enforcement
- official organization feed verification
- personal blocklist interaction filtering
- redaction / tombstone projection

