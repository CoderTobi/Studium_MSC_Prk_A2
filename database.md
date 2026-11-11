
# Firestore Schema Plan

## 1. Overview

```
users  (collection)
└── {uid}  (document: per-user metadata)
    └── items  (subcollection)
        └── {itemId}  (document: one shopping list item)
```

There is only **one collection tree**. Some things are deliberately **not** stored in Firestore:

| Data | Where it lives | Why |
|---|---|---|
| AI recommendations | Nowhere (they're temporary) | The API says recommendations aren't stored. Accepting one goes through the item endpoints. |
| Prompts and model responses | Nowhere | The spec says not to log them by default, so they shouldn't be persisted either. |
| Model name and token usage | Backend logs | The spec asks for logging, not storage. |
| Rate limit counters | Backend memory | See §6. |
| Email, display name, other profile data | Firebase Auth only | The backend only needs the `uid`. This keeps personal data to a minimum (GDPR). |

## 2. `users/{uid}`: user metadata document

The document ID is the Firebase Auth `uid`, taken **only** from the verified token.

| Field | Type | Description |
|---|---|---|
| `itemCount` | integer | How many items are on the list right now. Used to enforce `ITEM_LIMIT` (409) atomically. |
| `nextSeq` | integer | Counter that only goes up. Each new item gets the next value as its sort key. It never goes down, so gaps after deletes are fine. |
| `createdAt` | timestamp | When this document was first created (server timestamp). |
| `updatedAt` | timestamp | When the list last changed (server timestamp). |

- **Created lazily:** the document appears in the same transaction as the user's first item write. `GET /items` with no user document just returns an empty list.
- **Why a counter document instead of a `count()` query:** a read-check-write transaction on one document is the standard way to enforce a limit without race conditions. Two parallel batch requests can't both slip past the limit. The cost is that one user's writes run one after another. For a shopping list that's not a problem.

## 3. `users/{uid}/items/{itemId}`: item document

The document ID is a **Firestore auto-ID** (20 alphanumeric characters). It matches the API's `ItemId` pattern `^[A-Za-z0-9_-]{1,64}$` and becomes `Item.id` in the API.

| Field | Type | Exposed in API | Rules |
|---|---|---|---|
| `name` | string | ✅ `name` | Trimmed, 1–100 characters, contains a non-whitespace character, no control characters. Stored as plain text. |
| `source` | string (enum) | ✅ `source` | `"manual"` or `"ai_recommendation"`. Same values as the API, so no mapping is needed. Defaults to `"manual"`. |
| `seq` | integer | ❌ internal | Sort key, taken from `users/{uid}.nextSeq`. |
| `createdAt` | timestamp | ❌ internal | Server timestamp, for debugging and auditing. |

**Why `seq` and not just `createdAt`:** every item in one batch write gets the *same* server timestamp, so `createdAt` can't keep "request order" for `/items/batch` or "oldest first" for `GET /items`. A per-user `seq` counter gives an order that's fully determined. Items in a batch get consecutive `seq` values in request order.

## 4. Mapping API operations to Firestore

| Endpoint | Firestore operation |
|---|---|
| `GET /health` | None. Health must not depend on Firestore. |
| `GET /items` | Query `users/{uid}/items` ordered by `seq` ascending, limited to `ITEM_LIMIT`. Return `{id, name, source}` for each item. |
| `POST /items` | **Transaction:** read `users/{uid}` → if `itemCount + 1 > ITEM_LIMIT`, return 409 → create the item with `seq = nextSeq` → update the user document (`itemCount + 1`, `nextSeq + 1`, `updatedAt`). |
| `POST /items/batch` | **Same transaction with n items.** Writes either all n items or none, as the API requires. At most 20 items plus 1 user document is 21 writes, far below Firestore's 500-writes-per-transaction limit. |
| `DELETE /items/{itemId}` | **Transaction:** read `users/{uid}/items/{itemId}` → if it doesn't exist, return 404 `ITEM_NOT_FOUND` → delete it and update the user document (`itemCount − 1`, `updatedAt`). |
| `POST /recommendations` | None. |

## 5. Data isolation and security

- **Isolation comes from the path structure.** Every path is built as `users/{token-uid}/…`. Another user's item simply doesn't exist under your path. That gives the API's "foreign item = 404" rule automatically, with no ownership check that could be forgotten.
- **Why a subcollection instead of a top-level `items` collection with an `ownerUid` field:** with the subcollection, a missing filter can't leak data, no composite index on `ownerUid` + `seq` is needed, and the 404 behaviour comes for free.
- **Why not an array inside the user document:** deleting by ID would be awkward, the API needs item IDs, and every change would rewrite the whole list.
- **Validate the uid before building a path.** In debug mode the `uid` comes from an *unverified* token, so it could contain `/` or other characters that change the path (for example `victim/items/x`). Only accept uids that are 1–128 characters long, contain no `/`, are not `.` or `..`, and don't match the reserved `__…__` pattern.
- **Validate `itemId` against the API pattern before any Firestore lookup.** An invalid ID returns 400 `VALIDATION_ERROR`.
- **Firestore Security Rules: deny all client access.** The backend uses the Admin SDK, which bypasses the rules. The frontend only talks to Firebase *Auth*, never to Firestore. So the rules should simply deny every read and write. This blocks anyone who tries to use the Firebase web config to reach Firestore directly.

## 6. Rate limiting (not in Firestore)

I recommend keeping the per-uid rate limit buckets (general and ai) **in the backend's memory**. There is exactly one backend container, so memory is enough. Storing counters in Firestore would cost one extra write per request and cause write contention on hot documents.

Trade-off: the counters reset when the backend restarts, which is acceptable for this project. If you ever run several backend instances, you could add a `rateLimits/{uid}` collection with window counters.

## 7. Indexes

- `items` ordered by `seq`: Firestore creates single-field indexes automatically, so **no composite indexes are needed**.

## 8. Example data

```
users/kX9aB2...                       (uid)
  itemCount: 3
  nextSeq:   5
  createdAt: 2026-11-11T10:00:00Z
  updatedAt: 2026-11-11T10:05:00Z

users/kX9aB2.../items/3fQk9ZbXc1LmN0pR7sTu
  name: "Milk"        source: "manual"             seq: 1   createdAt: …
users/kX9aB2.../items/aB7cD9eF1gH3iJ5kL7mN
  name: "Spaghetti"   source: "ai_recommendation"  seq: 3   createdAt: …
users/kX9aB2.../items/Zr4tY6uI8oP0aS2dF4gH
  name: "Tomatoes"    source: "ai_recommendation"  seq: 4   createdAt: …
```

Here `seq: 2` was deleted earlier, so there's a gap. That's expected.




