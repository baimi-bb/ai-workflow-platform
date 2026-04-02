import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{
    workspaceId: string;
    projectId: string;
  }>;
};

export default async function ProjectPage({ params }: PageProps) {
  const { workspaceId, projectId } = await params;

  redirect(`/workspaces/${workspaceId}/projects/${projectId}/list`);
}
