// Configuration utility that matches the STROT_ environment variables format
// Reads directly from system environment variables, just like the Python API

export interface AppConfig {
  api: {
    baseUrl: string;
  };
  aws: {
    accessKeyId: string;
    secretAccessKey: string;
    region: string;
    s3EndpointUrl: string;
    s3LogBucket: string;
  };
}

function getEnvVar(key: string, defaultValue?: string): string {
  // Read from system environment variables, not from .env files
  const value = typeof window === "undefined" ? process.env[key] : undefined;
  return value || defaultValue || "";
}

export function getAppConfig(): AppConfig {
  return {
    api: {
      baseUrl: getEnvVar("STROT_API_BASE_URL", "http://localhost:1337"),
    },
    aws: {
      accessKeyId: getEnvVar("STROT_AWS_ACCESS_KEY_ID", "strot-user"),
      secretAccessKey: getEnvVar(
        "STROT_AWS_SECRET_ACCESS_KEY",
        "secretpassword",
      ),
      region: getEnvVar("STROT_AWS_REGION", "us-east-1"),
      s3EndpointUrl: getEnvVar(
        "STROT_AWS_S3_ENDPOINT_URL",
        "http://localhost:9000",
      ),
      s3LogBucket: getEnvVar("STROT_AWS_S3_LOG_BUCKET", "job-logs"),
    },
  };
}
