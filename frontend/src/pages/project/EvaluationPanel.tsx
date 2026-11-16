import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, History, PlayCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, createEvaluation, evaluationReportUrl, getConfig, listArtifacts, listEvaluations, listSnapshots } from "@/api/client";
import { JobStatusTag } from "@/components/StatusTag";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useJobEvents } from "@/hooks/useJobEvents";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EvaluationRun, ModelArtifact } from "@/types/api";

interface QuestionMetrics { type: string; n: number; accuracy: number | null; macro_f1: number | null; mae: number | null; ece: number | null; brier: number | null }
interface ArtifactInfo { id: string; name: string; kind: string; path: string; createdAt: string | null }
interface ModelInfo { role?: string; target?: string; source?: string; provider?: string; artifact?: ArtifactInfo }
interface ModelMetrics { n: number; accuracy: number | null; errors: number; latency_p50_ms: number | null; latency_p95_ms: number | null; probability_fidelity?: string; questions: Record<string, QuestionMetrics> }
interface EvaluationResults { holdout: boolean; source: string; rows: number; models: Record<string, ModelMetrics>; modelInfo?: Record<string, ModelInfo> }
interface ModelOption { value: string; title: string; source: string; disabled: boolean; more?: { kind: ArtifactKind; count: number } }
interface ModelGroup { key: string; title: string; hint: string; variant: "info" | "secondary" | "success"; items: ModelOption[] }

type ModelRole = "remote" | "base" | "fit" | "finetuned";
type ArtifactKind = "calibration" | "checkpoint" | "gliner_checkpoint";

const metric = (value: number | null | undefined) => value === null || value === undefined ? "—" : value;

function fallbackRole(model: string): ModelRole {
  if (model === "jev") return "remote";
  if (model.endsWith("-base")) return "base";
  if (model === "laya-fit") return "fit";
  return "finetuned";
}

function fallbackTarget(model: string): string {
  if (model === "jev") return "jev";
  return model.startsWith("gliner") ? "gliner" : "laya";
}

const HISTORY_MODEL: Record<ArtifactKind, string> = {
  calibration: "laya-fit",
  checkpoint: "laya-finetuned",
  gliner_checkpoint: "gliner-finetuned",
};

const roleVariant: Record<ModelRole, "info" | "secondary" | "warning" | "success"> = {
  remote: "info",
  base: "secondary",
  fit: "warning",
  finetuned: "success",
};

export function EvaluationPanel({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [snapshotId, setSnapshotId] = useState("");
  const [models, setModels] = useState<string[]>(["laya-base"]);
  const [device, setDevice] = useState("auto");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<EvaluationRun | null>(null);
  const [selectedArtifactIds, setSelectedArtifactIds] = useState<Record<string, string>>({});
  const [historyKind, setHistoryKind] = useState<ArtifactKind | null>(null);

  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const snapshots = useQuery({ queryKey: ["snapshots", projectId], queryFn: () => listSnapshots(projectId) });
  const artifacts = useQuery({ queryKey: ["artifacts", projectId], queryFn: () => listArtifacts(projectId) });
  const runs = useQuery({ queryKey: ["evaluations", projectId], queryFn: () => listEvaluations(projectId), refetchInterval: (query) => query.state.data?.some((run) => ["pending", "running"].includes(run.status)) ? 4000 : false });

  useEffect(() => { if (!snapshotId && snapshots.data?.length) setSnapshotId(snapshots.data[0].id); }, [snapshotId, snapshots.data]);
  useEffect(() => { if (activeId && runs.data) setActiveRun(runs.data.find((run) => run.id === activeId) ?? activeRun); }, [activeId, runs.data, activeRun]);
  useJobEvents<EvaluationRun>(activeId ? `/api/v1/evaluations/${activeId}/events` : null, (run) => {
    setActiveRun(run);
    if (["completed", "failed", "cancelled"].includes(run.status)) {
      queryClient.invalidateQueries({ queryKey: ["evaluations", projectId] });
      if (run.status === "completed") toast.success(t("evaluate.completed"));
    }
  });

  const artifactsForKind = (kind: ArtifactKind): ModelArtifact[] => (artifacts.data ?? [])
    .filter((item) => item.kind === kind)
    .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt));
  const selectedArtifact = (modelKey: string, kind: ArtifactKind): ModelArtifact | undefined => {
    const matching = artifactsForKind(kind);
    return matching.find((item) => item.id === selectedArtifactIds[modelKey]) ?? matching[0];
  };
  const fitArtifact = selectedArtifact("laya-fit", "calibration");
  const layaCheckpoint = selectedArtifact("laya-finetuned", "checkpoint");
  const glinerCheckpoint = selectedArtifact("gliner-finetuned", "gliner_checkpoint");
  const hasFit = Boolean(fitArtifact);
  const hasFinetuned = Boolean(layaCheckpoint);
  const hasGliner = Boolean(glinerCheckpoint);

  const roleLabel = (role: ModelRole) => {
    if (role === "remote") return t("evaluate.roleRemote");
    if (role === "base") return t("evaluate.roleBase");
    if (role === "fit") return t("evaluate.roleFit");
    return t("evaluate.roleFinetuned");
  };
  const kindLabel = (kind: string) => kind === "calibration" ? t("evaluate.kindCalibration") : kind === "gliner_checkpoint" ? t("evaluate.kindGliner") : t("evaluate.kindCheckpoint");
  const targetLabel = (target: string) => target === "laya" ? "Laya" : target === "gliner" ? "GLiNER2.5" : "Jev";
  const artifactSource = (artifact: ModelArtifact | undefined, kind: ArtifactKind) => {
    if (!artifact) return t("evaluate.noArtifact");
    const latest = artifactsForKind(kind)[0];
    return `${kindLabel(artifact.kind)} · ${artifact.id === latest?.id ? t("evaluate.latest") : t("evaluate.previousVersion")} · ${formatDate(artifact.createdAt, i18n.language)}`;
  };

  const modelGroups: ModelGroup[] = [
    {
      key: "remote",
      title: t("evaluate.groupRemote"),
      hint: t("evaluate.groupRemoteHint"),
      variant: "info",
      items: [
        {
          value: "jev",
          title: "Jev",
          source: [config.data?.jevProvider, config.data?.jevModel].filter(Boolean).join(" · ") || "—",
          disabled: !config.data?.jevConfigured,
        },
      ],
    },
    {
      key: "base",
      title: t("evaluate.groupBase"),
      hint: t("evaluate.groupBaseHint"),
      variant: "secondary",
      items: [
        { value: "laya-base", title: t("evaluate.layaBase"), source: config.data?.layaModels?.default ?? "—", disabled: !config.data?.layaRuntimeReady },
        { value: "laya-multi-base", title: t("evaluate.layaMultiBase"), source: config.data?.layaModels?.multilingual ?? "—", disabled: !config.data?.layaRuntimeReady },
        { value: "gliner-base", title: t("evaluate.glinerBase"), source: config.data?.glinerModels?.english ?? "—", disabled: !config.data?.glinerRuntimeReady },
        { value: "gliner-multi-base", title: t("evaluate.glinerMultiBase"), source: config.data?.glinerModels?.multilingual ?? "—", disabled: !config.data?.glinerRuntimeReady },
      ],
    },
    {
      key: "trained",
      title: t("evaluate.groupTrained"),
      hint: t("evaluate.groupTrainedHint"),
      variant: "success",
      items: [
        { value: "laya-fit", title: fitArtifact?.name ?? t("evaluate.layaFit"), source: artifactSource(fitArtifact, "calibration"), disabled: !fitArtifact || !config.data?.layaRuntimeReady, more: artifactsForKind("calibration").length > 1 ? { kind: "calibration", count: artifactsForKind("calibration").length } : undefined },
        { value: "laya-finetuned", title: layaCheckpoint?.name ?? t("evaluate.layaFinetuned"), source: artifactSource(layaCheckpoint, "checkpoint"), disabled: !layaCheckpoint || !config.data?.layaRuntimeReady, more: artifactsForKind("checkpoint").length > 1 ? { kind: "checkpoint", count: artifactsForKind("checkpoint").length } : undefined },
        { value: "gliner-finetuned", title: glinerCheckpoint?.name ?? t("evaluate.glinerFinetuned"), source: artifactSource(glinerCheckpoint, "gliner_checkpoint"), disabled: !glinerCheckpoint || !config.data?.glinerRuntimeReady, more: artifactsForKind("gliner_checkpoint").length > 1 ? { kind: "gliner_checkpoint", count: artifactsForKind("gliner_checkpoint").length } : undefined },
      ],
    },
  ];

  const toggleModel = (value: string, checked: boolean) => setModels((current) => checked ? [...new Set([...current, value])] : current.filter((item) => item !== value));

  const start = useMutation({
    mutationFn: () => {
      const existingIds = new Set((artifacts.data ?? []).map((artifact) => artifact.id));
      const artifactIds = Object.fromEntries(Object.entries(selectedArtifactIds).filter(([modelKey, artifactId]) => models.includes(modelKey) && existingIds.has(artifactId)));
      return createEvaluation({ projectId, snapshotId, models, device, artifactIds });
    },
    onSuccess: (run) => { setActiveId(run.id); setActiveRun(run); queryClient.invalidateQueries({ queryKey: ["evaluations", projectId] }); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const results = activeRun?.results as EvaluationResults | undefined;
  const runtimeReady = !models.some((model) => model.startsWith("gliner")) || config.data?.glinerRuntimeReady;
  const historyItems = historyKind ? artifactsForKind(historyKind) : [];
  const historyModelKey = historyKind ? HISTORY_MODEL[historyKind] : "";
  const historySelected = historyKind ? selectedArtifact(historyModelKey, historyKind) : undefined;

  const describeModel = (model: string) => {
    const info = results?.modelInfo?.[model];
    const role = (info?.role as ModelRole | undefined) ?? fallbackRole(model);
    const target = info?.target ?? fallbackTarget(model);
    const artifact = info?.artifact;
    const baseTitle = model === "jev" ? "Jev" : model === "laya-base" ? t("evaluate.layaBase") : model === "laya-multi-base" ? t("evaluate.layaMultiBase") : model === "laya-fit" ? t("evaluate.layaFit") : model === "laya-finetuned" ? t("evaluate.layaFinetuned") : model === "gliner-base" ? t("evaluate.glinerBase") : model === "gliner-multi-base" ? t("evaluate.glinerMultiBase") : model === "gliner-finetuned" ? t("evaluate.glinerFinetuned") : model;
    return {
      role,
      target,
      title: artifact?.name ?? baseTitle,
      artifact,
      source: info?.source ?? (info ? "" : t("evaluate.legacyNoMetadata")),
      provider: info?.provider,
    };
  };

  const resultGroups: { key: string; title: string; variant: "info" | "secondary" | "success"; items: [string, ModelMetrics][] }[] = results ? [
    { key: "remote", title: t("evaluate.groupRemote"), variant: "info", items: Object.entries(results.models).filter(([model]) => describeModel(model).role === "remote") },
    { key: "base", title: t("evaluate.groupBase"), variant: "secondary", items: Object.entries(results.models).filter(([model]) => describeModel(model).role === "base") },
    { key: "trained", title: t("evaluate.groupTrained"), variant: "success", items: Object.entries(results.models).filter(([model]) => ["fit", "finetuned"].includes(describeModel(model).role)) },
  ] : [];

  return (
    <div className="grid gap-5">
      {!config.data?.layaRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("train.runtimeMissing")}</AlertTitle></Alert> : null}
      <Card>
        <CardHeader><CardTitle>{t("evaluate.title")}</CardTitle><p className="text-xs text-muted-foreground">{t("evaluate.subtitle")}</p></CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="grid gap-2"><Label>{t("evaluate.snapshot")}</Label><Select value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)}>{snapshots.data?.map((snapshot) => <option key={snapshot.id} value={snapshot.id}>v{snapshot.version} · {formatDate(snapshot.createdAt, i18n.language)}</option>)}</Select></div>
            <div className="grid gap-2"><Label>{t("train.device")}</Label><Select value={device} onChange={(event) => setDevice(event.target.value)}><option value="auto">auto</option>{(config.data?.availableDevices ?? ["cpu"]).map((item) => <option key={item} value={item}>{item}</option>)}</Select></div>
          </div>
          <div className="grid gap-2"><Label>{t("evaluate.models")}</Label><div className="grid gap-3 lg:grid-cols-3">{modelGroups.map((group) => (
            <div key={group.key} className="grid content-start gap-3 rounded-xl border border-border bg-muted/15 p-3">
              <div className="flex flex-wrap items-center gap-2"><Badge variant={group.variant}>{group.title}</Badge></div>
              <p className="text-xs text-muted-foreground">{group.hint}</p>
              <div className="grid gap-2">{group.items.map((item) => (
                <div key={item.value} className={cn("flex items-start gap-1 rounded-lg border border-border bg-background/60 text-sm transition-colors", item.disabled ? "opacity-50" : "hover:bg-accent/40")}>
                  <label className={cn("flex min-w-0 flex-1 items-start gap-2 px-3 py-2", item.disabled ? "cursor-not-allowed" : "cursor-pointer")}>
                    <Checkbox className="mt-0.5" checked={models.includes(item.value)} disabled={item.disabled} onCheckedChange={(value) => toggleModel(item.value, value === true)} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium" title={item.title}>{item.title}</span>
                      <span className="block truncate font-mono text-[10px] text-muted-foreground" title={item.source}>{item.source}</span>
                    </span>
                  </label>
                  {item.more ? (
                    <Button type="button" size="sm" variant="ghost" className="my-1 mr-1 shrink-0" onClick={() => setHistoryKind(item.more!.kind)}>
                      <History /> {t("evaluate.more")}
                    </Button>
                  ) : null}
                </div>
              ))}</div>
            </div>
          ))}</div></div>
          <div className="flex items-center gap-2"><Button disabled={!snapshotId || !models.length || !runtimeReady || start.isPending} onClick={() => start.mutate()}><PlayCircle /> {t("evaluate.start")}</Button>{!hasFit || !hasFinetuned || !hasGliner ? <span className="text-xs text-muted-foreground">{t("evaluate.missingArtifact")}</span> : null}</div>
        </CardContent>
      </Card>

      {activeRun ? (
        <Card>
          <CardHeader className="flex-row items-start justify-between"><div><CardTitle className="flex items-center gap-2">{t("common.job")} <JobStatusTag status={activeRun.status} /></CardTitle><p className="mt-1 text-xs text-muted-foreground">{activeRun.stage}</p></div>{activeRun.reportPath ? <div className="flex gap-2"><Button size="sm" variant="outline" asChild><a href={evaluationReportUrl(activeRun.id, "json")}><Download /> JSON</a></Button><Button size="sm" variant="outline" asChild><a href={evaluationReportUrl(activeRun.id, "md")}><Download /> MD</a></Button></div> : null}</CardHeader>
          <CardContent className="grid gap-3"><Progress value={activeRun.progress} />{activeRun.error ? <Alert variant="destructive"><AlertTitle>{activeRun.error}</AlertTitle></Alert> : null}</CardContent>
        </Card>
      ) : null}

      {results ? (
        <div className="grid gap-5">
          <Alert variant={results.holdout ? "success" : "warning"}><AlertTitle>{t("evaluate.holdout")}: {results.rows}</AlertTitle><p className="text-sm text-muted-foreground">{results.holdout ? results.source : t("evaluate.allRows")}</p></Alert>
          {resultGroups.map((group) => group.items.length ? (
            <div key={group.key} className="grid gap-3">
              <div className="flex items-center gap-2"><Badge variant={group.variant}>{group.title}</Badge><span className="text-xs text-muted-foreground">{group.items.length}</span></div>
              <div className="grid gap-3 xl:grid-cols-2">
                {group.items.map(([model, data]) => {
                  const info = describeModel(model);
                  return (
                    <Card key={model}>
                      <CardHeader className="gap-2">
                        <div className="flex flex-wrap items-center gap-2"><CardTitle className="text-base">{info.title}</CardTitle><Badge variant={roleVariant[info.role]}>{roleLabel(info.role)}</Badge><Badge variant="outline">{targetLabel(info.target)}</Badge></div>
                        <div className="grid min-w-0 gap-1 text-xs text-muted-foreground">
                          {info.artifact?.createdAt ? <span>{kindLabel(info.artifact.kind)} · {formatDate(info.artifact.createdAt, i18n.language)}</span> : null}
                          <span className="block min-w-0 truncate font-mono" title={info.source}>{t("evaluate.modelSource")}: {info.source || "—"}</span>
                          {info.provider ? <span>{t("evaluate.provider")}: {info.provider}</span> : null}
                        </div>
                      </CardHeader>
                      <CardContent className="grid gap-4">
                        {data.probability_fidelity === "confidence_only" ? <Alert variant="info"><AlertTitle>{t("evaluate.confidenceOnly")}</AlertTitle></Alert> : null}
                        <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">{[["Accuracy", data.accuracy], ["P50", data.latency_p50_ms], ["P95", data.latency_p95_ms], ["N", data.n]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-muted/40 p-3"><div className="text-lg font-semibold">{metric(value as number | null)}</div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div></div>)}</div>
                        <Table><TableHeader><TableRow><TableHead>{t("evaluate.question")}</TableHead><TableHead>{t("evaluate.n")}</TableHead><TableHead>{t("evaluate.accuracy")}</TableHead><TableHead>{t("evaluate.macroF1")}</TableHead><TableHead>{t("evaluate.mae")}</TableHead><TableHead>{t("evaluate.ece")}</TableHead></TableRow></TableHeader><TableBody>{Object.entries(data.questions).map(([key, item]) => <TableRow key={key}><TableCell><code className="mono text-xs">{key}</code></TableCell><TableCell>{item.n}</TableCell><TableCell>{metric(item.accuracy)}</TableCell><TableCell>{metric(item.macro_f1)}</TableCell><TableCell>{metric(item.mae)}</TableCell><TableCell>{metric(item.ece)}</TableCell></TableRow>)}</TableBody></Table>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          ) : null)}
        </div>
      ) : null}

      <Card><CardHeader><CardTitle>{t("common.job")}</CardTitle></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>{t("common.createdAt")}</TableHead><TableHead>{t("common.status")}</TableHead><TableHead>{t("evaluate.models")}</TableHead><TableHead>{t("common.progress")}</TableHead><TableHead className="w-24" /></TableRow></TableHeader><TableBody>{runs.data?.map((run) => <TableRow key={run.id}><TableCell className="text-xs text-muted-foreground">{formatDate(run.createdAt, i18n.language)}</TableCell><TableCell><JobStatusTag status={run.status} /></TableCell><TableCell><div className="flex flex-wrap gap-1">{run.models.map((model) => <Badge key={model} variant="secondary">{model}</Badge>)}</div></TableCell><TableCell className="w-40"><Progress value={run.progress} /></TableCell><TableCell><Button size="sm" variant="ghost" onClick={() => setActiveId(run.id)}>{t("common.learnMore")}</Button></TableCell></TableRow>)}</TableBody></Table>{!runs.data?.length ? <p className="py-8 text-center text-sm text-muted-foreground">{t("evaluate.noRuns")}</p> : null}</CardContent></Card>

      <Dialog open={historyKind !== null} onOpenChange={(open) => { if (!open) setHistoryKind(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{t("evaluate.historyTitle")}</DialogTitle></DialogHeader>
          <p className="text-xs text-muted-foreground">{t("evaluate.historyHint")}</p>
          <div className="grid max-h-[55vh] gap-2 overflow-auto pr-1">
            {historyItems.map((artifact) => {
              const isLatest = artifact.id === historyItems[0]?.id;
              const isSelected = artifact.id === historySelected?.id;
              return (
                <button key={artifact.id} type="button" className={cn("grid gap-1 rounded-lg border border-border p-3 text-left transition-colors hover:bg-accent/40", isSelected && "border-primary/50 bg-primary/5")} onClick={() => { if (historyModelKey) setSelectedArtifactIds((current) => ({ ...current, [historyModelKey]: artifact.id })); }}>
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{artifact.name}</span>{isLatest ? <Badge variant="success">{t("evaluate.latest")}</Badge> : null}{isSelected ? <Badge variant="info">{t("evaluate.selected")}</Badge> : null}</div>
                  <div className="text-xs text-muted-foreground">{kindLabel(artifact.kind)} · {formatDate(artifact.createdAt, i18n.language)}</div>
                  <div className="truncate font-mono text-[10px] text-muted-foreground" title={artifact.path}>{artifact.path}</div>
                </button>
              );
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { if (historyModelKey) setSelectedArtifactIds((current) => { const next = { ...current }; delete next[historyModelKey]; return next; }); setHistoryKind(null); }}>{t("evaluate.useLatest")}</Button>
            <Button variant="outline" onClick={() => setHistoryKind(null)}>{t("common.close")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
