const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function analyzeIssueData() {
  try {
    console.log('🔍 Analyzing Issue-Related Data in Database...\n');

    // 1. Overall Statistics
    console.log('='.repeat(80));
    console.log('📊 OVERALL STATISTICS');
    console.log('='.repeat(80));
    
    const totalRecords = await prisma.sentimentData.count();
    const withIssueSlug = await prisma.sentimentData.count({
      where: { issueSlug: { not: null } }
    });
    const withIssueLabel = await prisma.sentimentData.count({
      where: { issueLabel: { not: null } }
    });
    const withQuery = await prisma.sentimentData.count({
      where: { query: { not: null } }
    });
    const withIssueKeywords = await prisma.sentimentData.count({
      where: { issueKeywords: { not: null } }
    });
    const withIssueConfidence = await prisma.sentimentData.count({
      where: { issueConfidence: { not: null } }
    });
    const withMinistryHint = await prisma.sentimentData.count({
      where: { ministryHint: { not: null } }
    });

    console.log(`\nTotal Records: ${totalRecords.toLocaleString()}`);
    console.log(`Records with issueSlug: ${withIssueSlug.toLocaleString()} (${((withIssueSlug / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records with issueLabel: ${withIssueLabel.toLocaleString()} (${((withIssueLabel / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records with query: ${withQuery.toLocaleString()} (${((withQuery / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records with issueKeywords: ${withIssueKeywords.toLocaleString()} (${((withIssueKeywords / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records with issueConfidence: ${withIssueConfidence.toLocaleString()} (${((withIssueConfidence / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records with ministryHint: ${withMinistryHint.toLocaleString()} (${((withMinistryHint / totalRecords) * 100).toFixed(2)}%)`);

    // 2. Issue Coverage Analysis
    console.log(`\n${'='.repeat(80)}`);
    console.log('📋 ISSUE COVERAGE ANALYSIS');
    console.log('='.repeat(80));
    
    const recordsWithIssue = await prisma.sentimentData.count({
      where: {
        OR: [
          { issueSlug: { not: null } },
          { issueLabel: { not: null } },
          { query: { not: null } }
        ]
      }
    });
    
    const recordsWithoutIssue = totalRecords - recordsWithIssue;
    
    console.log(`\nRecords with some issue data: ${recordsWithIssue.toLocaleString()} (${((recordsWithIssue / totalRecords) * 100).toFixed(2)}%)`);
    console.log(`Records without issue data: ${recordsWithoutIssue.toLocaleString()} (${((recordsWithoutIssue / totalRecords) * 100).toFixed(2)}%)`);

    // 3. Unique Issues
    console.log(`\n${'='.repeat(80)}`);
    console.log('🏷️  UNIQUE ISSUES');
    console.log('='.repeat(80));
    
    const uniqueIssueSlugs = await prisma.sentimentData.groupBy({
      by: ['issueSlug'],
      where: { issueSlug: { not: null } },
      _count: true,
      orderBy: { _count: { issueSlug: 'desc' } },
      take: 20
    });

    console.log(`\nTotal Unique issueSlugs: ${uniqueIssueSlugs.length}`);
    console.log('\nTop 20 Issues by Record Count:');
    uniqueIssueSlugs.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. "${item.issueSlug}" : ${item._count} records`);
    });

    const uniqueIssueLabels = await prisma.sentimentData.groupBy({
      by: ['issueLabel'],
      where: { issueLabel: { not: null } },
      _count: true,
      orderBy: { _count: { issueLabel: 'desc' } },
      take: 20
    });

    console.log(`\nTotal Unique issueLabels: ${uniqueIssueLabels.length}`);
    console.log('\nTop 20 Issue Labels by Record Count:');
    uniqueIssueLabels.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. "${item.issueLabel}" : ${item._count} records`);
    });

    // 4. Issue Confidence Analysis
    console.log(`\n${'='.repeat(80)}`);
    console.log('📈 ISSUE CONFIDENCE ANALYSIS');
    console.log('='.repeat(80));
    
    const confidenceStats = await prisma.sentimentData.aggregate({
      where: { issueConfidence: { not: null } },
      _avg: { issueConfidence: true },
      _min: { issueConfidence: true },
      _max: { issueConfidence: true },
      _count: true
    });

    if (confidenceStats._count > 0) {
      console.log(`\nRecords with confidence scores: ${confidenceStats._count.toLocaleString()}`);
      console.log(`Average Confidence: ${(confidenceStats._avg.issueConfidence * 100).toFixed(2)}%`);
      console.log(`Min Confidence: ${(confidenceStats._min.issueConfidence * 100).toFixed(2)}%`);
      console.log(`Max Confidence: ${(confidenceStats._max.issueConfidence * 100).toFixed(2)}%`);

      // Confidence distribution
      const highConfidence = await prisma.sentimentData.count({
        where: {
          issueConfidence: { gte: 0.8 }
        }
      });
      const mediumConfidence = await prisma.sentimentData.count({
        where: {
          issueConfidence: { gte: 0.5, lt: 0.8 }
        }
      });
      const lowConfidence = await prisma.sentimentData.count({
        where: {
          issueConfidence: { lt: 0.5 }
        }
      });

      console.log(`\nConfidence Distribution:`);
      console.log(`  High (≥80%): ${highConfidence.toLocaleString()} (${((highConfidence / confidenceStats._count) * 100).toFixed(2)}%)`);
      console.log(`  Medium (50-79%): ${mediumConfidence.toLocaleString()} (${((mediumConfidence / confidenceStats._count) * 100).toFixed(2)}%)`);
      console.log(`  Low (<50%): ${lowConfidence.toLocaleString()} (${((lowConfidence / confidenceStats._count) * 100).toFixed(2)}%)`);
    } else {
      console.log('\n⚠️  No records with confidence scores found');
    }

    // 5. Issue-Ministry Association
    console.log(`\n${'='.repeat(80)}`);
    console.log('🏛️  ISSUE-MINISTRY ASSOCIATION');
    console.log('='.repeat(80));
    
    const issueMinistryData = await prisma.sentimentData.groupBy({
      by: ['issueSlug', 'ministryHint'],
      where: {
        issueSlug: { not: null },
        ministryHint: { not: null }
      },
      _count: true,
      orderBy: { _count: { issueSlug: 'desc' } },
      take: 20
    });

    console.log('\nTop 20 Issue-Ministry Combinations:');
    issueMinistryData.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. Issue: "${item.issueSlug}" | Ministry: "${item.ministryHint}" | Count: ${item._count}`);
    });

    // 6. Query vs IssueSlug Analysis
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔗 QUERY vs ISSUE SLUG ANALYSIS');
    console.log('='.repeat(80));
    
    const withBoth = await prisma.sentimentData.count({
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: { not: null } }
        ]
      }
    });
    
    const queryOnly = await prisma.sentimentData.count({
      where: {
        AND: [
          { query: { not: null } },
          { issueSlug: null }
        ]
      }
    });
    
    const issueSlugOnly = await prisma.sentimentData.count({
      where: {
        AND: [
          { query: null },
          { issueSlug: { not: null } }
        ]
      }
    });

    console.log(`\nRecords with both query and issueSlug: ${withBoth.toLocaleString()}`);
    console.log(`Records with query only (no issueSlug): ${queryOnly.toLocaleString()}`);
    console.log(`Records with issueSlug only (no query): ${issueSlugOnly.toLocaleString()}`);

    // 7. Recent Issues (Last 30 days)
    console.log(`\n${'='.repeat(80)}`);
    console.log('📅 RECENT ISSUES (Last 30 Days)');
    console.log('='.repeat(80));
    
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    const recentIssues = await prisma.sentimentData.groupBy({
      by: ['issueSlug', 'issueLabel', 'ministryHint'],
      where: {
        createdAt: { gte: thirtyDaysAgo },
        OR: [
          { issueSlug: { not: null } },
          { query: { not: null } }
        ]
      },
      _count: true,
      _avg: { sentimentScore: true },
      orderBy: { _count: { issueSlug: 'desc' } },
      take: 15
    });

    console.log(`\nTop 15 Recent Issues (Last 30 Days):`);
    console.log(`${'Rank'.padStart(4)} | ${'Issue Slug'.padEnd(40)} | ${'Count'.padStart(8)} | ${'Avg Sentiment'.padStart(12)} | ${'Ministry'.padEnd(20)}`);
    console.log('-'.repeat(100));
    
    recentIssues.forEach((issue, index) => {
      const rank = (index + 1).toString().padStart(4);
      const slug = (issue.issueSlug || 'N/A').substring(0, 40).padEnd(40);
      const count = issue._count.toString().padStart(8);
      const avgSentiment = issue._avg.sentimentScore 
        ? issue._avg.sentimentScore.toFixed(2).padStart(12)
        : 'N/A'.padStart(12);
      const ministry = (issue.ministryHint || 'N/A').substring(0, 20).padEnd(20);
      console.log(`${rank} | ${slug} | ${count} | ${avgSentiment} | ${ministry}`);
    });

    // 8. Issue Keywords Analysis
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔑 ISSUE KEYWORDS ANALYSIS');
    console.log('='.repeat(80));
    
    const withKeywords = await prisma.sentimentData.findMany({
      where: { issueKeywords: { not: null } },
      select: { issueKeywords: true },
      take: 10
    });

    console.log(`\nSample Issue Keywords (first 10 records):`);
    withKeywords.forEach((record, index) => {
      console.log(`  ${index + 1}. ${JSON.stringify(record.issueKeywords)}`);
    });

    // 9. Data Quality Issues
    console.log(`\n${'='.repeat(80)}`);
    console.log('⚠️  DATA QUALITY ISSUES');
    console.log('='.repeat(80));
    
    const issueSlugNoLabel = await prisma.sentimentData.count({
      where: {
        AND: [
          { issueSlug: { not: null } },
          { issueLabel: null }
        ]
      }
    });
    
    const issueLabelNoSlug = await prisma.sentimentData.count({
      where: {
        AND: [
          { issueLabel: { not: null } },
          { issueSlug: null }
        ]
      }
    });
    
    const issueSlugNoConfidence = await prisma.sentimentData.count({
      where: {
        AND: [
          { issueSlug: { not: null } },
          { issueConfidence: null }
        ]
      }
    });

    console.log(`\nRecords with issueSlug but no issueLabel: ${issueSlugNoLabel.toLocaleString()}`);
    console.log(`Records with issueLabel but no issueSlug: ${issueLabelNoSlug.toLocaleString()}`);
    console.log(`Records with issueSlug but no issueConfidence: ${issueSlugNoConfidence.toLocaleString()}`);

    // 10. Query Pattern Analysis
    console.log(`\n${'='.repeat(80)}`);
    console.log('🔍 QUERY PATTERN ANALYSIS');
    console.log('='.repeat(80));
    
    const uniqueQueries = await prisma.sentimentData.groupBy({
      by: ['query'],
      where: { query: { not: null } },
      _count: true,
      orderBy: { _count: { query: 'desc' } },
      take: 15
    });

    console.log(`\nTop 15 Most Common Queries:`);
    uniqueQueries.forEach((item, index) => {
      console.log(`  ${(index + 1).toString().padStart(2)}. "${item.query}" : ${item._count} records`);
    });

  } catch (error) {
    console.error('❌ Error analyzing issue data:', error);
  } finally {
    await prisma.$disconnect();
  }
}

// Run the analysis
analyzeIssueData()
  .then(() => {
    console.log('\n✅ Issue data analysis completed!');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  });











