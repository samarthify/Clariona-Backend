const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkMinistryData() {
  try {
    console.log('🔍 Checking ministry data in database...\n');

    // Get total records
    const totalRecords = await prisma.sentimentData.count();
    console.log(`📊 Total records: ${totalRecords.toLocaleString()}\n`);

    // Get records with ministryHint
    const withMinistryHint = await prisma.sentimentData.count({
      where: { ministryHint: { not: null } }
    });
    console.log(`📋 Records with ministryHint: ${withMinistryHint.toLocaleString()} (${((withMinistryHint / totalRecords) * 100).toFixed(2)}%)\n`);

    // Get unique ministryHint values and their counts
    console.log('🏛️  MINISTRY DISTRIBUTION:\n');
    const ministryDistribution = await prisma.sentimentData.groupBy({
      by: ['ministryHint'],
      where: {
        ministryHint: { not: null }
      },
      _count: {
        ministryHint: true
      },
      orderBy: {
        _count: {
          ministryHint: 'desc'
        }
      }
    });

    console.log(`${'Rank'.padStart(4)} | ${'Ministry Hint'.padEnd(40)} | ${'Count'.padStart(12)} | ${'Percentage'.padStart(10)}`);
    console.log('-'.repeat(75));

    ministryDistribution.forEach((item, index) => {
      const ministry = (item.ministryHint || 'NULL').padEnd(40);
      const count = item._count.ministryHint.toLocaleString().padStart(12);
      const percentage = ((item._count.ministryHint / withMinistryHint) * 100).toFixed(2).padStart(10);
      console.log(`${(index + 1).toString().padStart(4)} | ${ministry} | ${count} | ${percentage}%`);
    });

    // Check for records with NULL ministryHint
    const nullMinistryHint = await prisma.sentimentData.count({
      where: { ministryHint: null }
    });
    console.log(`\n⚠️  Records with NULL ministryHint: ${nullMinistryHint.toLocaleString()} (${((nullMinistryHint / totalRecords) * 100).toFixed(2)}%)\n`);

    // Check for old frontend values (if any still exist)
    console.log('🔍 Checking for old frontend ministry values...\n');
    const oldValues = ['health', 'defense', 'agriculture', 'transport', 'energy', 'communication', 'youth-sports'];
    const oldValueCounts = {};

    for (const oldValue of oldValues) {
      const count = await prisma.sentimentData.count({
        where: { ministryHint: oldValue }
      });
      if (count > 0) {
        oldValueCounts[oldValue] = count;
      }
    }

    if (Object.keys(oldValueCounts).length > 0) {
      console.log('⚠️  Found old frontend values in database:');
      Object.entries(oldValueCounts).forEach(([value, count]) => {
        console.log(`   - "${value}": ${count.toLocaleString()} records`);
      });
      console.log('\n💡 These need to be migrated to backend values!\n');
    } else {
      console.log('✅ No old frontend values found in database.\n');
    }

    // Sample records for each ministry
    console.log('📝 Sample records for each ministry:\n');
    for (const ministry of ministryDistribution.slice(0, 10)) {
      const sample = await prisma.sentimentData.findFirst({
        where: { ministryHint: ministry.ministryHint },
        select: {
          entryId: true,
          ministryHint: true,
          issueSlug: true,
          issueLabel: true,
          sentimentLabel: true,
          createdAt: true,
          query: true,
          text: true
        }
      });

      if (sample) {
        console.log(`Ministry: ${ministry.ministryHint}`);
        console.log(`  Issue: ${sample.issueLabel || sample.issueSlug || 'N/A'}`);
        console.log(`  Sentiment: ${sample.sentimentLabel || 'N/A'}`);
        const textPreview = (sample.text || sample.query || '').substring(0, 100);
        if (textPreview) {
          console.log(`  Text preview: ${textPreview}...`);
        }
        console.log(`  Created: ${sample.createdAt}`);
        console.log('');
      }
    }

  } catch (error) {
    console.error('❌ Error checking ministry data:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkMinistryData();






