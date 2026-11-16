import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Loader2, RotateCw, Server, Square, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, createDeployment, deleteArtifact, deleteDeployment, downloadArtifact, listArtifacts, listDeployments, listProjects, restartDeployment, stopDeployment } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { JobStatusTag } from "@/components/StatusTag";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate } from "@/lib/format";
import type { Deployment, ModelArtifact } from "@/types/api";

export function ModelsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [artifact, setArtifact] = useState<ModelArtifact | null>(null);
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("");
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const artifacts = useQuery({ queryKey: ["artifacts"], queryFn: () => listArtifacts() });
  const deployments = useQuery({ queryKey: ["deployments"], queryFn: () => listDeployments(), refetchInterval: (query) => query.state.data?.some((item) => ["starting", "running"].includes(item.status)) ? 3000 : false });
  const projectName = (projectId: string) => projects.data?.find((project) => project.id === projectId)?.name ?? projectId.slice(0, 8);
  const artifactName = (artifactId: string | null) => artifacts.data?.find((item) => item.id === artifactId)?.name ?? "—";

  const deploy = useMutation({
    mutationFn: () => createDeployment({ artifactId: artifact?.id ?? "", target: artifact?.target === "gliner" ? "gliner" : "laya", host: host || undefined, port: port ? Number(port) : undefined }),
    onSuccess: () => { toast.success(t("models.starting")); setArtifact(null); setPort(""); queryClient.invalidateQueries({ queryKey: ["deployments"] }); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const stop = useMutation({ mutationFn: stopDeployment, onSuccess: () => { toast.success(t("models.stopped")); queryClient.invalidateQueries({ queryKey: ["deployments"] }); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const restart = useMutation({ mutationFn: restartDeployment, onSuccess: () => { toast.success(t("models.starting")); queryClient.invalidateQueries({ queryKey: ["deployments"] }); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const removeArtifact = useMutation({ mutationFn: deleteArtifact, onSuccess: () => { toast.success(t("common.saved")); queryClient.invalidateQueries({ queryKey: ["artifacts"] }); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))) });
  const removeDeployment = useMutation({ mutationFn: deleteDeployment, onSuccess: () => { toast.success(t("common.saved")); queryClient.invalidateQueries({ queryKey: ["deployments"] }); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))) });
  const download = useMutation({
    mutationFn: (item: ModelArtifact) => downloadArtifact(item.id, setDownloadProgress),
    onMutate: (item) => {
      setDownloadingId(item.id);
      setDownloadProgress(null);
      toast.loading(t("models.downloadPreparing"), { id: "artifact-download" });
    },
    onSuccess: () => toast.success(t("models.downloaded"), { id: "artifact-download" }),
    onError: (error) => toast.error(apiErrorMessage(error, t("models.downloadFailed")), { id: "artifact-download" }),
    onSettled: () => {
      setDownloadingId(null);
      setDownloadProgress(null);
    },
  });
  const kindLabel = (kind: string) => kind === "checkpoint" ? t("models.checkpoint") : kind === "gliner_checkpoint" ? t("models.glinerCheckpoint") : t("models.calibration");

  return (
    <div>
      <PageHeader title={t("models.title")} subtitle={t("models.subtitle")} />
      <div className="grid gap-5">
        <Card>
          <CardHeader><CardTitle>{t("models.artifacts")}</CardTitle></CardHeader>
          <CardContent>
            {artifacts.data?.length ? (
              <Table><TableHeader><TableRow><TableHead>{t("common.name")}</TableHead><TableHead>{t("models.kind")}</TableHead><TableHead>{t("models.path")}</TableHead><TableHead>{t("models.created")}</TableHead><TableHead className="w-72" /></TableRow></TableHeader><TableBody>{artifacts.data.map((item) => <TableRow key={item.id}><TableCell><div className="font-medium">{item.name}</div><div className="text-xs text-muted-foreground">{projectName(item.projectId)}</div></TableCell><TableCell><Badge variant={item.kind === "gliner_checkpoint" ? "success" : item.kind === "checkpoint" ? "info" : "secondary"}>{kindLabel(item.kind)}</Badge></TableCell><TableCell><span className="mono block max-w-xs truncate text-xs text-muted-foreground">{item.path}</span></TableCell><TableCell className="text-xs text-muted-foreground">{formatDate(item.createdAt, i18n.language)}</TableCell><TableCell><div className="flex justify-end gap-1"><Button size="sm" variant="outline" disabled={download.isPending} onClick={() => download.mutate(item)}>{downloadingId === item.id ? <Loader2 className="animate-spin" /> : <Download />}{downloadingId === item.id ? (downloadProgress === null ? t("models.packaging") : t("models.downloadingPercent", { percent: downloadProgress })) : t("models.download")}</Button><Button size="sm" variant="outline" onClick={() => { setArtifact(item); setHost("127.0.0.1"); setPort(""); }}><Server /> {t("models.deploy")}</Button><Button size="sm" variant="ghost" className="text-destructive" onClick={() => { if (window.confirm(t("common.confirm"))) removeArtifact.mutate(item.id); }}><Trash2 /> {t("common.delete")}</Button></div></TableCell></TableRow>)}</TableBody></Table>
            ) : <Empty title={t("models.noArtifacts")} />}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("models.deployments")}</CardTitle></CardHeader>
          <CardContent>
            {deployments.data?.length ? (
              <Table><TableHeader><TableRow><TableHead>{t("models.url")}</TableHead><TableHead>{t("models.status")}</TableHead><TableHead>{t("models.started")}</TableHead><TableHead className="w-64" /></TableRow></TableHeader><TableBody>{deployments.data.map((item: Deployment) => <TableRow key={item.id}><TableCell><a className="mono text-xs text-primary hover:underline" href={`http://${item.host}:${item.port}/v1/systemone`} target="_blank" rel="noreferrer">http://{item.host}:{item.port}/v1/systemone</a><div className="text-xs text-muted-foreground">{artifactName(item.artifactId)}</div></TableCell><TableCell><JobStatusTag status={item.status} /></TableCell><TableCell className="text-xs text-muted-foreground">{item.startedAt ? formatDate(item.startedAt, i18n.language) : "—"}</TableCell><TableCell><div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => restart.mutate(item.id)}><RotateCw /> {t("models.restart")}</Button><Button size="sm" variant="outline" className="text-destructive" onClick={() => stop.mutate(item.id)}><Square /> {t("models.stop")}</Button><Button size="sm" variant="ghost" className="text-destructive" onClick={() => { if (window.confirm(t("common.confirm"))) removeDeployment.mutate(item.id); }}><Trash2 /> {t("common.delete")}</Button></div></TableCell></TableRow>)}</TableBody></Table>
            ) : <Empty title={t("models.noDeployments")} />}
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(artifact)} onOpenChange={(open) => !open && setArtifact(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t("models.deployTitle")}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">{artifact?.name}</p>
          <div className="grid gap-3"><div className="grid gap-2"><Label>{t("models.host")}</Label><Input value={host} onChange={(event) => setHost(event.target.value)} /></div><div className="grid gap-2"><Label>{t("models.port")}</Label><Input type="number" min={1024} max={65535} value={port} onChange={(event) => setPort(event.target.value)} placeholder={t("models.portHint")} /></div></div>
          <DialogFooter><Button variant="outline" onClick={() => setArtifact(null)}>{t("common.cancel")}</Button><Button disabled={deploy.isPending} onClick={() => deploy.mutate()}>{t("models.deploy")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
