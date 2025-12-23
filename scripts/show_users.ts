import { PrismaClient } from '@prisma/client'

const DATABASE_URL = process.env.DATABASE_URL || 'postgresql://postgres:qmQiSbzPrSaaaDaDcDpDhBUgyVUVdKPg@yamanote.proxy.rlwy.net:21252/railway?connect_timeout=300&sslmode=require'

// Create Prisma client with the provided DATABASE_URL
const prisma = new PrismaClient({
  datasources: {
    db: {
      url: DATABASE_URL
    }
  }
})

async function showUsers() {
  try {
    console.log('Connecting to database...\n')
    
    // Test connection
    await prisma.$connect()
    console.log('✅ Connected to database\n')
    
    // Get table structure info
    console.log('📊 User Table Structure:')
    console.log('=' .repeat(80))
    console.log('Column Name          | Type              | Nullable | Description')
    console.log('-'.repeat(80))
    console.log('id                   | UUID              | NO       | Primary Key')
    console.log('email                | VARCHAR           | NO       | Unique')
    console.log('username             | VARCHAR(100)      | YES      | Optional')
    console.log('password_hash        | VARCHAR(255)      | YES      | Optional')
    console.log('role                 | VARCHAR(50)       | YES      | Optional')
    console.log('ministry             | VARCHAR(50)       | YES      | Optional')
    console.log('name                 | VARCHAR(200)      | YES      | Optional')
    console.log('created_at           | TIMESTAMPTZ(6)    | YES      | Default: now()')
    console.log('last_login           | TIMESTAMPTZ(6)    | YES      | Optional')
    console.log('is_admin             | BOOLEAN           | YES      | Default: false')
    console.log('api_calls_count      | INTEGER           | YES      | Default: 0')
    console.log('data_entries_count   | INTEGER           | YES      | Default: 0')
    console.log('=' .repeat(80))
    console.log()
    
    // Get all users
    const users = await prisma.user.findMany({
      orderBy: {
        createdAt: 'desc'
      }
    })
    
    console.log(`📋 Total Users: ${users.length}\n`)
    
    if (users.length === 0) {
      console.log('No users found in the database.')
    } else {
      console.log('User Records:')
      console.log('=' .repeat(120))
      
      users.forEach((user, index) => {
        console.log(`\n[User ${index + 1}]`)
        console.log(`  ID:                ${user.id}`)
        console.log(`  Email:             ${user.email}`)
        console.log(`  Username:          ${user.username || 'N/A'}`)
        console.log(`  Name:              ${user.name || 'N/A'}`)
        console.log(`  Role:              ${user.role || 'N/A'}`)
        console.log(`  Ministry:          ${user.ministry || 'N/A'}`)
        console.log(`  Is Admin:          ${user.isAdmin ? 'Yes' : 'No'}`)
        console.log(`  Created At:        ${user.createdAt ? new Date(user.createdAt).toLocaleString() : 'N/A'}`)
        console.log(`  Last Login:        ${user.lastLogin ? new Date(user.lastLogin).toLocaleString() : 'N/A'}`)
        console.log(`  API Calls Count:   ${user.apiCallsCount || 0}`)
        console.log(`  Data Entries Count: ${user.dataEntriesCount || 0}`)
        console.log(`  Password Hash:      ${user.passwordHash ? '***' + user.passwordHash.slice(-4) : 'N/A'}`)
      })
      
      console.log('\n' + '='.repeat(120))
    }
    
    // Get some statistics
    const adminCount = users.filter(u => u.isAdmin).length
    const usersWithRole = users.filter(u => u.role).length
    const usersWithMinistry = users.filter(u => u.ministry).length
    
    console.log('\n📈 Statistics:')
    console.log(`  Total Users:        ${users.length}`)
    console.log(`  Admin Users:        ${adminCount}`)
    console.log(`  Users with Role:    ${usersWithRole}`)
    console.log(`  Users with Ministry: ${usersWithMinistry}`)
    
  } catch (error) {
    console.error('❌ Error querying database:')
    console.error(error)
    process.exit(1)
  } finally {
    await prisma.$disconnect()
  }
}

showUsers()













