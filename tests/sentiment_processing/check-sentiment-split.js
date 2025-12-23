const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkSentimentSplit() {
  try {
    console.log('🔍 Checking sentiment split in database...\n');

    // Get current date
    const now = new Date();
    
    // Test different time ranges
    const timeRanges = {
      week: 7,
      month: 30,
      year: 365
    };

    // Test with and without ministry filter
    const ministries = [null, 'health', 'education', 'transport']; // null means all ministries

    for (const [rangeName, days] of Object.entries(timeRanges)) {
      console.log(`\n${'='.repeat(80)}`);
      console.log(`📅 TIME RANGE: ${rangeName.toUpperCase()} (Last ${days} days)`);
      console.log('='.repeat(80));

      const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

      // Check overall sentiment (no ministry filter)
      console.log(`\n📊 OVERALL SENTIMENT (All Ministries):`);
      await checkSentimentForFilter({ startDate, ministry: null });

      // Check for specific ministries
      for (const ministry of ministries.filter(m => m !== null)) {
        console.log(`\n📊 MINISTRY FILTER: ${ministry.toUpperCase()}`);
        await checkSentimentForFilter({ startDate, ministry });
      }
    }

    // Check unique sentiment labels in database
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔍 UNIQUE SENTIMENT LABELS IN DATABASE:');
    console.log('='.repeat(80));
    const uniqueLabels = await prisma.sentimentData.groupBy({
      by: ['sentimentLabel'],
      _count: true,
      orderBy: {
        _count: {
          sentimentLabel: 'desc'
        }
      }
    });

    console.log('\nSentiment Label Distribution:');
    uniqueLabels.forEach(item => {
      console.log(`  "${item.sentimentLabel || 'NULL'}" : ${item._count} records`);
    });

    // Check ministry hints
    console.log(`\n${'='.repeat(80)}`);
    console.log('🏛️  UNIQUE MINISTRY HINTS IN DATABASE:');
    console.log('='.repeat(80));
    const uniqueMinistries = await prisma.sentimentData.groupBy({
      by: ['ministryHint'],
      _count: true,
      where: {
        ministryHint: { not: null }
      },
      orderBy: {
        _count: {
          ministryHint: 'desc'
        }
      },
      take: 20
    });

    console.log('\nMinistry Hint Distribution:');
    uniqueMinistries.forEach(item => {
      console.log(`  "${item.ministryHint}" : ${item._count} records`);
    });

    // Check date range of data
    console.log(`\n${'='.repeat(80)}`);
    console.log('📅 DATE RANGE OF DATA:');
    console.log('='.repeat(80));
    const dateRange = await prisma.sentimentData.aggregate({
      _min: { createdAt: true },
      _max: { createdAt: true },
      _count: true
    });

    console.log(`\nTotal Records: ${dateRange._count}`);
    console.log(`Earliest Record: ${dateRange._min.createdAt || 'N/A'}`);
    console.log(`Latest Record: ${dateRange._max.createdAt || 'N/A'}`);

  } catch (error) {
    console.error('❌ Error checking sentiment split:', error);
  } finally {
    await prisma.$disconnect();
  }
}

async function checkSentimentForFilter({ startDate, ministry }) {
  try {
    // Build where clause (same as dashboard)
    const whereClause = {
      createdAt: {
        gte: startDate
      }
    };

    if (ministry) {
      whereClause.ministryHint = ministry;
    }

    // Get sentiment distribution (same query as dashboard)
    const sentimentDistribution = await prisma.sentimentData.groupBy({
      by: ['sentimentLabel'],
      where: whereClause,
      _count: true
    });

    // Calculate sentiment counts (same normalization as dashboard)
    const sentimentCounts = sentimentDistribution.reduce((acc, item) => {
      const label = (item.sentimentLabel && item.sentimentLabel.toLowerCase()) || 'neutral';
      const normalizedLabel = label === 'positive' ? 'positive' : 
                             label === 'negative' ? 'negative' : 'neutral';
      acc[normalizedLabel] = (acc[normalizedLabel] || 0) + item._count;
      return acc;
    }, {});

    const total = Object.values(sentimentCounts).reduce((sum, count) => sum + count, 0);

    // Display results
    console.log(`\nFilter: ${ministry ? `ministryHint = '${ministry}'` : 'All ministries'}`);
    console.log(`Date Range: ${startDate.toISOString().split('T')[0]} to ${new Date().toISOString().split('T')[0]}`);
    console.log(`\nRaw Sentiment Labels:`);
    sentimentDistribution.forEach(item => {
      const percentage = total > 0 ? ((item._count / total) * 100).toFixed(2) : '0.00';
      console.log(`  "${item.sentimentLabel || 'NULL'}" : ${item._count} (${percentage}%)`);
    });

    console.log(`\nNormalized Sentiment Split:`);
    console.log(`  Positive: ${sentimentCounts.positive || 0} (${total > 0 ? ((sentimentCounts.positive || 0) / total * 100).toFixed(2) : '0.00'}%)`);
    console.log(`  Negative: ${sentimentCounts.negative || 0} (${total > 0 ? ((sentimentCounts.negative || 0) / total * 100).toFixed(2) : '0.00'}%)`);
    console.log(`  Neutral:  ${sentimentCounts.neutral || 0} (${total > 0 ? ((sentimentCounts.neutral || 0) / total * 100).toFixed(2) : '0.00'}%)`);
    console.log(`  Total:    ${total} records`);

    // Calculate sentiment score (same as dashboard)
    const sentimentScore = total > 0 ? 
      ((sentimentCounts.positive || 0) - (sentimentCounts.negative || 0)) / total * 100 : 0;
    console.log(`  Sentiment Score: ${sentimentScore.toFixed(2)}`);

  } catch (error) {
    console.error(`Error checking filter:`, error);
  }
}

// Run the check
checkSentimentSplit()
  .then(() => {
    console.log('\n✅ Sentiment split check completed!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });

