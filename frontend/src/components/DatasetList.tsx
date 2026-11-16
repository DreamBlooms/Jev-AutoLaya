import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, deleteSnapshot } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { formatDate } from "@/lib/format";
import type { DatasetSnapshot } from "@/types/api";

const splitVariants: Record<string, "info" | "secondary" | "warning"> = {
  train: "info",
  validation: "secondary",
  test: "warning",
};

export function DatasetList({
  snapshots,
  loading,
  showProject = false,
}: {
  snapshots: DatasetSnapshot[];
  loading?: boolean;
  showProject?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: deleteSnapshot,
    onSuccess: (_, snapshotId) => {
      const snapshot = snapshots.find((item) => item.id === snapshotId);
      toast.success(t("datasets.deleted"));
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      if (snapshot) queryClient.invalidateQueries({ queryKey: ["project", snapshot.projectId] });
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("datasets.deleteFailed"))),
  });

  if (!snapshots.length && !loading) return <Empty title={t("datasets.noDatasets")} />;
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {snapshots.map((snapshot) => (
        <Card key={snapshot.id}>
          <CardHeader className="flex-row items-start justify-between">
            <CardTitle className="flex items-center gap-2">
              {t("datasets.version")} v{snapshot.version}
              {showProject ? <Badge variant="muted">{snapshot.projectId.slice(0, 8)}</Badge> : null}
            </CardTitle>
            <span className="text-xs text-muted-foreground">{formatDate(snapshot.createdAt, i18n.language)}</span>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              {Object.entries(snapshot.splitCounts).map(([split, count]) => (
                <Badge key={split} variant={splitVariants[split] ?? "secondary"}>
                  {split}: {count}
                </Badge>
              ))}
            </div>
            <div className="grid gap-2">
              {Object.entries(snapshot.labelDistribution).map(([question, labels]) => (
                <div key={question}>
                  <div className="text-xs font-medium text-muted-foreground">{question}</div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {Object.entries(labels).map(([label, count]) => (
                      <Badge key={label} variant="muted">
                        {label}: {count}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(snapshot.teacherModels).map(([teacher, count]) => (
                <Badge key={teacher} variant="info">
                  {teacher}: {count}
                </Badge>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 border-t border-border/70 pt-4">
              <Button size="sm" asChild>
                <a href={snapshot.downloads.laya}>
                  <Download /> {t("datasets.laya")}
                </a>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <a href={snapshot.downloads.canonical}>
                  <Download /> {t("datasets.canonical")}
                </a>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <a href={snapshot.downloads.gliner}>
                  <Download /> {t("datasets.gliner")}
                </a>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto text-destructive"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(t("datasets.deleteConfirm", { version: snapshot.version }))) remove.mutate(snapshot.id);
                }}
              >
                <Trash2 /> {t("common.delete")}
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
