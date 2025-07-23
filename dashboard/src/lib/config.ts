// Configuration utility that matches the AYEJAX_ environment variables format
// Reads directly from system environment variables, just like the Python API

export interface AppConfig {
  env: 'local' | 'prod';
  postgres: {
    user: string;
    password: string;
    db: string;
    host: string;
    port: number;
    uri: string;
  };
  aws: {
    accessKeyId: string;
    secretAccessKey: string;
    region: string;
    s3EndpointUrl: string;
    s3LogBucket: string;
  };
  externalApiRequestTimeout: number;
}

function getEnvVar(key: string, defaultValue?: string): string {
  // Read from system environment variables, not from .env files
  const value = typeof window === 'undefined' ? process.env[key] : undefined;
  return value || defaultValue || '';
}

function buildPostgresUri(user: string, password: string, host: string, port: number, db: string): string {
  return `postgresql://${user}:${password}@${host}:${port}/${db}`;
}

export function getAppConfig(): AppConfig {
  // Mirror the exact same environment variable reading as settings.py

  // PostgreSQL configuration with same defaults as Python
  const postgresUser = getEnvVar('AYEJAX_POSTGRES_USER', 'synacktra');
  const postgresPassword = getEnvVar('AYEJAX_POSTGRES_PASSWORD', 'secretpassword');
  const postgresDb = getEnvVar('AYEJAX_POSTGRES_DB', 'default');
  const postgresHost = getEnvVar('AYEJAX_POSTGRES_HOST', '127.0.0.1');
  const postgresPort = parseInt(getEnvVar('AYEJAX_POSTGRES_PORT', '5432'), 10);

  return {
    env: (getEnvVar('AYEJAX_ENV', 'local') as 'local' | 'prod'),
    postgres: {
      user: postgresUser,
      password: postgresPassword,
      db: postgresDb,
      host: postgresHost,
      port: postgresPort,
      uri: buildPostgresUri(postgresUser, postgresPassword, postgresHost, postgresPort, postgresDb),
    },
    aws: {
      accessKeyId: getEnvVar('AYEJAX_AWS_ACCESS_KEY_ID', 'minioadmin'),
      secretAccessKey: getEnvVar('AYEJAX_AWS_SECRET_ACCESS_KEY', 'minioadmin'),
      region: getEnvVar('AYEJAX_AWS_REGION', 'us-east-1'),
      s3EndpointUrl: getEnvVar('AYEJAX_AWS_S3_ENDPOINT_URL', 'http://localhost:9000'),
      s3LogBucket: getEnvVar('AYEJAX_AWS_S3_LOG_BUCKET', 'job-logs'),
    },
    externalApiRequestTimeout: parseInt(getEnvVar('AYEJAX_EXTERNAL_API_REQUEST_TIMEOUT', '30'), 10),
  };
}
