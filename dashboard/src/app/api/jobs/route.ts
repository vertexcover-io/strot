import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || "20");
    const status = searchParams.get("status") || undefined;

    const skip = (page - 1) * limit;

    // Get latest jobs grouped by URL+tag combination
    const jobs = await prisma.job.findMany({
      where: status ? { status } : undefined,
      include: {
        output: true,
      },
      orderBy: {
        createdAt: "desc",
      },
      skip,
      take: limit,
    });

    // Group by URL+tag and keep only the latest for each combination
    const latestJobsMap = new Map<string, (typeof jobs)[0]>();

    for (const job of jobs) {
      const key = `${job.url}:${job.tag}`;
      const existing = latestJobsMap.get(key);

      if (!existing || job.createdAt > existing.createdAt) {
        latestJobsMap.set(key, job);
      }
    }

    const latestJobs = Array.from(latestJobsMap.values()).sort(
      (a, b) => b.createdAt.getTime() - a.createdAt.getTime(),
    );

    // Get total count for pagination
    const totalJobs = await prisma.job.count({
      where: status ? { status } : undefined,
    });

    return NextResponse.json({
      jobs: latestJobs,
      pagination: {
        page,
        limit,
        total: totalJobs,
        pages: Math.ceil(totalJobs / limit),
      },
    });
  } catch (error) {
    console.error("Error fetching jobs:", error);
    return NextResponse.json(
      { error: "Failed to fetch jobs" },
      { status: 500 },
    );
  }
}
