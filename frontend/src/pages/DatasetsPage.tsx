import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Snowflake } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { apiErrorMessage, createSnapshot, listProjects, listSnapshots } from "@/api/client";
import { DatasetList } from "@/components/DatasetList";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Select } from "@/components/ui/select";

export function DatasetsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState("");
  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const snapshots = useQuery({ queryKey: ["snapshots"], queryFn: () => listSnapshots() });
  const freeze = useMutation({
    mutationFn: () => createSnapshot(projectId),
    onSuccess: () => { toast.success(t("datasets.frozen")); queryClient.invalidateQueries({ queryKey: ["snapshots"] }); queryClient.invalidateQueries({ queryKey: ["projects"] }); },
    onError: (error) => toast.error(apiErrorMessage(error, t("datasets.freezeFailed"))),
  });
  return (
    <div>
      <PageHeader title={t("datasets.title")} subtitle={t("datasets.subtitle")} extra={<div className="flex flex-wrap gap-2"><Select className="w-52" value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">{t("common.project")}</option>{projects.data?.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select><Button disabled={!projectId || freeze.isPending} onClick={() => freeze.mutate()}><Snowflake /> {t("datasets.freeze")}</Button><Button variant="outline" size="icon" onClick={() => snapshots.refetch()}><RefreshCw /></Button></div>} />
      {projects.data?.length === 0 ? <Card><CardContent className="pt-5"><Empty title={t("projects.noProjects")} action={<Button onClick={() => navigate("/")}>{t("nav.projects")}</Button>} /></CardContent></Card> : <DatasetList snapshots={snapshots.data ?? []} loading={snapshots.isLoading} showProject />}
    </div>
  );
}
