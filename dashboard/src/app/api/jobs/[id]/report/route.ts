import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getJobLogFile } from "@/lib/s3";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const resolvedParams = await params;

    // Verify job exists
    const job = await prisma.job.findUnique({
      where: {
        id: resolvedParams.id,
      },
    });

    if (!job) {
      return NextResponse.json({ error: "Job not found" }, { status: 404 });
    }

    // Fetch log file from S3
    try {
      const logContent = await getJobLogFile(resolvedParams.id);

      // For now, return the raw log content
      // TODO: Integrate with the Python report generation logic
      return NextResponse.json({
        jobId: resolvedParams.id,
        logContent,
        reportHtml: null, // Will be populated when we integrate the report generator
      });
    } catch (s3Error) {
      return NextResponse.json(
        { error: `Failed to fetch log file: ${s3Error}` },
        { status: 404 },
      );
    }
  } catch (error) {
    console.error("Error generating report:", error);
    return NextResponse.json(
      { error: "Failed to generate report" },
      { status: 500 },
    );
  }
}
