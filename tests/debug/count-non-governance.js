const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function countNonGovernance() {
  try {
    console.log('🔍 Counting records with ministry_hint = "non_governance"...\n');

    // Get total records
    const totalRecords = await prisma.sentimentData.count();
    console.log(`📊 Total records: ${totalRecords.toLocaleString()}\n`);

    // Count records with ministry_hint = 'non_governance'
    const nonGovernanceCount = await prisma.sentimentData.count({
      where: { 
        ministryHint: 'non_governance'
      }
    });

    console.log('='.repeat(80));
    console.log(`📋 Records with ministry_hint = 'non_governance': ${nonGovernanceCount.toLocaleString()}`);
    console.log(`📊 Percentage of total: ${((nonGovernanceCount / totalRecords) * 100).toFixed(2)}%`);
    console.log('='.repeat(80));

    // Also show breakdown of all ministry hints for context
    console.log('\n🏛️  MINISTRY HINT BREAKDOWN:\n');
    const ministryDistribution = await prisma.sentimentData.groupBy({
      by: ['ministryHint'],
      _count: {
        ministryHint: true
      },
      orderBy: {
        _count: {
          ministryHint: 'desc'
        }
      }
    });

    console.log(`${'Ministry Hint'.padEnd(40)} | ${'Count'.padStart(12)} | ${'Percentage'.padStart(10)}`);
    console.log('-'.repeat(75));

    ministryDistribution.forEach((item) => {
      const ministry = (item.ministryHint || 'NULL').padEnd(40);
      const count = item._count.ministryHint.toLocaleString().padStart(12);
      const percentage = ((item._count.ministryHint / totalRecords) * 100).toFixed(2).padStart(10);
      console.log(`${ministry} | ${count} | ${percentage}%`);
    });

  } catch (error) {
    console.error('❌ Error counting non-governance records:', error);
  } finally {
    await prisma.$disconnect();
  }
}

countNonGovernance();



