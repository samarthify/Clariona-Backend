const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkQueryOnlyRecords() {
  try {
    console.log('🔍 Checking how records with query but no issueSlug are grouped...\n');

    // 1. Check how many records have query but no issueSlug
    const queryOnlyCount = await prisma.sentimentData.count({
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: null }
        ]
      }
    });

    console.log(`Total records with query but no issueSlug: ${queryOnlyCount.toLocaleString()}\n`);

    // 2. Check how they're grouped by the current query logic
    console.log('='.repeat(80));
    console.log('📊 GROUPING BY issueSlug, issueLabel, ministryHint (Current Logic)');
    console.log('='.repeat(80));
    
    const groupedByCurrentLogic = await prisma.sentimentData.groupBy({
      by: ['issueSlug', 'issueLabel', 'ministryHint'],
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: null }
        ]
      },
      _count: true,
      orderBy: { _count: { issueSlug: 'desc' } },
      take: 20
    });

    console.log(`\nNumber of groups created: ${groupedByCurrentLogic.length}`);
    console.log('\nTop 20 Groups (query-only records):');
    console.log(`${'Rank'.padStart(4)} | ${'issueSlug'.padEnd(20)} | ${'issueLabel'.padEnd(40)} | ${'ministryHint'.padEnd(20)} | ${'Count'.padStart(8)}`);
    console.log('-'.repeat(100));
    
    groupedByCurrentLogic.forEach((group, index) => {
      const rank = (index + 1).toString().padStart(4);
      const slug = (group.issueSlug || 'NULL').substring(0, 20).padEnd(20);
      const label = (group.issueLabel || 'NULL').substring(0, 40).padEnd(40);
      const ministry = (group.ministryHint || 'NULL').substring(0, 20).padEnd(20);
      const count = group._count.toString().padStart(8);
      console.log(`${rank} | ${slug} | ${label} | ${ministry} | ${count}`);
    });

    // 3. Check unique queries in query-only records
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔍 UNIQUE QUERIES IN QUERY-ONLY RECORDS');
    console.log('='.repeat(80));
    
    const uniqueQueries = await prisma.sentimentData.groupBy({
      by: ['query'],
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: null }
        ]
      },
      _count: true,
      orderBy: { _count: { query: 'desc' } },
      take: 20
    });

    console.log(`\nTotal unique queries: ${uniqueQueries.length}`);
    console.log('\nTop 20 Queries (query-only records):');
    uniqueQueries.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. "${item.query}" : ${item._count} records`);
    });

    // 4. Sample records to see actual data
    console.log(`\n${'='.repeat(80)}`);
    console.log('📋 SAMPLE RECORDS (query but no issueSlug)');
    console.log('='.repeat(80));
    
    const sampleRecords = await prisma.sentimentData.findMany({
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: null }
        ]
      },
      select: {
        entryId: true,
        query: true,
        issueSlug: true,
        issueLabel: true,
        ministryHint: true,
        sentimentLabel: true
      },
      take: 10
    });

    console.log('\nSample Records:');
    sampleRecords.forEach((record, index) => {
      console.log(`\n  ${index + 1}. Entry ID: ${record.entryId}`);
      console.log(`     Query: "${record.query}"`);
      console.log(`     issueSlug: ${record.issueSlug || 'NULL'}`);
      console.log(`     issueLabel: ${record.issueLabel || 'NULL'}`);
      console.log(`     ministryHint: ${record.ministryHint || 'NULL'}`);
      console.log(`     sentimentLabel: ${record.sentimentLabel || 'NULL'}`);
    });

    // 5. Check how the current query would group these
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔗 HOW CURRENT QUERY GROUPS THESE RECORDS');
    console.log('='.repeat(80));
    
    const now = new Date();
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    const currentQueryGroups = await prisma.sentimentData.groupBy({
      by: ['issueSlug', 'issueLabel', 'ministryHint'],
      where: {
        createdAt: { gte: thirtyDaysAgo },
        OR: [
          { issueSlug: { not: null } },
          { query: { not: null } }
        ]
      },
      _count: true,
      orderBy: { _count: { issueSlug: 'desc' } },
      take: 30
    });

    console.log(`\nTotal groups from current query (last 30 days): ${currentQueryGroups.length}`);
    console.log('\nGroups with NULL issueSlug (these are query-only records):');
    
    const nullSlugGroups = currentQueryGroups.filter(g => g.issueSlug === null);
    console.log(`\nNumber of NULL issueSlug groups: ${nullSlugGroups.length}`);
    
    nullSlugGroups.slice(0, 10).forEach((group, index) => {
      console.log(`\n  ${index + 1}. issueSlug: NULL`);
      console.log(`     issueLabel: ${group.issueLabel || 'NULL'}`);
      console.log(`     ministryHint: ${group.ministryHint || 'NULL'}`);
      console.log(`     Count: ${group._count}`);
    });

    // 6. Show the problem: multiple queries grouped together
    console.log(`\n${'='.repeat(80)}`);
    console.log('⚠️  THE PROBLEM: Multiple Queries Grouped Together');
    console.log('='.repeat(80));
    
    // Find a NULL issueSlug group and show what queries are in it
    if (nullSlugGroups.length > 0) {
      const exampleGroup = nullSlugGroups[0];
      console.log(`\nExample: Group with NULL issueSlug, ministryHint="${exampleGroup.ministryHint}"`);
      console.log(`This group contains ${exampleGroup._count} records.`);
      console.log(`\nSample queries in this group:`);
      
      const queriesInGroup = await prisma.sentimentData.findMany({
        where: {
          AND: [
            { issueSlug: null },
            { issueLabel: exampleGroup.issueLabel },
            { ministryHint: exampleGroup.ministryHint },
            { query: { not: null } }
          ]
        },
        select: { query: true },
        distinct: ['query'],
        take: 10
      });
      
      queriesInGroup.forEach((item, index) => {
        console.log(`  ${index + 1}. "${item.query}"`);
      });
    }

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkQueryOnlyRecords()
  .then(() => {
    console.log('\n✅ Analysis completed!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });











