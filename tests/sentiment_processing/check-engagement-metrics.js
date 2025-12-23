const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkEngagementMetrics() {
  try {
    console.log('🔍 Checking Engagement Metrics in Sentiment Table...\n');

    // First, get total count of records
    const totalRecords = await prisma.sentimentData.count();
    console.log(`📊 Total records in sentiment_data: ${totalRecords}\n`);

    // Find records with any engagement metrics
    const recordsWithEngagement = await prisma.sentimentData.findMany({
      where: {
        OR: [
          { likes: { not: null, gt: 0 } },
          { retweets: { not: null, gt: 0 } },
          { comments: { not: null, gt: 0 } }
        ]
      },
      select: {
        entryId: true,
        platform: true,
        likes: true,
        retweets: true,
        comments: true,
        cumulativeReach: true,
        directReach: true,
        publishedAt: true,
        createdAt: true,
        url: true,
        text: true,
        title: true,
        issueLabel: true,
        issueSlug: true,
        sentimentLabel: true,
        userLocation: true,
        userName: true,
        userHandle: true
      },
      orderBy: {
        createdAt: 'desc'
      }
    });

    console.log(`✅ Found ${recordsWithEngagement.length} records with engagement metrics\n`);

    // Count records by metric type
    const withLikes = recordsWithEngagement.filter(r => r.likes && r.likes > 0).length;
    const withRetweets = recordsWithEngagement.filter(r => r.retweets && r.retweets > 0).length;
    const withComments = recordsWithEngagement.filter(r => r.comments && r.comments > 0).length;
    const withReach = recordsWithEngagement.filter(r => r.cumulativeReach && r.cumulativeReach > 0).length;

    console.log('📈 Engagement Metrics Breakdown:');
    console.log(`  Records with likes: ${withLikes} (${((withLikes / recordsWithEngagement.length) * 100).toFixed(1)}%)`);
    console.log(`  Records with retweets: ${withRetweets} (${((withRetweets / recordsWithEngagement.length) * 100).toFixed(1)}%)`);
    console.log(`  Records with comments: ${withComments} (${((withComments / recordsWithEngagement.length) * 100).toFixed(1)}%)`);
    console.log(`  Records with cumulative reach: ${withReach} (${((withReach / recordsWithEngagement.length) * 100).toFixed(1)}%)\n`);

    // Group by platform
    const byPlatform = {};
    recordsWithEngagement.forEach(record => {
      const platform = (record.platform || 'unknown').toLowerCase();
      if (!byPlatform[platform]) {
        byPlatform[platform] = {
          count: 0,
          totalLikes: 0,
          totalRetweets: 0,
          totalComments: 0,
          totalReach: 0,
          records: []
        };
      }
      byPlatform[platform].count++;
      byPlatform[platform].totalLikes += record.likes || 0;
      byPlatform[platform].totalRetweets += record.retweets || 0;
      byPlatform[platform].totalComments += record.comments || 0;
      byPlatform[platform].totalReach += record.cumulativeReach || 0;
      byPlatform[platform].records.push(record);
    });

    console.log('📱 Breakdown by Platform:');
    Object.entries(byPlatform)
      .sort((a, b) => b[1].count - a[1].count)
      .forEach(([platform, data]) => {
        console.log(`\n  ${platform.toUpperCase()}:`);
        console.log(`    Records: ${data.count}`);
        console.log(`    Total Likes: ${data.totalLikes.toLocaleString()}`);
        console.log(`    Total Retweets: ${data.totalRetweets.toLocaleString()}`);
        console.log(`    Total Comments: ${data.totalComments.toLocaleString()}`);
        console.log(`    Total Reach: ${data.totalReach.toLocaleString()}`);
        console.log(`    Avg Likes: ${Math.round(data.totalLikes / data.count)}`);
        console.log(`    Avg Retweets: ${Math.round(data.totalRetweets / data.count)}`);
        console.log(`    Avg Comments: ${Math.round(data.totalComments / data.count)}`);
      });

    // Calculate statistics
    const likesValues = recordsWithEngagement.map(r => r.likes || 0).filter(v => v > 0);
    const retweetsValues = recordsWithEngagement.map(r => r.retweets || 0).filter(v => v > 0);
    const commentsValues = recordsWithEngagement.map(r => r.comments || 0).filter(v => v > 0);
    const reachValues = recordsWithEngagement.map(r => r.cumulativeReach || 0).filter(v => v > 0);

    console.log('\n📊 Engagement Statistics:');
    
    if (likesValues.length > 0) {
      likesValues.sort((a, b) => a - b);
      console.log(`\n  Likes:`);
      console.log(`    Min: ${likesValues[0]}`);
      console.log(`    Max: ${likesValues[likesValues.length - 1]}`);
      console.log(`    Median: ${likesValues[Math.floor(likesValues.length / 2)]}`);
      console.log(`    Average: ${Math.round(likesValues.reduce((a, b) => a + b, 0) / likesValues.length)}`);
    }

    if (retweetsValues.length > 0) {
      retweetsValues.sort((a, b) => a - b);
      console.log(`\n  Retweets:`);
      console.log(`    Min: ${retweetsValues[0]}`);
      console.log(`    Max: ${retweetsValues[retweetsValues.length - 1]}`);
      console.log(`    Median: ${retweetsValues[Math.floor(retweetsValues.length / 2)]}`);
      console.log(`    Average: ${Math.round(retweetsValues.reduce((a, b) => a + b, 0) / retweetsValues.length)}`);
    }

    if (commentsValues.length > 0) {
      commentsValues.sort((a, b) => a - b);
      console.log(`\n  Comments:`);
      console.log(`    Min: ${commentsValues[0]}`);
      console.log(`    Max: ${commentsValues[commentsValues.length - 1]}`);
      console.log(`    Median: ${commentsValues[Math.floor(commentsValues.length / 2)]}`);
      console.log(`    Average: ${Math.round(commentsValues.reduce((a, b) => a + b, 0) / commentsValues.length)}`);
    }

    if (reachValues.length > 0) {
      reachValues.sort((a, b) => a - b);
      console.log(`\n  Cumulative Reach:`);
      console.log(`    Min: ${reachValues[0]}`);
      console.log(`    Max: ${reachValues[reachValues.length - 1]}`);
      console.log(`    Median: ${reachValues[Math.floor(reachValues.length / 2)]}`);
      console.log(`    Average: ${Math.round(reachValues.reduce((a, b) => a + b, 0) / reachValues.length)}`);
    }

    // Show top 20 records by total engagement
    console.log('\n🏆 Top 20 Records by Total Engagement:');
    const sortedByEngagement = [...recordsWithEngagement].sort((a, b) => {
      const engagementA = (a.likes || 0) + (a.retweets || 0) + (a.comments || 0);
      const engagementB = (b.likes || 0) + (b.retweets || 0) + (b.comments || 0);
      return engagementB - engagementA;
    });

    sortedByEngagement.slice(0, 20).forEach((record, idx) => {
      const engagement = (record.likes || 0) + (record.retweets || 0) + (record.comments || 0);
      console.log(`\n  ${idx + 1}. Entry ID: ${record.entryId}`);
      console.log(`     Platform: ${record.platform || 'N/A'}`);
      console.log(`     Total Engagement: ${engagement.toLocaleString()} (Likes: ${(record.likes || 0).toLocaleString()}, RTs: ${(record.retweets || 0).toLocaleString()}, Comments: ${(record.comments || 0).toLocaleString()})`);
      if (record.cumulativeReach) {
        console.log(`     Reach: ${record.cumulativeReach.toLocaleString()}`);
      }
      console.log(`     Issue: ${record.issueLabel || record.issueSlug || 'N/A'}`);
      console.log(`     Sentiment: ${record.sentimentLabel || 'N/A'}`);
      console.log(`     User: ${record.userName || record.userHandle || 'N/A'}`);
      console.log(`     Location: ${record.userLocation || 'N/A'}`);
      console.log(`     Date: ${record.publishedAt ? new Date(record.publishedAt).toISOString().split('T')[0] : record.createdAt ? new Date(record.createdAt).toISOString().split('T')[0] : 'N/A'}`);
      if (record.url) {
        console.log(`     URL: ${record.url}`);
      }
      if (record.text) {
        const textPreview = record.text.substring(0, 100);
        console.log(`     Text: ${textPreview}${record.text.length > 100 ? '...' : ''}`);
      }
    });

    // Check date range
    const dates = recordsWithEngagement
      .map(r => r.publishedAt || r.createdAt)
      .filter(d => d)
      .map(d => new Date(d));
    
    if (dates.length > 0) {
      dates.sort((a, b) => a - b);
      console.log('\n📅 Date Range:');
      console.log(`  Earliest: ${dates[0].toISOString().split('T')[0]}`);
      console.log(`  Latest: ${dates[dates.length - 1].toISOString().split('T')[0]}`);
    }

    console.log('\n✅ Analysis complete!');

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkEngagementMetrics();



