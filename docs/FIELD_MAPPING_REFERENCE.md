# Field Mapping Reference

This document shows which fields are available from each data source (Apify actors) and where they are stored in the database.

**Last Updated**: 2026-01-07  
**Status**: All major gaps fixed ✅

---

## Database Schema (SentimentData Table)

The following fields are available in the `sentiment_data` table:

### Core Content Fields
- `url` - Unique identifier (required for upsert)
- `text` - Main content text
- `title` - Post/article title
- `description` - Post description
- `content` - Full content body
- `date` - Publication date (primary date field)
- `published_at` - Alternative publication timestamp
- `published_date` - Publication date (alternative)

### Platform & Source Fields
- `platform` - Platform name (twitter, instagram, facebook, tiktok)
- `source` - Data source identifier
- `source_url` - Source URL
- `language` - Content language
- `query` - Search query used

### User Information Fields
- `user_name` - Display name of the user/page
- `user_handle` - Username/handle (@username)
- `user_avatar` - Profile picture URL
- `user_location` - User's location

### Engagement Metrics Fields
- `likes` - Number of likes/favorites/reactions
- `retweets` - Number of retweets/shares/reshares
- `comments` - Number of comments/replies
- `direct_reach` - Views/impressions
- `cumulative_reach` - Total reach (if available)
- `domain_reach` - Domain-level reach (if available)

### Analysis Fields (Populated by processing pipeline)
- `sentiment_label` - Sentiment classification
- `sentiment_score` - Sentiment score
- `emotion_label` - Emotion classification
- `location_label` - Location classification
- `issue_label` - Issue classification
- `processing_status` - Processing status

---

## Platform-Specific Field Mappings

### Twitter/X

**Apify Actor**: `CJdippxWmn9uRfooo` (Twitter/X Scraper)

#### Available Source Fields

| Source Field | Type | Database Field | Status | Notes |
|-------------|------|----------------|--------|-------|
| `url` | string | `url` | ✅ Working | **Primary URL** (checked first) |
| `twitterUrl` | string | `url` | ✅ Working | **Fallback URL** (alternative format) |
| `text` | string | `text` | ✅ Working | Tweet content |
| `createdAt` | datetime | `date` | ✅ Working | Primary date field |
| `createdAt` | datetime | `published_at` | ✅ Working | Alternative date field |
| `author.userName` | string | `user_handle` | ✅ **FIXED** | Username (camelCase) |
| `author.name` | string | `user_name` | ✅ Working | Display name |
| `author.profilePicture` | string | `user_avatar` | ✅ **FIXED** | Avatar URL (camelCase) |
| `author.id` | string | `user_handle` | ✅ Working | Fallback if userName missing |
| `place.full_name` | string | `user_location` | ✅ Working | Location |
| `likeCount` | integer | `likes` | ✅ **FIXED** | Handles 0 values |
| `retweetCount` | integer | `retweets` | ✅ **FIXED** | Handles 0 values |
| `replyCount` | integer | `comments` | ✅ **FIXED** | Handles 0 values |
| `viewCount` | integer | `direct_reach` | ✅ Working | Views |
| `quoteCount` | integer | `comments` | ✅ Working | Added to comments |
| `bookmarkCount` | integer | `likes` | ✅ Working | Added to likes |
| `inReplyToUsername` | string | `user_handle` | ✅ Working | Fallback for replies |
| `lang` | string | `language` | ✅ Working | Language code |

#### Author Object Structure
```
author: {
  userName: string,        // → user_handle ✅
  name: string,           // → user_name ✅
  profilePicture: string, // → user_avatar ✅
  id: string,            // → user_handle (fallback)
  location: string,      // → user_location (if place not available)
  ...
}
```

---

### Instagram

**Apify Actor**: `reGe1ST3OBgYZSsZJ` (Instagram Scraper)

#### Available Source Fields

| Source Field | Type | Database Field | Status | Notes |
|-------------|------|----------------|--------|-------|
| `url` | string | `url` | ✅ Working | **Primary URL** |
| `shortCode` | string | - | - | Used for **URL generation** if `url` missing |
| `caption` | string | `text` | ✅ Working | Post caption |
| `timestamp` | datetime | `date` | ✅ Working | Post timestamp |
| `ownerUsername` | string | `user_handle` | ✅ Working | Username |
| `ownerFullName` | string | `user_name` | ✅ Working | Display name |
| `ownerId` | string | - | - | Owner ID |
| `likesCount` | integer | `likes` | ✅ **FIXED** | Handles 0 values |
| `commentsCount` | integer | `comments` | ✅ **FIXED** | Handles 0 values |
| `displayUrl` | string | - | - | Media URL |
| `locationName` | string | `user_location` | ✅ Working | Location |
| `hashtags` | array | - | - | Hashtags (not stored) |
| `mentions` | array | - | - | Mentions (not stored) |

#### Notes
- Instagram posts with 0 likes/comments are now properly stored (not NULL)
- `ownerUsername` is the primary source for `user_handle`

---

### Facebook

**Apify Actor**: `l6CUZt8H0214D3I0N` (Facebook Scraper)

#### Available Source Fields

| Source Field | Type | Database Field | Status | Notes |
|-------------|------|----------------|--------|-------|
| `url` | string | `url` | ✅ Working | **Primary URL** |
| `post_id` | string | `post_id` | ✅ Working | Facebook post ID |
| `message` | string | `text` | ✅ Working | Post content |
| `message_rich` | string | `content` | ✅ Working | Rich text content |
| `timestamp` | datetime | `date` | ✅ Working | Post timestamp |
| `author.id` | string | `user_handle` | ✅ **FIXED** | Uses ID as handle (no username available) |
| `author.name` | string | `user_name` | ✅ Working | Page/Profile name |
| `author.profile_picture_url` | string | `user_avatar` | ✅ **FIXED** | Avatar URL (snake_case) |
| `author.url` | string | - | - | Profile URL |
| `reactions_count` | integer | `likes` | ✅ Working | Reactions count |
| `comments_count` | integer | `comments` | ✅ Working | Comments count |
| `reshare_count` | integer | `retweets` | ✅ Working | Share count |
| `external_url` | string | `source_url` | ✅ Working | External link if present |
| `image` | string | - | - | Image URL (not stored) |
| `video` | string | - | - | Video URL (not stored) |

#### Author Object Structure
```
author: {
  id: string,                    // → user_handle ✅ (no username field available)
  name: string,                 // → user_name ✅
  profile_picture_url: string,   // → user_avatar ✅
  url: string,                   // Profile URL
  ...
}
```

#### Notes
- Facebook author objects **do not have a username field**
- We use `author.id` as `user_handle` (e.g., `100064820345745`)
- This is expected behavior for Facebook pages/profiles

---

### TikTok

**Apify Actor**: `5K30i8aFccKNF5ICs` (TikTok Scraper)

#### Available Source Fields

| Source Field | Type | Database Field | Status | Notes |
|-------------|------|----------------|--------|-------|
| `id` | string | `original_id` | ✅ Working | Video ID (used for **URL generation**) |
| `title` | string | `title` | ✅ Working | Video title |
| `url` | string | `url` | ⚠️ **Often Missing** | Usually **generated** from `id` → `apify://tiktok/{id}` |
| `postPage` | string | - | - | May be used for URL generation if available |
| `uploadedAt` | datetime | `date` | ✅ Working | Upload timestamp |
| `uploadedAtFormatted` | string | - | - | Formatted date |
| `likes` | integer | `likes` | ✅ Working | Direct field (no Count suffix) |
| `comments` | integer | `comments` | ✅ Working | Direct field (no Count suffix) |
| `shares` | integer | `retweets` | ✅ Working | Direct field (no Count suffix) |
| `views` | integer | `direct_reach` | ✅ Working | Direct field (no Count suffix) |
| `bookmarks` | integer | - | - | Bookmarks (not mapped) |
| `hashtags` | array | - | - | Hashtags (not stored) |
| `channel` | object | - | - | Channel info (structure TBD) |
| `postPage` | string | - | - | Post page URL (may be used for URL generation) |

#### Notes
- TikTok uses **direct field names** (no `Count` suffix)
- Fields are checked in priority order: direct fields first, then platform-specific
- `channel` object structure needs further investigation for user fields
- URL may need to be constructed from `id` or `postPage` if missing

---

## URL Field Mapping

The `url` field is the **primary unique identifier** for database records (used for upsert operations).

### URL Mapping Priority Order

The system maps to `url` in the following priority order:

1. **Direct `url` field** (if already present in record)
2. **Fallback URL fields** (checked in order):
   - `link`
   - `postUrl`
   - `pageUrl`
   - `videoUrl`
   - `articleUrl`
   - `twitterUrl` (Twitter/X alternative format)
3. **Generated URLs** (if no URL field found):
   - **Instagram**: Constructed from `shortcode` → `https://instagram.com/p/{shortcode}`
   - **Generic**: Constructed from `postId` or `original_id` → `apify://{platform}/{post_id}`
   - **Last resort**: Hash-based URL from content + timestamp → `apify://generated/{hash}`

### Platform-Specific URL Fields

| Platform | Primary URL Field | Alternative URL Fields | Generated From |
|----------|------------------|------------------------|----------------|
| **Twitter/X** | `url` | `twitterUrl` | - |
| **Instagram** | `url` | - | `shortcode` → `https://instagram.com/p/{shortcode}` |
| **Facebook** | `url` | - | - |
| **TikTok** | ⚠️ Often missing | - | `id` → `apify://tiktok/{id}` |

**Note**: TikTok often doesn't provide a URL field, so URLs are generated from the video `id`.

---

## Field Mapping Priority Order

The ingestion system checks fields in priority order (highest to lowest):

### User Handle (`user_handle`)
1. `author.userName` (Twitter/X - camelCase)
2. `inReplyToUsername` (Twitter/X replies)
3. `ownerUsername` (Instagram)
4. `author.username` (Generic)
5. `author.screen_name` (Alternative)
6. `author.handle` (Alternative)
7. `user.username` (User object)
8. `author.id` (Facebook fallback)
9. `username` (Top-level fallback)

### User Avatar (`user_avatar`)
1. `author.profilePicture` (Twitter/X - camelCase)
2. `author.profile_picture_url` (Facebook - snake_case)
3. `author.profile_image_url` (Generic)
4. `author.profilePicUrl` (Alternative camelCase)
5. `author.avatar` (Alternative)
6. `user.profilePicture` (User object)
7. `profilePicUrl` (Top-level)
8. `ownerProfilePicUrl` (Instagram)

### Likes (`likes`)
1. `likes` (TikTok direct field)
2. `likeCount` (Twitter/X)
3. `likesCount` (Instagram)
4. `favoriteCount` (Twitter alternative)
5. `reactions_count` (Facebook)

### Retweets/Shares (`retweets`)
1. `shares` (TikTok direct field)
2. `retweetCount` (Twitter/X)
3. `reshareCount` (Generic)
4. `reshare_count` (Facebook)
5. `shareCount` (Generic)
6. `retweets` (Generic fallback)

### Comments (`comments`)
1. `comments` (TikTok direct field)
2. `replyCount` (Twitter/X)
3. `commentsCount` (Instagram)
4. `comments_count` (Facebook)
5. `commentCount` (Generic)

### Views/Reach (`direct_reach`)
1. `views` (TikTok direct field)
2. `viewCount` (Twitter/X)
3. `impressions` (Generic)
4. `direct_reach` (Generic fallback)

---

## Zero Value Handling

**Status**: ✅ **FIXED** (2026-01-07)

The system now correctly handles `0` values for engagement metrics:
- Previously: `likeCount: 0` → stored as `likes=None` ❌
- Now: `likeCount: 0` → stored as `likes=0` ✅

This is handled by the `_extract_engagement_value()` helper function which:
- Checks if field exists in record (not just truthiness)
- Distinguishes between `0` (valid value) and `None` (missing value)
- Uses `is None` checks instead of falsy checks

---

## Verification Status

| Platform | User Handle | User Avatar | Engagement Metrics | Date Fields | Status |
|----------|-------------|-------------|-------------------|-------------|--------|
| **Twitter/X** | ✅ Fixed | ✅ Fixed | ✅ Fixed | ✅ Working | Complete |
| **Instagram** | ✅ Working | ✅ Working | ✅ Fixed | ✅ Working | Complete |
| **Facebook** | ✅ Fixed* | ✅ Fixed | ✅ Working | ✅ Working | Complete |
| **TikTok** | ⚠️ TBD | ⚠️ TBD | ✅ Working | ✅ Working | Partial |

*Facebook uses `author.id` as `user_handle` (no username field available - expected behavior)

---

## Implementation Details

### Helper Function: `_extract_engagement_value()`

Located in: `src/services/data_ingestor.py`

```python
def _extract_engagement_value(self, record: Dict[str, Any], candidates: List[str]) -> Optional[int]:
    """
    Extract engagement value from multiple candidate fields, handling 0 values correctly.
    
    This function checks if a key exists in the record and if its value is not None.
    This allows 0 values to be properly extracted (since 0 is not None, but is falsy).
    """
    for candidate in candidates:
        if candidate in record:
            value = record[candidate]
            if value is not None:  # This handles 0 correctly (0 is not None)
                result = safe_int(value)
                if result is not None:
                    return result
    return None
```

### Mapping Logic Location

All field mappings are implemented in:
- **File**: `src/services/data_ingestor.py`
- **Method**: `normalize_record()`
- **Lines**: 
  - Engagement metrics: 168-227
  - User fields: 330-410

---

## Known Limitations

1. **Facebook `user_handle`**: Uses numeric ID instead of username (no username field in Facebook author object - this is expected)
2. **TikTok User Fields**: `channel` object structure needs further investigation
3. **TikTok URL**: May need URL construction if not provided in source data

---

## Future Enhancements

1. Extract TikTok user fields from `channel` object
2. Construct TikTok URLs from `id` or `postPage` if missing
3. Add support for additional platforms as needed
4. Document any new field mappings as they are discovered

---

## Related Documentation

- [Data Ingestion Coverage Gaps](./DATA_INGESTION_COVERAGE_GAPS.md) - Original gap analysis
- [Backend Architecture](./BACKEND_ARCHITECTURE.md) - System architecture
- [Database Config System Summary](./DATABASE_CONFIG_SYSTEM_SUMMARY.md) - Database configuration
