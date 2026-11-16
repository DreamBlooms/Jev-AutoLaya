import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Compass, Info, Laptop, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, getConfig, setDevice } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppStore } from "@/store/useAppStore";

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

  return (
    <div>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} extra={<Button variant="outline" asChild><a href="/docs" target="_blank" rel="noreferrer"><Info /> {t("settings.docs")}</a></Button>} />
      <div className="grid gap-4">
        <Alert variant="info"><ShieldCheck className="size-4" /><AlertTitle>{t("settings.warning")}</AlertTitle><AlertDescription>{t("settings.phase")}</AlertDescription></Alert>
        {!data.layaRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("settings.layaSetupHint")}</AlertTitle></Alert> : null}
        {data.glinerEnabled && !data.glinerRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("settings.glinerSetupHint")}</AlertTitle></Alert> : null}

        <div className="grid gap-4 xl:grid-cols-2">
          <Card><CardHeader><CardTitle className="flex items-center gap-2"><Laptop className="size-4" /> {t("settings.runtime")}</CardTitle></CardHeader><CardContent className="grid gap-4">
            <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.device")}</span><Select value={data.devicePreference} disabled={update.isPending} onChange={(event) => update.mutate(event.target.value)}><option value="auto">auto · {data.device}</option>{data.availableDevices.map((device) => <option key={device} value={device}>{device}</option>)}</Select></div>
            <div className="flex flex-wrap gap-1">{data.availableDevices.map((device) => <Badge key={device} variant={device === data.device ? "success" : "muted"}>{device}</Badge>)}</div>
            <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.targets")}</span><div className="flex flex-wrap gap-1">{data.targets.map((target) => <Badge key={target} variant="success">{target}</Badge>)}{data.reservedTargets.map((target) => <Badge key={target} variant="muted">{target} · {t("settings.reserved")}</Badge>)}</div></div>
            <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.dataDir")}</span><code className="mono break-all rounded-md bg-muted p-2 text-xs">{data.dataDir}</code></div>
            <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.layaRuntime")}</span><div className="flex items-center gap-2"><Badge variant={data.layaRuntimeReady ? "success" : "muted"}>{data.layaRuntimeReady ? t("settings.ready") : t("settings.notReady")}</Badge><code className="mono text-xs text-muted-foreground">{data.layaVenv}</code></div></div>
            <div className="grid gap-2"><span className="text-xs font-medium text-muted-foreground">{t("settings.glinerRuntime")}</span><div className="flex items-center gap-2"><Badge variant={data.glinerRuntimeReady ? "success" : "muted"}>{data.glinerRuntimeReady ? t("settings.ready") : t("settings.notReady")}</Badge><code className="mono text-xs text-muted-foreground">{data.glinerVenv}</code></div></div>
          </CardContent></Card>

          <div className="grid gap-4">
            <Card><CardHeader><CardTitle>{t("settings.llm")}</CardTitle></CardHeader><CardContent className="grid gap-2 text-sm"><div className="flex justify-between"><span className="text-muted-foreground">{t("settings.provider")}</span><span>{data.llmProvider}</span></div><div className="flex justify-between"><span className="text-muted-foreground">{t("settings.model")}</span><code className="mono text-xs">{data.llmModel}</code></div><div className="flex justify-between"><span className="text-muted-foreground">{t("settings.configured")}</span><Badge variant={data.llmConfigured ? "success" : "muted"}>{data.llmConfigured ? t("settings.configured") : t("settings.notConfigured")}</Badge></div><span className="text-xs text-muted-foreground">{data.llmBaseUrl}</span></CardContent></Card>
            <Card><CardHeader><CardTitle>{t("settings.teacher")}</CardTitle></CardHeader><CardContent className="flex items-center justify-between text-sm"><span>{data.jevProvider}</span><Badge variant={data.jevConfigured ? "success" : "muted"}>{data.jevConfigured ? t("settings.configured") : t("settings.notConfigured")}</Badge></CardContent></Card>
            <Card><CardHeader><CardTitle>{t("settings.languageTitle")}</CardTitle></CardHeader><CardContent><div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">{[{ value: "zh", label: "简体中文" }, { value: "en", label: "English" }].map((item) => <button key={item.value} type="button" className={`rounded-md px-3 py-2 text-sm ${language === item.value ? "bg-background shadow-sm" : "text-muted-foreground"}`} onClick={() => i18n.changeLanguage(item.value)}>{item.label}</button>)}</div></CardContent></Card>
            <Card><CardHeader><CardTitle>{t("settings.themeTitle")}</CardTitle></CardHeader><CardContent><div className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">{[{ value: "light", label: t("common.light") }, { value: "dark", label: t("common.dark") }].map((item) => <button key={item.value} type="button" className={`rounded-md px-3 py-2 text-sm ${theme === item.value ? "bg-background shadow-sm" : "text-muted-foreground"}`} onClick={() => setTheme(item.value as "light" | "dark")}>{item.label}</button>)}</div></CardContent></Card>
            <Card><CardHeader><CardTitle>{t("settings.guideTitle")}</CardTitle></CardHeader><CardContent className="grid gap-3"><p className="text-sm text-muted-foreground">{t("settings.guideHint")}</p><Button variant="outline" onClick={() => window.dispatchEvent(new Event("autolaya:onboarding"))}><Compass /> {t("settings.showGuide")}</Button></CardContent></Card>
          </div>
        </div>
      </div>
    </div>
  );
}
