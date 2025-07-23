// Set DATABASE_URL immediately when this module loads, before Prisma is imported anywhere
import { getAppConfig } from './config';

const config = getAppConfig();
process.env.DATABASE_URL = config.postgres.uri;

console.log('🔧 DATABASE_URL set to:', config.postgres.uri.replace(config.postgres.password, '****'));
