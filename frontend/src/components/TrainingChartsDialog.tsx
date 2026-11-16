import { useQuery } from "@tanstack/react-query";
import { ChartNoAxesCombined, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getTrainingCharts } from "@/api/client";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import type { TrainingCharts, TrainingHeadMetrics, TrainingJob, TrainingMetricSeries } from "@/types/api";

const COLORS = ["#0ea5e9", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"];
const SERIES_LABELS: Record<string, string> = {
  loss: "train.chartLoss",
  loss_step: "train.chartLossStep",
  eval_loss: "train.chartEvalLoss",
  learning_rate: "train.chartLearningRate",
  learning_rate_encoder: "train.chartEncoderLr",
  learning_rate_head: "train.chartHeadLr",
  classification_loss: "train.chartClassificationLoss",
  structure_loss: "train.chartStructureLoss",
  count_loss: "train.chartCountLoss",
  eval_classification_loss: "train.chartEvalClassificationLoss",
  eval_structure_loss: "train.chartEvalStructureLoss",
  eval_count_loss: "train.chartEvalCountLoss",
  throughput: "train.chartThroughput",
};

function isRatio(key: string) {
  return ["accuracy", "ece", "brier", "chance", "cv_accuracy", "engine_accuracy"].includes(key);
}

function isLearningRate(key: string) {
  return key.includes("learning_rate");
}

function formatValue(key: string, value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (isLearningRate(key)) return value.toExponential(2);
  if (isRatio(key)) return `${(value * 100).toFixed(1)}%`;
  if (key === "throughput" || key === "samples_per_second") return value.toFixed(2);
  return value.toFixed(4);
}

function LineChart({ title, series }: { title: string; series: TrainingMetricSeries[] }) {
  const { t } = useTranslation();
  if (!series.length) return null;
  const allPoints = series.flatMap((item) => item.points);
  if (!allPoints.length) return null;
  const width = 720;
  const height = 240;
  const pad = { left: 52, right: 16, top: 16, bottom: 28 };
  const minY = Math.min(...allPoints.map((point) => point.value));
  const maxY = Math.max(...allPoints.map((point) => point.value));
  const yRange = maxY - minY || Math.max(Math.abs(maxY) * 0.1, 0.0001);
  const maxPointCount = Math.max(...series.map((item) => item.points.length));
  const xFor = (index: number, count: number) => pad.left + (count <= 1 ? 0 : (index / (count - 1)) * (width - pad.left - pad.right));
  const yFor = (value: number) => pad.top + (1 - (value - (minY - yRange * 0.08)) / (yRange * 1.16)) * (height - pad.top - pad.bottom);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const formatKey = series[0]?.key ?? "";

  return (
    <div className="grid gap-3 rounded-xl border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><div className="text-sm font-semibold">{title}</div><div className="flex flex-wrap gap-2">{series.map((item, index) => <span key={item.key} className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"><span className="size-2 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />{t(SERIES_LABELS[item.key] ?? item.key)}</span>)}</div></div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-52 w-full" role="img" aria-label={title}>
        {ticks.map((tick) => {
          const y = pad.top + tick * (height - pad.top - pad.bottom);
          const value = (minY - yRange * 0.08) + (1 - tick) * yRange * 1.16;
          return <g key={tick}><line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="currentColor" strokeOpacity=".1" /><text x={pad.left - 8} y={y + 3} textAnchor="end" fontSize="10" fill="currentColor" opacity=".55">{formatValue(formatKey, value)}</text></g>;
        })}
        <text x={pad.left} y={height - 8} fontSize="10" fill="currentColor" opacity=".55">1</text>
        <text x={width - pad.right} y={height - 8} textAnchor="end" fontSize="10" fill="currentColor" opacity=".55">{maxPointCount}</text>
        {series.map((item, index) => {
          const points = item.points.map((point, pointIndex) => `${xFor(pointIndex, item.points.length)},${yFor(point.value)}`).join(" ");
          return <g key={item.key}><polyline points={points} fill="none" stroke={COLORS[index % COLORS.length]} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />{item.points.map((point, pointIndex) => <circle key={pointIndex} cx={xFor(pointIndex, item.points.length)} cy={yFor(point.value)} r="2.8" fill={COLORS[index % COLORS.length]} />)}</g>;
        })}
      </svg>
    </div>
  );
}

interface BarGroup {
  label: string;
  values: { label: string; value: number | null; key: string }[];
}

function BarGroups({ title, groups }: { title: string; groups: BarGroup[] }) {
  const { t } = useTranslation();
  if (!groups.length) return null;
  return (
    <div className="grid gap-3 rounded-xl border border-border p-4">
      <div className="text-sm font-semibold">{title}</div>
      <div className="grid gap-4">
        {groups.map((group) => {
          const max = Math.max(0.0001, ...group.values.map((item) => item.value ?? 0));
          return (
            <div key={group.label} className="grid gap-1.5">
              <div className="text-xs font-medium text-muted-foreground">{group.label}</div>
              {group.values.map((item, index) => (
                <div key={item.label} className="flex items-center gap-2 text-[10px]">
                  <span className="w-24 shrink-0 truncate text-muted-foreground" title={item.label}>{item.label}</span>
                  <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, ((item.value ?? 0) / max) * 100))}%`, backgroundColor: COLORS[index % COLORS.length] }} /></div>
                  <span className="w-16 shrink-0 text-right font-mono">{formatValue(item.key, item.value)}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">{groups[0]?.values.map((item, index) => <span key={item.label} className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"><span className="size-2 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />{item.label}</span>)}</div>
      <span className="sr-only">{t("train.chartMetrics")}</span>
    </div>
  );
}

function summaryNumber(value: unknown, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

function headGroups(heads: TrainingHeadMetrics[], t: (key: string) => string): BarGroup[] {
  return heads.map((head) => ({
    label: head.key,
    values: [
      { label: t("train.chartCvAccuracy"), key: "cv_accuracy", value: head.cvAccuracy },
      { label: t("train.chartEngineAccuracy"), key: "engine_accuracy", value: head.engineAccuracy },
      { label: t("train.chartChance"), key: "chance", value: head.chance },
    ],
  }));
}

function eceGroups(heads: TrainingHeadMetrics[], t: (key: string) => string): BarGroup[] {
  return heads.map((head) => ({
    label: head.key,
    values: [
      { label: t("train.chartBeforeEce"), key: "ece", value: head.eceBefore },
      { label: t("train.chartAfterEce"), key: "ece", value: head.eceAfter },
    ],
  }));
}

function ComparisonBars({ charts }: { charts: TrainingCharts }) {
  const { t } = useTranslation();
  const before = (charts.summary.before ?? {}) as Record<string, unknown>;
  const after = (charts.summary.after ?? {}) as Record<string, unknown>;
  const metrics = [
    ["loss", t("train.chartLoss")],
    ["accuracy", t("train.chartAccuracy")],
    ["ece", t("train.chartEce")],
    ["brier", t("train.chartBrier")],
  ] as const;
  const groups = metrics.map(([key, label]) => ({
    label,
    values: [
      { label: t("train.chartBefore"), key, value: typeof before[key] === "number" ? before[key] : null },
      { label: t("train.chartAfter"), key, value: typeof after[key] === "number" ? after[key] : null },
    ],
  }));
  return <BarGroups title={t("train.chartComparison")} groups={groups} />;
}

function summaryCards(charts: TrainingCharts) {
  const s = charts.summary;
  if (charts.target === "gliner") {
    return [
      ["train.chartSteps", summaryNumber(s.total_steps, 0)],
      ["train.chartEpochs", summaryNumber(s.total_epochs, 0)],
      ["train.chartBestMetric", summaryNumber(s.best_metric, 4)],
      ["train.chartSamplesPerSecond", summaryNumber(s.samples_per_second, 2)],
    ];
  }
  if (charts.mode === "fit") {
    return [
      ["train.chartRows", summaryNumber(s.n_rows, 0)],
      ["train.chartFitRows", summaryNumber(s.n_fit, 0)],
      ["train.chartCalibrationRows", summaryNumber(s.n_calibrate, 0)],
      ["train.chartServing", Array.isArray(s.serving) ? String(s.serving.length) : "—"],
    ];
  }
  return [];
}

export function TrainingChartsDialog({ job, onOpenChange }: { job: TrainingJob | null; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["training-charts", job?.id],
    queryFn: () => getTrainingCharts(job!.id),
    enabled: Boolean(job),
  });
  const charts = query.data;
  const byKey = new Map((charts?.series ?? []).map((series) => [series.key, series]));
  const loss = [byKey.get("loss"), byKey.get("loss_step"), byKey.get("eval_loss")].filter((item): item is TrainingMetricSeries => Boolean(item));
  const lr = [byKey.get("learning_rate_encoder"), byKey.get("learning_rate_head"), byKey.get("learning_rate")].filter((item): item is TrainingMetricSeries => Boolean(item));
  const auxiliary = ["classification_loss", "structure_loss", "count_loss", "eval_classification_loss", "eval_structure_loss", "eval_count_loss"].map((key) => byKey.get(key)).filter((item): item is TrainingMetricSeries => Boolean(item));
  const throughput = byKey.get("throughput") ? [byKey.get("throughput")!] : [];
  const cards = charts ? summaryCards(charts) : [];
  return (
    <Dialog open={Boolean(job)} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-6xl overflow-y-auto">
        <DialogHeader><DialogTitle className="flex items-center gap-2"><ChartNoAxesCombined className="size-5" /> {t("train.chartsTitle")}</DialogTitle><p className="text-xs text-muted-foreground">{job ? `${job.target} · ${job.mode} · #${job.id.slice(0, 8)}` : ""}</p></DialogHeader>
        {query.isLoading ? <div className="grid min-h-48 place-items-center"><Loader2 className="animate-spin text-muted-foreground" /></div> : query.isError ? <Alert variant="destructive"><AlertTitle>{t("train.chartFailed")}</AlertTitle></Alert> : charts ? (
          <div className="grid gap-4">
            {cards.length ? <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{cards.map(([label, value]) => <div key={label} className="rounded-lg border border-border bg-muted/15 p-3"><div className="text-lg font-semibold">{value}</div><div className="text-[10px] text-muted-foreground">{t(label)}</div></div>)}</div> : null}
            {charts.warnings.length ? <Alert variant="info"><AlertTitle>{t("train.chartNotes")}</AlertTitle><div className="mt-1 grid gap-1 text-xs text-muted-foreground">{charts.warnings.map((warning) => <span key={warning}>{warning}</span>)}</div></Alert> : null}
            {loss.length ? <LineChart title={t("train.chartLossLearning")} series={loss} /> : null}
            {lr.length ? <LineChart title={t("train.chartLearningRate")} series={lr} /> : null}
            {auxiliary.length ? <LineChart title={t("train.chartAuxiliaryLoss")} series={auxiliary} /> : null}
            {throughput.length ? <LineChart title={t("train.chartThroughput")} series={throughput} /> : null}
            {charts.heads.length ? <BarGroups title={t("train.chartHeadAccuracy")} groups={headGroups(charts.heads, t)} /> : null}
            {charts.heads.length ? <BarGroups title={t("train.chartHeadEce")} groups={eceGroups(charts.heads, t)} /> : null}
            {charts.summary.before && charts.summary.after ? <ComparisonBars charts={charts} /> : null}
            {!loss.length && !lr.length && !auxiliary.length && !throughput.length && !charts.heads.length && !charts.summary.before ? <Empty title={t("train.chartNoData")} /> : null}
            {charts.logPath ? <p className="truncate text-[10px] text-muted-foreground" title={charts.logPath}>{t("train.chartLogPath")}: {charts.logPath}</p> : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
