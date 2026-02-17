# Data Ingestion Coverage Gaps

This document tracks gaps between incoming Apify data and what gets stored in the database.

## How to Read the Logs

When a dataset is ingested, you'll see:
1. **First item keys**: All available fields from Apify
2. **URL-related fields**: Extracted URL fields
3. **Author object keys**: Structure of `author` object (for user_handle debugging)
4. **Engagement fields (raw)**: Raw engagement values before mapping
5. **STORED in DB**: What actually got saved (shows NULL gaps)

## Current Gaps Identified

### 1. `user_handle` = NULL (Twitter/X data)

**Incoming fields available:**
- `author` (object) - contains user info
- `inReplyToUsername` - reply thread username

**Current mapping logic:**
- Checks: `author.username`, `user.username`, `ownerUsername`

**Gap:**
- `author` object may have different structure (e.g., `author.username` might not exist)
- Need to inspect actual `author` object structure from Twitter/X Apify actor

**Example from logs:**
```
Incoming: author={...} (object present)
Stored: user_handle=None (but user_name=The Nation Nigeria works)
```

**Fix needed:**
- Add logging to show `author` object structure
- Add fallback: `inReplyToUsername` if `author.username` missing
- Check for `author.id`, `author.userId`, or other variants

---

### 2. Engagement Metrics = NULL (Twitter/X data)

**Incoming fields available:**
- `likeCount` → should map to `likes`
- `retweetCount` → should map to `retweets`  
- `replyCount` → should map to `comments`
- `viewCount` → should map to `direct_reach` ✅ (this one works)

**Current mapping logic:**
- Maps `likeCount` → `likes` (if `likes` not already set)
- Maps `retweetCount` → `retweets` (if `retweets` not already set)
- Maps `replyCount` → `comments` (if `comments` not already set)

**Gap:**
- Mapping happens BEFORE checking if value is 0/None
- If incoming value is `0`, it might be treated as falsy and skipped
- Need to check: are values `0` or `None` in incoming data?

**Example from logs:**
```
Incoming: likeCount=?, retweetCount=?, replyCount=?
Stored: likes=None retweets=None comments=None (but views=11 works)
```

**Fix needed:**
- Ensure mapping handles `0` values (not just falsy check)
- Add logging to show raw engagement values before mapping

---

### 3. `user_avatar` = NULL

**Incoming fields available:**
- `author` (object) - may contain `profile_image_url` or similar

**Current mapping logic:**
- Checks: `author.profile_image_url`, `user.profile_image_url`, `ownerAvatar`

**Gap:**
- `author` object structure unknown
- May need to check `author.avatar`, `author.image`, etc.

---

## Platform-Specific Field Mapping

### Twitter/X
- ✅ `createdAt` → `date` (works)
- ✅ `viewCount` → `direct_reach` (works)
- ❌ `likeCount` → `likes` (NULL)
- ❌ `retweetCount` → `retweets` (NULL)
- ❌ `replyCount` → `comments` (NULL)
- ❌ `author.username` → `user_handle` (NULL)
- ✅ `author.name` → `user_name` (works)
- ✅ `place.full_name` → `user_location` (works)

### Instagram
- ✅ `timestamp` → `date` (works)
- ✅ `ownerFullName` → `user_name` (works)
- ❌ `ownerUsername` → `user_handle` (needs verification)
- ✅ `likesCount` → `likes` (should work)
- ✅ `commentsCount` → `comments` (should work)

### Facebook
- ✅ `timestamp` → `date` (works)
- ❌ Engagement metrics (needs verification)

---

## Next Steps to Fix

1. **Add debug logging for `author` object structure**
   - Log full `author` object for first record
   - Identify actual field names

2. **Fix engagement metrics mapping**
   - Handle `0` values explicitly
   - Log raw values before mapping

3. **Add more fallback fields**
   - `inReplyToUsername` → `user_handle` (Twitter)
   - Check `author.id`, `author.userId` variants

4. **Verify platform-specific mappings**
   - Test with actual Apify data samples
   - Document expected field names per actor

---

## Log Analysis Template

When analyzing gaps, check:

```
1. First item keys: [list of all incoming fields]
2. URL-related fields: {extracted URLs}
3. STORED in DB: {actual stored values}
```

**Compare:**
- Incoming field name → Expected DB field → Actual stored value
- If NULL, check: mapping logic, field name mismatch, value type issue

---

Last updated: 2026-01-07
Based on logs from: Run SsxhhATprv7nZnk3e (Twitter/X dataset)
