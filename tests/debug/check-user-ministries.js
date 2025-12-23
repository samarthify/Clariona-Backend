const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkUserMinistries() {
  try {
    console.log('🔍 Checking user ministry values in database...\n');

    // Get all users with their ministries
    const users = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        name: true,
        ministry: true,
        role: true
      },
      where: {
        ministry: { not: null }
      }
    });

    console.log(`📊 Total users with ministry: ${users.length}\n`);

    if (users.length === 0) {
      console.log('✅ No users with ministry values found.\n');
      return;
    }

    // Group by ministry
    const ministryGroups = {};
    users.forEach(user => {
      const ministry = user.ministry || 'NULL';
      if (!ministryGroups[ministry]) {
        ministryGroups[ministry] = [];
      }
      ministryGroups[ministry].push(user);
    });

    console.log('🏛️  Ministry Distribution:\n');
    console.log(`${'Ministry'.padEnd(30)} | ${'User Count'.padStart(10)}`);
    console.log('-'.repeat(45));

    Object.entries(ministryGroups)
      .sort((a, b) => b[1].length - a[1].length)
      .forEach(([ministry, users]) => {
        console.log(`${ministry.padEnd(30)} | ${users.length.toString().padStart(10)}`);
      });

    // Check for old frontend values
    console.log('\n🔍 Checking for old frontend ministry values...\n');
    const oldValues = ['health', 'defense', 'agriculture', 'transport', 'energy', 'communication', 'youth-sports'];
    const oldValueUsers = {};

    users.forEach(user => {
      if (oldValues.includes(user.ministry)) {
        if (!oldValueUsers[user.ministry]) {
          oldValueUsers[user.ministry] = [];
        }
        oldValueUsers[user.ministry].push(user);
      }
    });

    if (Object.keys(oldValueUsers).length > 0) {
      console.log('⚠️  Found users with old frontend ministry values:\n');
      Object.entries(oldValueUsers).forEach(([ministry, users]) => {
        console.log(`   "${ministry}": ${users.length} users`);
        users.forEach(user => {
          console.log(`     - ${user.email} (${user.name || 'N/A'})`);
        });
      });
      console.log('\n💡 These need to be migrated to backend values!\n');
    } else {
      console.log('✅ No old frontend values found in user profiles.\n');
    }

  } catch (error) {
    console.error('❌ Error checking user ministries:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkUserMinistries();






