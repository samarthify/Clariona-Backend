/**
 * Clear regional sentiment cache
 * Run this if regional sentiment is showing stale data
 * 
 * Note: This requires the Next.js app to be running or Redis to be accessible
 */

async function clearCache() {
  try {
    // Import dynamically to handle ES modules
    const { redisClient } = await import('./lib/cache/redis.js');
    
    console.log('🧹 Clearing regional sentiment cache...\n');
    
    // Clear all regional sentiment cache keys
    const pattern = 'regional:sentiment:*';
    const deleted = await redisClient.invalidatePattern(pattern);
    
    console.log(`✅ Cleared ${deleted} cache entries matching pattern: ${pattern}\n`);
    console.log('✨ Cache cleared! Regional sentiment will be recalculated on next request.\n');
    
    await redisClient.disconnect();
  } catch (error) {
    console.error('❌ Error clearing cache:', error);
    console.log('\n💡 Alternative: Restart your Next.js server to clear in-memory cache\n');
  }
}

clearCache();






