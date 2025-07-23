// Import env setup FIRST to ensure DATABASE_URL is set before Prisma loads
import './env';
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

// Simple Prisma client creation - DATABASE_URL is already set by env.ts
function createPrismaClient() {
  console.log('🔧 Creating Prisma client with DATABASE_URL:', process.env.DATABASE_URL?.replace('secretpassword', '****'));

  return new PrismaClient({
    log: ['query', 'error', 'warn'],
  });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
