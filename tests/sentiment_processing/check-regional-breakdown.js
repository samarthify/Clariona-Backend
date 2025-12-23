const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkRegionalBreakdown() {
  try {
    console.log('🌍 Checking Regional Breakdown in database...\n');

    // Get current date
    const now = new Date();
    
    // Test different time ranges (same as dashboard)
    const timeRanges = {
      week: 7,
      month: 30,
      year: 365
    };

    // Test with and without ministry filter
    const ministries = [null, 'health', 'education', 'transport'];

    for (const [rangeName, days] of Object.entries(timeRanges)) {
      console.log(`\n${'='.repeat(80)}`);
      console.log(`📅 TIME RANGE: ${rangeName.toUpperCase()} (Last ${days} days)`);
      console.log('='.repeat(80));

      const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

      // Check overall regional breakdown (no ministry filter)
      console.log(`\n🌍 OVERALL REGIONAL BREAKDOWN (All Ministries):`);
      await checkRegionalForFilter({ startDate, ministry: null, rangeName });

      // Check for specific ministries
      for (const ministry of ministries.filter(m => m !== null)) {
        console.log(`\n🏛️  MINISTRY FILTER: ${ministry.toUpperCase()}`);
        await checkRegionalForFilter({ startDate, ministry, rangeName });
      }
    }

    // Check unique locations in database
    console.log(`\n${'='.repeat(80)}`);
    console.log('📍 UNIQUE USER LOCATIONS IN DATABASE:');
    console.log('='.repeat(80));
    const uniqueLocations = await prisma.sentimentData.groupBy({
      by: ['userLocation'],
      _count: true,
      where: {
        userLocation: { not: null }
      },
      orderBy: {
        _count: {
          userLocation: 'desc'
        }
      },
      take: 50
    });

    console.log('\nTop 50 Locations by Record Count:');
    uniqueLocations.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. "${item.userLocation || 'NULL'}" : ${item._count} records`);
    });

    // Check NULL location count
    const nullLocationCount = await prisma.sentimentData.count({
      where: {
        userLocation: null
      }
    });

    const totalRecords = await prisma.sentimentData.count();
    const withLocation = totalRecords - nullLocationCount;

    console.log(`\n📍 Location Data Coverage:`);
    console.log(`  Total Records: ${totalRecords}`);
    console.log(`  Records with Location: ${withLocation} (${((withLocation / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`  Records without Location: ${nullLocationCount} (${((nullLocationCount / totalRecords) * 100).toFixed(2)}%)`);

    // Check location distribution by sentiment
    console.log(`\n${'='.repeat(80)}`);
    console.log('📊 LOCATION DISTRIBUTION BY SENTIMENT:');
    console.log('='.repeat(80));
    
    const locationBySentiment = await prisma.sentimentData.groupBy({
      by: ['userLocation', 'sentimentLabel'],
      _count: true,
      where: {
        userLocation: { not: null }
      },
      orderBy: {
        _count: {
          userLocation: 'desc'
        }
      },
      take: 30
    });

    console.log('\nTop 30 Location-Sentiment Combinations:');
    locationBySentiment.forEach((item, index) => {
      const percentage = ((item._count / withLocation) * 100).toFixed(2);
      console.log(`  ${(index + 1).toString().padStart(2)}. ${item.userLocation} | ${item.sentimentLabel || 'NULL'} : ${item._count} (${percentage}%)`);
    });

  } catch (error) {
    console.error('❌ Error checking regional breakdown:', error);
  } finally {
    await prisma.$disconnect();
  }
}

async function checkRegionalForFilter({ startDate, ministry, rangeName }) {
  try {
    // Build where clause (same as dashboard)
    const whereClause = {
      createdAt: {
        gte: startDate
      },
      userLocation: {
        not: null  // Only records with location
      }
    };

    if (ministry) {
      whereClause.ministryHint = ministry;
    }

    // Get regional sentiment data (same query as dashboard)
    const locationSentimentData = await prisma.sentimentData.groupBy({
      by: ['userLocation', 'sentimentLabel'],
      where: whereClause,
      _count: true,
      _avg: {
        sentimentScore: true
      }
    });

    // Process in memory (same logic as dashboard)
    const locationMap = {};

    locationSentimentData.forEach(item => {
      const location = item.userLocation || 'Unknown';
      if (!locationMap[location]) {
        locationMap[location] = {
          positive: 0,
          negative: 0,
          neutral: 0,
          total: 0,
          avgScore: 0,
          scoreCount: 0
        };
      }

      // Normalize sentiment label (same as dashboard)
      const sentiment = (item.sentimentLabel && item.sentimentLabel.toLowerCase()) || 'neutral';
      const normalizedSentiment = sentiment === 'positive' ? 'positive' :
                                  sentiment === 'negative' ? 'negative' : 'neutral';

      locationMap[location][normalizedSentiment] += item._count;
      locationMap[location].total += item._count;

      // Track average sentiment score
      if (item._avg && item._avg.sentimentScore) {
        locationMap[location].avgScore += item._avg.sentimentScore * item._count;
        locationMap[location].scoreCount += item._count;
      }
    });

    // Convert to array and sort (same as dashboard)
    const regionalSentiment = Object.entries(locationMap)
      .map(([state, counts]) => ({
        state,
        sentimentScore: counts.scoreCount > 0
          ? Math.round((counts.avgScore / counts.scoreCount) * 100)
          : 0,
        positive: counts.positive,
        negative: counts.negative,
        neutral: counts.neutral,
        totalMentions: counts.total
      }))
      .sort((a, b) => b.totalMentions - a.totalMentions);

    // Display results
    console.log(`\nFilter: ${ministry ? `ministryHint = '${ministry}'` : 'All ministries'}`);
    console.log(`Date Range: ${startDate.toISOString().split('T')[0]} to ${new Date().toISOString().split('T')[0]}`);
    console.log(`Only records with userLocation (not null)`);
    
    const totalMentions = regionalSentiment.reduce((sum, r) => sum + r.totalMentions, 0);
    console.log(`\nTotal Regional Records: ${totalMentions}`);
    console.log(`Unique Locations: ${regionalSentiment.length}`);

    if (regionalSentiment.length === 0) {
      console.log('  ⚠️  No regional data found for this filter');
      return;
    }

    // Show top 20 regions
    console.log(`\nTop 20 Regions by Total Mentions:`);
    console.log(`${'Rank'.padStart(4)} | ${'Location'.padEnd(30)} | ${'Total'.padStart(8)} | ${'Pos'.padStart(6)} | ${'Neg'.padStart(6)} | ${'Neu'.padStart(6)} | ${'Score'.padStart(6)}`);
    console.log('-'.repeat(90));
    
    regionalSentiment.slice(0, 20).forEach((region, index) => {
      const rank = (index + 1).toString().padStart(4);
      const location = (region.state || 'Unknown').substring(0, 30).padEnd(30);
      const total = region.totalMentions.toString().padStart(8);
      const pos = region.positive.toString().padStart(6);
      const neg = region.negative.toString().padStart(6);
      const neu = region.neutral.toString().padStart(6);
      const score = region.sentimentScore.toString().padStart(6);
      console.log(`${rank} | ${location} | ${total} | ${pos} | ${neg} | ${neu} | ${score}`);
    });

    // Summary statistics
    const totalPositive = regionalSentiment.reduce((sum, r) => sum + r.positive, 0);
    const totalNegative = regionalSentiment.reduce((sum, r) => sum + r.negative, 0);
    const totalNeutral = regionalSentiment.reduce((sum, r) => sum + r.neutral, 0);

    console.log(`\n📊 Summary Statistics:`);
    console.log(`  Total Positive: ${totalPositive} (${totalMentions > 0 ? ((totalPositive / totalMentions) * 100).toFixed(2) : '0.00'}%)`);
    console.log(`  Total Negative: ${totalNegative} (${totalMentions > 0 ? ((totalNegative / totalMentions) * 100).toFixed(2) : '0.00'}%)`);
    console.log(`  Total Neutral:  ${totalNeutral} (${totalMentions > 0 ? ((totalNeutral / totalMentions) * 100).toFixed(2) : '0.00'}%)`);
    
    // Average sentiment score across all regions
    const avgSentimentScore = regionalSentiment.length > 0
      ? Math.round(regionalSentiment.reduce((sum, r) => sum + r.sentimentScore, 0) / regionalSentiment.length)
      : 0;
    console.log(`  Average Regional Sentiment Score: ${avgSentimentScore}`);

    // Regions with highest positive sentiment
    const topPositive = [...regionalSentiment]
      .sort((a, b) => {
        const aRatio = a.totalMentions > 0 ? a.positive / a.totalMentions : 0;
        const bRatio = b.totalMentions > 0 ? b.positive / b.totalMentions : 0;
        return bRatio - aRatio;
      })
      .slice(0, 5);

    console.log(`\n👍 Top 5 Regions by Positive Sentiment Ratio:`);
    topPositive.forEach((region, index) => {
      const ratio = region.totalMentions > 0 ? ((region.positive / region.totalMentions) * 100).toFixed(2) : '0.00';
      console.log(`  ${index + 1}. ${region.state}: ${ratio}% positive (${region.positive}/${region.totalMentions})`);
    });

    // Regions with highest negative sentiment
    const topNegative = [...regionalSentiment]
      .sort((a, b) => {
        const aRatio = a.totalMentions > 0 ? a.negative / a.totalMentions : 0;
        const bRatio = b.totalMentions > 0 ? b.negative / b.totalMentions : 0;
        return bRatio - aRatio;
      })
      .slice(0, 5);

    console.log(`\n👎 Top 5 Regions by Negative Sentiment Ratio:`);
    topNegative.forEach((region, index) => {
      const ratio = region.totalMentions > 0 ? ((region.negative / region.totalMentions) * 100).toFixed(2) : '0.00';
      console.log(`  ${index + 1}. ${region.state}: ${ratio}% negative (${region.negative}/${region.totalMentions})`);
    });

  } catch (error) {
    console.error(`Error checking regional filter:`, error);
  }
}

// Run the check
checkRegionalBreakdown()
  .then(() => {
    console.log('\n✅ Regional breakdown check completed!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });











