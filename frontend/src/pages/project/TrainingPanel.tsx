import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlayCircle, StopCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, cancelTrainingJob, createTrainingJob, getConfig, listSnapshots, listTrainingJobs } from "@/api/client";
import { JobStatusTag } from "@/components/StatusTag";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useJobEvents } from "@/hooks/useJobEvents";
import { formatDate } from "@/lib/format";
import type { TrainingJob } from "@/types/api";

type ModelChoice = "laya-default" | "laya-multilingual" | "gliner-english" | "gliner-multilingual";

export function TrainingPanel({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [snapshotId, setSnapshotId] = useState("");
  const [modelChoice, setModelChoice] = useState<ModelChoice>("laya-default");
  const [mode, setMode] = useState<"fit" | "finetune">("finetune");
  const [device, setDevice] = useState("auto");
  const [epochs, setEpochs] = useState(4);
  const [microBatch, setMicroBatch] = useState(8);
  const [gradAccum, setGradAccum] = useState(8);
  const [loss, setLoss] = useState("rlcd");
  const [freezeEncoder, setFreezeEncoder] = useState(false);
  const [shuffleOptions, setShuffleOptions] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<TrainingJob | null>(null);

  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const snapshots = useQuery({ queryKey: ["snapshots", projectId], queryFn: () => listSnapshots(projectId) });
  const jobs = useQuery({
    queryKey: ["training-jobs", projectId],
    queryFn: () => listTrainingJobs(projectId),
    refetchInterval: (query) => query.state.data?.some((job) => ["pending", "running"].includes(job.status)) ? 4000 : false,
  });

  const target: "laya" | "gliner" = modelChoice.startsWith("gliner") ? "gliner" : "laya";
  const baseModel = target === "gliner"
    ? config.data?.glinerModels[modelChoice === "gliner-multilingual" ? "multilingual" : "english"]
    : config.data?.layaModels[modelChoice === "laya-multilingual" ? "multilingual" : "default"];
  const runtimeReady = target === "gliner" ? config.data?.glinerRuntimeReady : config.data?.layaRuntimeReady;

  useEffect(() => {
    if (!snapshotId && snapshots.data?.length) setSnapshotId(snapshots.data[0].id);
  }, [snapshotId, snapshots.data]);
  useEffect(() => {
    if (activeId && jobs.data) setActiveJob(jobs.data.find((job) => job.id === activeId) ?? activeJob);
  }, [activeId, jobs.data, activeJob]);

  useJobEvents<TrainingJob>(activeId ? `/api/v1/training-jobs/${activeId}/events` : null, (job) => {
    setActiveJob(job);
    if (["completed", "failed", "cancelled"].includes(job.status)) {
      queryClient.invalidateQueries({ queryKey: ["training-jobs", projectId] });
      queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      if (job.status === "completed") toast.success(t("train.completed"));
    }
  });

  const start = useMutation({
    mutationFn: () => createTrainingJob({
      projectId,
      snapshotId,
      target,
      mode: target === "gliner" ? "finetune" : mode,
      device,
      baseModel,
      config: { epochs, microBatch, gradAccum, encoderLr: 2.5e-5, headLr: 1e-4, loss, labelSmoothing: 0, shuffleOptions, freezeEncoder, targetError: 0.1, minAbstainN: 10 },
    }),
    onSuccess: (job) => {
      setActiveId(job.id);
      setActiveJob(job);
      queryClient.invalidateQueries({ queryKey: ["training-jobs", projectId] });
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const cancel = useMutation({
    mutationFn: cancelTrainingJob,
    onSuccess: setActiveJob,
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });

  return (
    <div className="grid gap-5">
      {!runtimeReady ? <Alert variant="warning"><AlertTitle>{target === "gliner" ? t("train.glinerRuntimeMissing") : t("train.runtimeMissing")}</AlertTitle><AlertDescription>{target === "gliner" ? t("train.glinerRuntimeHint") : t("train.runtimeHint")}</AlertDescription></Alert> : null}
      <Card>
        <CardHeader><CardTitle>{t("train.title")}</CardTitle><p className="text-xs text-muted-foreground">{t("train.subtitle")}</p></CardHeader>
        <CardContent className="grid gap-4">
          {!snapshots.data?.length ? <Alert variant="info"><AlertTitle>{t("train.noSnapshots")}</AlertTitle></Alert> : null}
          <div className="grid gap-4 md:grid-cols-5">
            <div className="grid gap-2 md:col-span-2"><Label>{t("train.snapshot")}</Label><Select value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)}>{snapshots.data?.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>v{snapshot.version} · {formatDate(snapshot.createdAt, i18n.language)}</option>)}</Select></div>
            <div className="grid gap-2 md:col-span-2"><Label>{t("train.targetBase")}</Label><Select value={modelChoice} onChange={(event) => setModelChoice(event.target.value as ModelChoice)}><option value="laya-default">{t("train.layaDefault")}</option><option value="laya-multilingual">{t("train.layaMultilingual")}</option><option value="gliner-english" disabled={!config.data?.glinerEnabled}>{t("train.glinerEnglish")}</option><option value="gliner-multilingual" disabled={!config.data?.glinerEnabled}>{t("train.glinerMultilingual")}</option></Select></div>
            <div className="grid gap-2"><Label>{t("train.device")}</Label><Select value={device} onChange={(event) => setDevice(event.target.value)}><option value="auto">auto</option>{(config.data?.availableDevices ?? ["cpu"]).map((item) => <option key={item} value={item}>{item}</option>)}</Select></div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <div className="grid gap-2"><Label>{t("train.mode")}</Label><Select value={target === "gliner" ? "finetune" : mode} disabled={target === "gliner"} onChange={(event) => setMode(event.target.value as "fit" | "finetune")}><option value="fit">{t("train.fit")}</option><option value="finetune">{t("train.finetune")}</option></Select></div>
            <div className="grid gap-2"><Label>{t("train.epochs")}</Label><Input type="number" min={1} max={100} value={epochs} onChange={(event) => setEpochs(Number(event.target.value))} /></div>
            <div className="grid gap-2"><Label>{t("train.microBatch")}</Label><Input type="number" min={1} max={256} value={microBatch} onChange={(event) => setMicroBatch(Number(event.target.value))} /></div>
            <div className="grid gap-2"><Label>{t("train.gradAccum")}</Label><Input type="number" min={1} max={256} value={gradAccum} onChange={(event) => setGradAccum(Number(event.target.value))} /></div>
            {target === "laya" ? <div className="grid gap-2"><Label>{t("train.loss")}</Label><Select value={loss} onChange={(event) => setLoss(event.target.value)}><option value="rlcd">rlcd</option><option value="soft-ce">soft-ce</option></Select></div> : null}
          </div>
          {target === "laya" ? (
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"><span>{t("train.freezeEncoder")}</span><Switch checked={freezeEncoder} onCheckedChange={setFreezeEncoder} /></label>
              <label className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"><span>{t("train.shuffleOptions")}</span><Switch checked={shuffleOptions} onCheckedChange={setShuffleOptions} /></label>
            </div>
          ) : <p className="text-xs text-muted-foreground">{t("train.glinerHint")}</p>}
          <div className="flex items-center gap-3"><Button disabled={!snapshotId || !runtimeReady || !baseModel || start.isPending} onClick={() => start.mutate()}><PlayCircle /> {t("train.start")}</Button><span className="text-xs text-muted-foreground">{target === "gliner" ? t("train.glinerHint") : mode === "fit" ? t("train.fitHint") : t("train.finetuneHint")}</span></div>
        </CardContent>
      </Card>

      {activeJob ? (
        <Card>
          <CardHeader className="flex-row items-start justify-between"><div><CardTitle className="flex items-center gap-2">{t("common.job")} <JobStatusTag status={activeJob.status} /></CardTitle><p className="mt-1 text-xs text-muted-foreground">{activeJob.stage}</p></div>{!["completed", "failed", "cancelled"].includes(activeJob.status) ? <Button size="sm" variant="destructive" onClick={() => cancel.mutate(activeJob.id)}><StopCircle /> {t("train.cancel")}</Button> : null}</CardHeader>
          <CardContent className="grid gap-3"><Progress value={activeJob.progress} /><div className="grid grid-cols-3 gap-2 text-sm"><div><span className="text-muted-foreground">{t("train.mode")}: </span>{activeJob.mode}</div><div><span className="text-muted-foreground">{t("common.device")}: </span>{activeJob.device}</div><div className="col-span-1 truncate"><span className="text-muted-foreground">{t("train.artifact")}: </span>{activeJob.artifactPath ?? "—"}</div></div>{activeJob.error ? <Alert variant="destructive"><AlertTitle>{activeJob.error}</AlertTitle></Alert> : null}{activeJob.logPath ? <p className="text-xs text-muted-foreground">{t("train.log")}: {activeJob.logPath}</p> : null}</CardContent>
        </Card>
      ) : null}

      <Card><CardHeader><CardTitle>{t("common.job")}</CardTitle></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>{t("common.createdAt")}</TableHead><TableHead>{t("train.target")}</TableHead><TableHead>{t("train.mode")}</TableHead><TableHead>{t("common.status")}</TableHead><TableHead>{t("common.progress")}</TableHead><TableHead className="w-24" /></TableRow></TableHeader><TableBody>{jobs.data?.map((job) => <TableRow key={job.id}><TableCell className="text-xs text-muted-foreground">{formatDate(job.createdAt, i18n.language)}</TableCell><TableCell><Badge>{job.target}</Badge></TableCell><TableCell>{job.mode}</TableCell><TableCell><JobStatusTag status={job.status} /></TableCell><TableCell className="w-40"><Progress value={job.progress} /></TableCell><TableCell><Button size="sm" variant="ghost" onClick={() => setActiveId(job.id)}>{t("common.learnMore")}</Button></TableCell></TableRow>)}</TableBody></Table>{!jobs.data?.length ? <p className="py-8 text-center text-sm text-muted-foreground">{t("train.noJobs")}</p> : null}</CardContent></Card>
    </div>
  );
}
