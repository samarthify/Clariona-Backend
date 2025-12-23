const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

// Function to generate a slug from text
function generateSlug(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim('-');
}

// Function to create a meaningful label from query
function createIssueLabel(query) {
  if (!query) return null;
  
  // Split by comma and clean up
  const terms = query.split(',').map(term => term.trim()).filter(term => term.length > 0);
  
  if (terms.length === 0) return null;
  
  // If it's a single term, use it as is
  if (terms.length === 1) {
    return terms[0];
  }
  
  // If multiple terms, create a more descriptive label
  if (terms.length <= 3) {
    return terms.join(' & ');
  }
  
  // For many terms, use the first few
  return terms.slice(0, 3).join(', ') + ' & others';
}

async function populateIssues() {
  try {
    console.log('🔍 Finding records with null issueSlug and issueLabel...');
    
    // Find records that need population
    const recordsToUpdate = await prisma.sentimentData.findMany({
      where: {
        AND: [
          { issueSlug: null },
          { issueLabel: null },
          { query: { not: null } }
        ]
      },
      select: {
        entryId: true,
        query: true
      },
      take: 1000 // Process in batches
    });
    
    console.log(`📊 Found ${recordsToUpdate.length} records to update`);
    
    if (recordsToUpdate.length === 0) {
      console.log('✅ No records need updating');
      return;
    }
    
    // Process each record
    let updatedCount = 0;
    for (const record of recordsToUpdate) {
      const issueLabel = createIssueLabel(record.query);
      const issueSlug = issueLabel ? generateSlug(issueLabel) : null;
      
      if (issueLabel && issueSlug) {
        await prisma.sentimentData.update({
          where: { entryId: record.entryId },
          data: {
            issueLabel: issueLabel,
            issueSlug: issueSlug
          }
        });
        
        updatedCount++;
        
        if (updatedCount % 100 === 0) {
          console.log(`✅ Updated ${updatedCount} records...`);
        }
      }
    }
    
    console.log(`🎉 Successfully updated ${updatedCount} records!`);
    
    // Show some examples of what was created
    console.log('\n📋 Sample of updated records:');
    const samples = await prisma.sentimentData.findMany({
      where: {
        issueLabel: { not: null },
        issueSlug: { not: null }
      },
      select: {
        issueLabel: true,
        issueSlug: true,
        query: true
      },
      take: 5
    });
    
    console.log(JSON.stringify(samples, null, 2));
    
  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

populateIssues();

