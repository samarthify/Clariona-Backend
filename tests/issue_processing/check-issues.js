const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkIssues() {
  try {
    // Check issue labels and slugs
    const issueData = await prisma.sentimentData.findMany({
      select: {
        issueLabel: true,
        issueSlug: true,
        title: true,
        query: true,
        sentimentLabel: true,
        sentimentScore: true
      },
      where: {
        OR: [
          { issueSlug: { not: null } },
          { issueLabel: { not: null } },
          { query: { not: null } }
        ]
      },
      take: 10
    });
    
    console.log('Issue data samples:');
    console.log(JSON.stringify(issueData, null, 2));
    
    // Check grouped data like the API does
    const groupedIssues = await prisma.sentimentData.groupBy({
      by: ['issueSlug', 'issueLabel', 'ministryHint'],
      where: {
        OR: [
          { issueSlug: { not: null } },
          { query: { not: null } }
        ]
      },
      _count: true,
      _avg: { sentimentScore: true },
      _max: { createdAt: true },
      take: 5
    });
    
    console.log('\nGrouped issues (like API):');
    console.log(JSON.stringify(groupedIssues, null, 2));
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkIssues();
