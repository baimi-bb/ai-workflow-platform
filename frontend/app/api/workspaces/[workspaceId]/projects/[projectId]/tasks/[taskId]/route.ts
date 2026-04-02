import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/api";

type RouteContext = {
  params: Promise<{
    workspaceId: string;
    projectId: string;
    taskId: string;
  }>;
};

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { workspaceId, projectId, taskId } = await context.params;
  const body = await request.text();

  const response = await fetch(
    `${apiBaseUrl}/api/v1/workspaces/${workspaceId}/projects/${projectId}/tasks/${taskId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body,
      cache: "no-store",
    },
  );

  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
    },
  });
}
