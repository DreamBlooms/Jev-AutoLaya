import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Compass, Cpu, HardDrive, Info, Laptop, MemoryStick, ShieldCheck, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, getConfig, setDevice } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppStore } from "@/store/useAppStore";
import type { GpuDevice } from "@/types/api";

function formatMemory(mb: number | null) {
  if (mb === null) return "—";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
}

function GpuCard({ device }: { device: GpuDevice }) {
  const { t } = useTranslation();
  const total = device.memoryTotalMb;
  const used = device.memoryUsedMb;
  const percent = total && total > 0 && used !== null ? Math.min(100, Math.round((used / total) * 100)) : null;
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-muted/15 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-medium" title={device.name}>{device.name}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {device.vendor}
            {device.computeCapability ? ` · ${device.computeCapability}` : ""}
          </div>
        </div>
        <Badge variant={device.backend === "cuda" ? "success" : device.backend === "rocm" ? "warning" : "secondary"}>{device.backend.toUpperCase()}</Badge>
      </div>
      {total !== null && used !== null ? (
        <div className="mt-1 grid gap-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground"><span>{t("settings.gpuMemory")}</span><span>{formatMemory(used)} / {formatMemory(total)}</span></div>
          <Progress value={percent ?? 0} />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{t("settings.gpuMemoryUnavailable")}</p>
      )}
      {device.driver ? <p className="truncate text-xs text-muted-foreground" title={device.driver}>{t("settings.gpuDriver")}: {device.driver}</p> : null}
    </div>
  );
}

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const theme = useAppStore((state) => state.theme);
  const setTheme = useAppStore((state) => state.setTheme);
  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const update = useMutation({ mutationFn: setDevice, onSuccess: () => { toast.success(t("settings.deviceSaved")); queryClient.invalidateQueries({ queryKey: ["config"] }); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const language = i18n.language.startsWith("zh") ? "zh" : "en";

  if (config.isLoading) return <Card><CardContent className="space-y-3 pt-5"><Skeleton className="h-8 w-60" /><Skeleton className="h-48 w-full" /></CardContent></Card>;
  const data = config.data;
  if (!data) return <Alert variant="destructive"><AlertTitle>{t("errors.load")}</AlertTitle><AlertDescription>{apiErrorMessage(config.error, t("errors.load"))}</AlertDescription></Alert>;

  const memoryTotal = data.memory.totalMb;
  const memoryAvailable = data.memory.availableMb;
  const memoryUsed = memoryTotal !== null && memoryAvailable !== null ? Math.max(0, memoryTotal - memoryAvailable) : null;
  const memoryPercent = memoryTotal && memoryUsed !== null ? Math.min(100, Math.round((memoryUsed / memoryTotal) * 100)) : null;
  const fallbackGpu = data.gpuDevices.length === 0
    ? data.availableDevices.filter((item) => item === "cuda" || item === "rocm")
    : [];

  return (
    <div>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} extra={<Button variant="outline" asChild><a href="/docs" target="_blank" rel="noreferrer"><Info /> {t("settings.docs")}</a></Button>} />
      <div className="grid gap-4">
        <Alert variant="info"><ShieldCheck className="size-4" /><AlertTitle>{t("settings.warning")}</AlertTitle><AlertDescription>{t("settings.phase")}</AlertDescription></Alert>
        {!data.layaRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("settings.layaSetupHint")}</AlertTitle></Alert> : null}
        {data.glinerEnabled && !data.glinerRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("settings.glinerSetupHint")}</AlertTitle></Alert> : null}

        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2">
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div><CardTitle className="flex items-center gap-2"><Laptop className="size-4" /> {t("settings.runtime")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("settings.runtimeHint")}</p></div>
              <div className="flex flex-wrap justify-end gap-1"><Badge variant="success">{data.device.toUpperCase()}</Badge><Badge variant={data.layaRuntimeReady ? "success" : "muted"}>Laya</Badge>{data.glinerEnabled ? <Badge variant={data.glinerRuntimeReady ? "success" : "muted"}>GLiNER</Badge> : null}</div>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.device")}</span><Select value={data.devicePreference} disabled={update.isPending} onChange={(event) => update.mutate(event.target.value)}><option value="auto">auto · {data.device}</option>{data.availableDevices.map((device) => <option key={device} value={device}>{device}</option>)}</Select></div>
                <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.available")}</span><div className="flex min-h-9 flex-wrap items-center gap-1 rounded-lg border border-border bg-muted/20 px-3 py-1.5">{data.availableDevices.map((device) => <Badge key={device} variant={device === data.device ? "success" : "muted"}>{device}</Badge>)}</div></div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-border p-3"><div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">{t("settings.layaRuntime")}</span><Badge variant={data.layaRuntimeReady ? "success" : "muted"}>{data.layaRuntimeReady ? t("settings.ready") : t("settings.notReady")}</Badge></div><code className="mono mt-2 block break-all text-[11px] text-muted-foreground">{data.layaVenv}</code></div>
                <div className="rounded-lg border border-border p-3"><div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">{t("settings.glinerRuntime")}</span><Badge variant={data.glinerRuntimeReady ? "success" : "muted"}>{data.glinerRuntimeReady ? t("settings.ready") : t("settings.notReady")}</Badge></div><code className="mono mt-2 block break-all text-[11px] text-muted-foreground">{data.glinerVenv}</code></div>
              </div>
              <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.targets")}</span><div className="flex flex-wrap gap-1">{data.targets.map((target) => <Badge key={target} variant="success">{target}</Badge>)}{data.reservedTargets.map((target) => <Badge key={target} variant="muted">{target} · {t("settings.reserved")}</Badge>)}</div></div>
              <div className="grid gap-3 md:grid-cols-3">
                {[[t("settings.dataDir"), data.dataDir], [t("settings.modelsDir"), data.modelsDir], [t("settings.artifactDir"), data.artifactDir]].map(([label, value]) => (
                  <div key={label} className="grid content-start gap-2 rounded-lg border border-border p-3"><span className="text-xs text-muted-foreground">{label}</span><code className="mono break-all text-[11px]">{value}</code></div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Cpu className="size-4" /> {t("settings.hardwareTitle")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("settings.hardwareHint")}</p></CardHeader>
            <CardContent className="grid gap-3">
              <div className="grid gap-2 rounded-lg border border-border bg-muted/15 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><Cpu className="size-4 text-muted-foreground" /><span className="text-sm font-medium">CPU</span></div>{data.cpu.logicalCores !== null ? <Badge variant="muted">{data.cpu.logicalCores} {t("settings.cores")}</Badge> : null}</div>
                <p className="truncate text-xs text-muted-foreground" title={data.cpu.name}>{data.cpu.name}</p>
              </div>
              <div className="grid gap-2 rounded-lg border border-border bg-muted/15 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><MemoryStick className="size-4 text-muted-foreground" /><span className="text-sm font-medium">RAM</span></div><span className="text-xs text-muted-foreground">{memoryUsed !== null && memoryTotal !== null ? `${formatMemory(memoryUsed)} / ${formatMemory(memoryTotal)}` : t("settings.gpuMemoryUnavailable")}</span></div>
                <Progress value={memoryPercent ?? 0} />
                <p className="text-xs text-muted-foreground">{t("settings.memoryAvailable")}: {formatMemory(memoryAvailable)}</p>
              </div>
              {data.gpuDevices.length ? data.gpuDevices.map((device, index) => <GpuCard key={`${device.backend}-${device.name}-${index}`} device={device} />) : fallbackGpu.length ? (
                fallbackGpu.map((backend) => (
                  <div key={backend} className="grid gap-2 rounded-lg border border-border bg-muted/15 p-3">
                    <div className="flex items-center justify-between gap-2"><span className="font-medium">{backend === "cuda" ? "CUDA GPU" : "ROCm GPU"}</span><Badge variant={backend === "cuda" ? "success" : "warning"}>{backend.toUpperCase()}</Badge></div>
                    <p className="text-xs text-muted-foreground">{t("settings.gpuDetailsUnavailable", { backend })}</p>
                  </div>
                ))
              ) : <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">{t("settings.noGpu")}</div>}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="size-4" /> {t("settings.providersTitle")}</CardTitle></CardHeader>
            <CardContent className="grid gap-3">
              <div className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{t("settings.llm")}</span><Badge variant={data.llmConfigured ? "success" : "muted"}>{data.llmConfigured ? t("settings.configured") : t("settings.notConfigured")}</Badge></div>
                <div className="mt-2 grid gap-1 text-xs text-muted-foreground"><span>{t("settings.provider")}: {data.llmProvider}</span><span>{t("settings.model")}: <code className="mono">{data.llmModel}</code></span><span className="truncate" title={data.llmBaseUrl}>{data.llmBaseUrl}</span></div>
              </div>
              <div className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{t("settings.teacher")}</span><Badge variant={data.jevConfigured ? "success" : "muted"}>{data.jevConfigured ? t("settings.configured") : t("settings.notConfigured")}</Badge></div>
                <div className="mt-2 grid gap-1 text-xs text-muted-foreground"><span>{t("settings.provider")}: {data.jevProvider}</span><span className="truncate" title={data.jevModel}>{t("settings.model")}: <code className="mono">{data.jevModel || "—"}</code></span></div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><HardDrive className="size-4" /> {t("settings.preferencesTitle")}</CardTitle></CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.languageTitle")}</span><div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">{[{ value: "zh", label: "简体中文" }, { value: "en", label: "English" }].map((item) => <button key={item.value} type="button" className={`rounded-md px-3 py-2 text-sm ${language === item.value ? "bg-background shadow-sm" : "text-muted-foreground"}`} onClick={() => i18n.changeLanguage(item.value)}>{item.label}</button>)}</div></div>
              <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.themeTitle")}</span><div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">{[{ value: "light", label: t("common.light") }, { value: "dark", label: t("common.dark") }].map((item) => <button key={item.value} type="button" className={`rounded-md px-3 py-2 text-sm ${theme === item.value ? "bg-background shadow-sm" : "text-muted-foreground"}`} onClick={() => setTheme(item.value as "light" | "dark")}>{item.label}</button>)}</div></div>
              <div className="rounded-lg border border-border p-3"><div className="text-sm font-medium">{t("settings.guideTitle")}</div><p className="mt-1 text-xs text-muted-foreground">{t("settings.guideHint")}</p><Button variant="outline" size="sm" className="mt-3" onClick={() => window.dispatchEvent(new Event("autolaya:onboarding"))}><Compass /> {t("settings.showGuide")}</Button></div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
