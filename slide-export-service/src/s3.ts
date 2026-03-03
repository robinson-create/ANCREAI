/**
 * S3 upload utility — uploads generated files (PPTX/PDF) to S3/MinIO.
 */

import {
  S3Client,
  PutObjectCommand,
  type PutObjectCommandInput,
} from "@aws-sdk/client-s3";

const s3 = new S3Client({
  region: process.env.AWS_REGION ?? "us-east-1",
  endpoint: process.env.S3_ENDPOINT ?? undefined,
  forcePathStyle: process.env.S3_FORCE_PATH_STYLE === "true",
  credentials:
    process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY
      ? {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
        }
      : undefined,
});

const BUCKET = process.env.S3_BUCKET ?? "ancre-exports";

export interface UploadResult {
  s3_key: string;
  file_size: number;
}

const CONTENT_TYPES: Record<string, string> = {
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  pdf: "application/pdf",
};

/** Upload a buffer to S3 and return the key + size. */
export async function uploadToS3(
  buffer: Buffer,
  s3Key: string,
  contentType?: string,
): Promise<UploadResult> {
  const ext = s3Key.split(".").pop()?.toLowerCase() ?? "pptx";
  const resolvedContentType = contentType ?? CONTENT_TYPES[ext] ?? CONTENT_TYPES.pptx;

  const params: PutObjectCommandInput = {
    Bucket: BUCKET,
    Key: s3Key,
    Body: buffer,
    ContentType: resolvedContentType,
    ContentDisposition: `attachment; filename="${s3Key.split("/").pop()}"`,
  };

  await s3.send(new PutObjectCommand(params));

  return {
    s3_key: s3Key,
    file_size: buffer.byteLength,
  };
}
