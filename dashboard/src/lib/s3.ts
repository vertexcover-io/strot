import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getAppConfig } from './config';

let s3Client: S3Client;

function getS3Client() {
  if (!s3Client) {
    const config = getAppConfig();
    s3Client = new S3Client({
      region: config.aws.region,
      endpoint: config.aws.s3EndpointUrl,
      credentials: {
        accessKeyId: config.aws.accessKeyId,
        secretAccessKey: config.aws.secretAccessKey,
      },
      forcePathStyle: true, // Required for MinIO and other S3-compatible services
    });
  }
  return s3Client;
}

export async function getJobLogFile(jobId: string): Promise<string> {
  const config = getAppConfig();
  const client = getS3Client();

  try {
    const command = new GetObjectCommand({
      Bucket: config.aws.s3LogBucket,
      Key: `job-${jobId}.log`,
    });

    const response = await client.send(command);

    if (!response.Body) {
      throw new Error('Empty response body');
    }

    const logContent = await response.Body.transformToString();
    return logContent;
  } catch (error) {
    console.error('Error fetching log file:', error);
    throw new Error(`Failed to fetch log file for job ${jobId}: ${error}`);
  }
}
