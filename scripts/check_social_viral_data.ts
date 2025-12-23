/**
 * Script to analyze social viral data in the database
 * Run with: npx tsx scripts/check_social_viral_data.ts
 */

import { prisma } from '../lib/db/prisma'

async function analyzeSocialViralData() {
  try {
    console.log('🔍 Analyzing Social Viral Data in Database...\n')

    // Get sample of negative sentiment posts from social platforms
    const socialPlatforms = ['x', 'twitter', 'facebook', 'instagram', 'tiktok', 'linkedin', 'reddit']
    
    const samplePosts = await prisma.sentimentData.findMany({
      where: {
        sentimentLabel: { in: ['negative', 'Negative'] },
        sentimentScore: { lt: -0.7 },
        platform: { in: socialPlatforms }
      },
      take: 100,
      orderBy: {
        createdAt: 'desc'
      },
      select: {
        entryId: true,
        platform: true,
        sentimentScore: true,
        likes: true,
        retweets: true,
        comments: true,
        cumulativeReach: true,
        directReach: true,
        issueLabel: true,
        issueSlug: true,
        createdAt: true,
        userLocation: true
      }
    })

    console.log(`📊 Found ${samplePosts.length} negative sentiment posts from social platforms\n`)

    // Group by platform
    const byPlatform = new Map<string, typeof samplePosts>()
    samplePosts.forEach(post => {
      const platform = (post.platform || 'unknown').toLowerCase()
      if (!byPlatform.has(platform)) {
        byPlatform.set(platform, [])
      }
      byPlatform.get(platform)!.push(post)
    })

    console.log('📱 Distribution by Platform:')
    byPlatform.forEach((posts, platform) => {
      console.log(`  ${platform}: ${posts.length} posts`)
    })
    console.log()

    // Analyze engagement metrics
    console.log('📈 Engagement Statistics:')
    
    const engagementStats = {
      likes: { min: Infinity, max: 0, avg: 0, hasValue: 0 },
      retweets: { min: Infinity, max: 0, avg: 0, hasValue: 0 },
      comments: { min: Infinity, max: 0, avg: 0, hasValue: 0 },
      cumulativeReach: { min: Infinity, max: 0, avg: 0, hasValue: 0 },
      directReach: { min: Infinity, max: 0, avg: 0, hasValue: 0 }
    }

    samplePosts.forEach(post => {
      // Likes
      if (post.likes !== null && post.likes !== undefined) {
        engagementStats.likes.min = Math.min(engagementStats.likes.min, post.likes)
        engagementStats.likes.max = Math.max(engagementStats.likes.max, post.likes)
        engagementStats.likes.avg += post.likes
        engagementStats.likes.hasValue++
      }

      // Retweets
      if (post.retweets !== null && post.retweets !== undefined) {
        engagementStats.retweets.min = Math.min(engagementStats.retweets.min, post.retweets)
        engagementStats.retweets.max = Math.max(engagementStats.retweets.max, post.retweets)
        engagementStats.retweets.avg += post.retweets
        engagementStats.retweets.hasValue++
      }

      // Comments
      if (post.comments !== null && post.comments !== undefined) {
        engagementStats.comments.min = Math.min(engagementStats.comments.min, post.comments)
        engagementStats.comments.max = Math.max(engagementStats.comments.max, post.comments)
        engagementStats.comments.avg += post.comments
        engagementStats.comments.hasValue++
      }

      // Cumulative Reach
      if (post.cumulativeReach !== null && post.cumulativeReach !== undefined) {
        engagementStats.cumulativeReach.min = Math.min(engagementStats.cumulativeReach.min, post.cumulativeReach)
        engagementStats.cumulativeReach.max = Math.max(engagementStats.cumulativeReach.max, post.cumulativeReach)
        engagementStats.cumulativeReach.avg += post.cumulativeReach
        engagementStats.cumulativeReach.hasValue++
      }

      // Direct Reach
      if (post.directReach !== null && post.directReach !== undefined) {
        engagementStats.directReach.min = Math.min(engagementStats.directReach.min, post.directReach)
        engagementStats.directReach.max = Math.max(engagementStats.directReach.max, post.directReach)
        engagementStats.directReach.avg += post.directReach
        engagementStats.directReach.hasValue++
      }
    })

    Object.entries(engagementStats).forEach(([metric, stats]) => {
      if (stats.hasValue > 0) {
        stats.avg = Math.round(stats.avg / stats.hasValue)
        console.log(`  ${metric}:`)
        console.log(`    Min: ${stats.min === Infinity ? 'N/A' : stats.min}`)
        console.log(`    Max: ${stats.max === 0 ? 'N/A' : stats.max}`)
        console.log(`    Avg: ${stats.avg}`)
        console.log(`    Posts with value: ${stats.hasValue}/${samplePosts.length}`)
      } else {
        console.log(`  ${metric}: No data available`)
      }
    })
    console.log()

    // Show sample entries
    console.log('📋 Sample Entries (Top 10 by engagement):')
    const sortedByEngagement = [...samplePosts].sort((a, b) => {
      const engagementA = (a.likes || 0) + (a.retweets || 0) + (a.comments || 0)
      const engagementB = (b.likes || 0) + (b.retweets || 0) + (b.comments || 0)
      return engagementB - engagementA
    })

    sortedByEngagement.slice(0, 10).forEach((post, idx) => {
      const engagement = (post.likes || 0) + (post.retweets || 0) + (post.comments || 0)
      console.log(`\n  ${idx + 1}. Entry ID: ${post.entryId}`)
      console.log(`     Platform: ${post.platform || 'N/A'}`)
      console.log(`     Sentiment Score: ${post.sentimentScore?.toFixed(3) || 'N/A'}`)
      console.log(`     Engagement: ${engagement} (Likes: ${post.likes || 0}, RTs: ${post.retweets || 0}, Comments: ${post.comments || 0})`)
      console.log(`     Reach: Cumulative=${post.cumulativeReach || 0}, Direct=${post.directReach || 0}`)
      console.log(`     Issue: ${post.issueLabel || post.issueSlug || 'N/A'}`)
      console.log(`     Location: ${post.userLocation || 'N/A'}`)
      console.log(`     Date: ${post.createdAt?.toISOString().split('T')[0] || 'N/A'}`)
    })

    // Check platform value variations
    console.log('\n🔤 Platform Value Variations:')
    const platformVariations = new Set<string>()
    samplePosts.forEach(post => {
      if (post.platform) {
        platformVariations.add(post.platform.toLowerCase())
      }
    })
    console.log(`  Found platform values: ${Array.from(platformVariations).join(', ')}`)

    // Check what would qualify as "social_viral" with current thresholds
    console.log('\n🎯 Current Social Viral Thresholds:')
    console.log('  Engagement > 50 OR Reach > 5000')
    
    const viralCount = samplePosts.filter(post => {
      const engagement = (post.likes || 0) + (post.retweets || 0) + (post.comments || 0)
      return engagement > 50 || (post.cumulativeReach || 0) > 5000
    }).length

    console.log(`  Posts that would qualify: ${viralCount}/${samplePosts.length} (${Math.round(viralCount/samplePosts.length*100)}%)`)

    // Suggest thresholds based on data
    const engagementValues = samplePosts
      .map(p => (p.likes || 0) + (p.retweets || 0) + (p.comments || 0))
      .filter(v => v > 0)
      .sort((a, b) => b - a)
    
    if (engagementValues.length > 0) {
      const p50 = engagementValues[Math.floor(engagementValues.length * 0.5)]
      const p75 = engagementValues[Math.floor(engagementValues.length * 0.25)]
      const p90 = engagementValues[Math.floor(engagementValues.length * 0.1)]
      
      console.log('\n💡 Suggested Thresholds (based on percentiles):')
      console.log(`  50th percentile: ${p50} (median)`)
      console.log(`  75th percentile: ${p75} (top 25%)`)
      console.log(`  90th percentile: ${p90} (top 10%)`)
    }

    await prisma.$disconnect()
    console.log('\n✅ Analysis complete!')
  } catch (error) {
    console.error('❌ Error analyzing data:', error)
    await prisma.$disconnect()
    process.exit(1)
  }
}

analyzeSocialViralData()













