import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Snowflake } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, createSnapshot, listSnapshots } from "@/api/client";
import { DatasetList } from "@/components/DatasetList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DatasetsPanel({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const snapshots = useQuery({ queryKey: ["snapshots", projectId], queryFn: () => listSnapshots(projectId) });
  const freeze = useMutation({
    mutationFn: () => createSnapshot(projectId),
    onSuccess: () => { toast.success(t("datasets.frozen")); queryClient.invalidateQueries({ queryKey: ["snapshots", projectId] }); queryClient.invalidateQueries({ queryKey: ["snapshots"] }); queryClient.invalidateQueries({ queryKey: ["project", projectId] }); },
    onError: (error) => toast.error(apiErrorMessage(error, t("datasets.freezeFailed"))),
  });
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between"><div><CardTitle>{t("datasets.title")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("datasets.freezeHint")}</p></div><Button size="sm" disabled={freeze.isPending} onClick={() => freeze.mutate()}><Snowflake /> {t("datasets.freeze")}</Button></CardHeader>
      <CardContent><DatasetList snapshots={snapshots.data ?? []} loading={snapshots.isLoading} /></CardContent>
    </Card>
  );
}
