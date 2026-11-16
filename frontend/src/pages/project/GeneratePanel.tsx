import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Code2, Loader2, PauseCircle, PlayCircle, SlidersHorizontal, StopCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  apiErrorMessage,
  cancelGenerationJob,
  getConfig,
  getGenerationPromptDefaults,
  listGenerationJobs,
  pauseGenerationJob,
  previewGeneration,
  resumeGenerationJob,
  startGeneration,
} from "@/api/client";
import {
  DISTRIBUTION_DOT_CLASS,
  DISTRIBUTION_KEYS,
  DistributionSlider,
  rebalanceDistribution,
} from "@/components/DistributionSlider";
import type { Distribution } from "@/components/DistributionSlider";
import { JobStatusTag } from "@/components/StatusTag";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useJobEvents } from "@/hooks/useJobEvents";
import { formatDate } from "@/lib/format";
import type { GenerationJob, GenerationPayload } from "@/types/api";

export function GeneratePanel({ projectId, languages: projectLanguages }: { projectId: string; languages: string[] }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [count, setCount] = useState(50);
  const [languages, setLanguages] = useState<string[]>(projectLanguages.length ? projectLanguages : ["en"]);
  const [teacher, setTeacher] = useState("llm");
  const [difficulty, setDifficulty] = useState<Distribution>({ easy: 50, medium: 35, hard: 15 });
  const [negativeRatio, setNegativeRatio] = useState(0.1);
  const [labelBalanced, setLabelBalanced] = useState(true);
  const [customPrompt, setCustomPrompt] = useState("");
  const [customTemplateEnabled, setCustomTemplateEnabled] = useState(false);
  const [systemPromptTemplate, setSystemPromptTemplate] = useState("");
  const [userPromptTemplate, setUserPromptTemplate] = useState("");
  const [thinkBudget, setThinkBudget] = useState("");
  const [thinkLevel, setThinkLevel] = useState("");
  const [temperature, setTemperature] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<GenerationJob | null>(null);

  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const promptDefaults = useQuery({
    queryKey: ["generation-prompt-defaults", projectId],
    queryFn: () => getGenerationPromptDefaults(projectId),
  });
  const jobs = useQuery({
    queryKey: ["generation-jobs", projectId],
    queryFn: () => listGenerationJobs(projectId),
    refetchInterval: (query) => query.state.data?.some((job) => ["pending", "running"].includes(job.status)) ? 4000 : false,
  });

  useEffect(() => {
    if (!config.data) return;
    setTeacher(config.data.jevConfigured ? "jev" : config.data.llmConfigured ? "llm" : "none");
  }, [config.data]);

  useEffect(() => {
    if (!customTemplateEnabled || !promptDefaults.data) return;
    setSystemPromptTemplate((current) => current || promptDefaults.data.system);
    setUserPromptTemplate((current) => current || promptDefaults.data.user);
  }, [customTemplateEnabled, promptDefaults.data]);

  useEffect(() => {
    if (activeId && jobs.data) setActiveJob(jobs.data.find((job) => job.id === activeId) ?? activeJob);
  }, [activeId, jobs.data, activeJob]);

  useJobEvents<GenerationJob>(activeId ? `/api/v1/generation-jobs/${activeId}/events` : null, (job) => {
    setActiveJob(job);
    if (["completed", "failed", "cancelled"].includes(job.status)) {
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", projectId] });
      queryClient.invalidateQueries({ queryKey: ["samples", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      if (job.status === "completed") toast.success(t("generate.completed"));
    }
  });

  const buildPayload = (): GenerationPayload => {
    const total = difficulty.easy + difficulty.medium + difficulty.hard || 1;
    const payload: GenerationPayload = {
      count,
      languages,
      teacher,
      difficulty: { easy: difficulty.easy / total, medium: difficulty.medium / total, hard: difficulty.hard / total },
      negativeRatio,
      labelBalanced,
    };
    if (customPrompt.trim()) payload.customPrompt = customPrompt.trim();
    if (customTemplateEnabled && systemPromptTemplate.trim()) payload.systemPromptTemplate = systemPromptTemplate;
    if (customTemplateEnabled && userPromptTemplate.trim()) payload.userPromptTemplate = userPromptTemplate;
    const llm: NonNullable<GenerationPayload["llm"]> = {};
    if (temperature.trim() !== "") llm.temperature = Number(temperature);
    if (thinkBudget.trim() !== "") llm.thinkBudget = Math.round(Number(thinkBudget));
    if (thinkLevel !== "") llm.thinkLevel = thinkLevel;
    if (Object.keys(llm).length) payload.llm = llm;
    return payload;
  };

  const start = useMutation({
    mutationFn: () => startGeneration(projectId, buildPayload()),
    onSuccess: (job) => { setActiveId(job.id); setActiveJob(job); queryClient.invalidateQueries({ queryKey: ["generation-jobs", projectId] }); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const preview = useMutation({
    mutationFn: () => previewGeneration(projectId, buildPayload()),
    onError: (error) => toast.error(apiErrorMessage(error, t("generate.previewFailed"))),
  });
  const pause = useMutation({ mutationFn: pauseGenerationJob, onSuccess: setActiveJob, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const resume = useMutation({ mutationFn: resumeGenerationJob, onSuccess: setActiveJob, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const cancel = useMutation({ mutationFn: cancelGenerationJob, onSuccess: setActiveJob, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });

  const toggleLanguage = (language: string, checked: boolean) => setLanguages((current) => checked ? [...new Set([...current, language])] : current.filter((item) => item !== language));
  const difficultyLabels = {
    easy: t("generate.easy"),
    medium: t("generate.medium"),
    hard: t("generate.hard"),
  };

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader><CardTitle>{t("generate.title")}</CardTitle><p className="text-xs text-muted-foreground">{t("generate.subtitle")}</p></CardHeader>
        <CardContent className="grid gap-4">
          {!config.data?.llmConfigured ? <Alert variant="warning"><AlertTitle>{t("generate.llmMissing")}</AlertTitle></Alert> : null}
          {!config.data?.jevConfigured ? <Alert variant="info"><AlertTitle>{t("generate.jevMissing")}</AlertTitle></Alert> : null}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="grid gap-2"><Label>{t("generate.count")}</Label><Input type="number" min={1} max={2000} value={count} onChange={(event) => setCount(Number(event.target.value))} /></div>
            <div className="grid gap-2 md:col-span-2"><Label>{t("generate.languages")}</Label><div className="flex gap-2">{[{ value: "zh", label: "简体中文" }, { value: "en", label: "English" }].map((item) => <label key={item.value} className="flex flex-1 items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm"><Checkbox checked={languages.includes(item.value)} onCheckedChange={(value) => toggleLanguage(item.value, value === true)} />{item.label}</label>)}</div></div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid content-start gap-2"><Label>{t("generate.teacher")}</Label><Select value={teacher} onChange={(event) => setTeacher(event.target.value)}><option value="jev" disabled={!config.data?.jevConfigured}>{t("generate.teacherJev")}</option><option value="llm" disabled={!config.data?.llmConfigured}>{t("generate.teacherLlm")}</option><option value="none">{t("generate.teacherNone")}</option></Select></div>
            <div className="grid content-start gap-2"><Label>{t("generate.negativeRatio")}</Label><Input type="number" min={0} max={1} step={0.05} value={negativeRatio} onChange={(event) => setNegativeRatio(Number(event.target.value))} /></div>
          </div>
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2"><Label>{t("generate.difficulty")} (%)</Label><span className="text-xs text-muted-foreground">{t("generate.percentHint")}</span></div>
            <DistributionSlider values={difficulty} labels={difficultyLabels} onChange={setDifficulty} />
            <div className="grid grid-cols-3 gap-2">
              {DISTRIBUTION_KEYS.map((key) => (
                <div key={key} className="grid gap-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground"><span className={`size-2 rounded-full ${DISTRIBUTION_DOT_CLASS[key]}`} />{difficultyLabels[key]} (%)</div>
                  <div className="relative">
                    <Input aria-label={`${difficultyLabels[key]} (%)`} type="number" min={0} max={100} value={difficulty[key]} onChange={(event) => setDifficulty((current) => rebalanceDistribution(current, key, Number(event.target.value)))} className="pr-7" />
                    <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <label className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"><span>{t("generate.labelBalanced")}</span><Switch checked={labelBalanced} onCheckedChange={setLabelBalanced} /></label>
          {teacher === "llm" ? <Alert variant="info"><AlertTitle>{t("generate.llmLabelHint")}</AlertTitle></Alert> : null}
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={!config.data?.llmConfigured || start.isPending} onClick={() => start.mutate()}><PlayCircle /> {t("generate.start")}</Button>
            <span className="text-xs text-muted-foreground">{t("generate.runningHint")}</span>
            <Button type="button" size="sm" variant="outline" className="ml-auto" aria-expanded={showAdvanced} onClick={() => setShowAdvanced((value) => !value)}><SlidersHorizontal /> {t("generate.advanced")}</Button>
          </div>
          {showAdvanced ? (
            <div className="grid gap-4 rounded-xl border border-border p-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="grid gap-2"><Label>{t("generate.thinkBudget")}</Label><Input type="number" min={0} max={32768} value={thinkBudget} onChange={(event) => setThinkBudget(event.target.value)} placeholder={t("generate.defaultValue")} /><p className="text-xs text-muted-foreground">{t("generate.thinkBudgetHint")}</p></div>
                <div className="grid gap-2"><Label>{t("generate.thinkLevel")}</Label><Select value={thinkLevel} onChange={(event) => setThinkLevel(event.target.value)}><option value="">{t("generate.defaultValue")}</option><option value="minimal">minimal</option><option value="low">low</option><option value="medium">medium</option><option value="high">high</option></Select><p className="text-xs text-muted-foreground">{t("generate.thinkLevelHint")}</p></div>
                <div className="grid gap-2"><Label>{t("generate.temperatureSetting")}</Label><Input type="number" min={0} max={2} step={0.1} value={temperature} onChange={(event) => setTemperature(event.target.value)} placeholder={t("generate.defaultValue")} /><p className="text-xs text-muted-foreground">{t("generate.temperatureHint")}</p></div>
              </div>
              <div className="grid gap-2"><Label>{t("generate.customPrompt")}</Label><Textarea className="min-h-32 text-xs" value={customPrompt} onChange={(event) => setCustomPrompt(event.target.value)} placeholder={t("generate.customPromptPlaceholder")} /><p className="text-xs text-muted-foreground">{t("generate.customPromptHint")}</p></div>
              <label className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm"><span><span className="font-medium">{t("generate.customTemplateToggle")}</span><span className="mt-1 block text-xs text-muted-foreground">{t("generate.customTemplateHint")}</span></span><Switch checked={customTemplateEnabled} onCheckedChange={setCustomTemplateEnabled} /></label>
              {customTemplateEnabled ? (
                <div className="grid gap-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="grid gap-2"><Label>{t("generate.systemPromptTemplate")}</Label><Textarea className="mono min-h-40 text-xs" value={systemPromptTemplate} onChange={(event) => setSystemPromptTemplate(event.target.value)} placeholder={t("generate.systemPromptPlaceholder")} /></div>
                    <div className="grid gap-2"><Label>{t("generate.userPromptTemplate")}</Label><Textarea className="mono min-h-40 text-xs" value={userPromptTemplate} onChange={(event) => setUserPromptTemplate(event.target.value)} placeholder={t("generate.userPromptPlaceholder")} /></div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="grid gap-2">
                      <div className="text-xs font-medium">{t("generate.promptPlaceholders")}</div>
                      <div className="flex flex-wrap gap-1">{(promptDefaults.data?.placeholders ?? []).map((name) => <code key={name} className="mono rounded bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">{`{{${name}}}`}</code>)}</div>
                    </div>
                    <Button type="button" size="sm" variant="outline" disabled={!promptDefaults.data} onClick={() => { if (promptDefaults.data) { setSystemPromptTemplate(promptDefaults.data.system); setUserPromptTemplate(promptDefaults.data.user); } }}>{t("generate.restoreDefaultTemplates")}</Button>
                  </div>
                  <p className="text-xs text-muted-foreground">{t("generate.promptTemplateHint")}</p>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-3"><Button type="button" size="sm" variant="outline" disabled={preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? <Loader2 className="animate-spin" /> : <Code2 />}{t("generate.previewRequest")}</Button><span className="text-xs text-muted-foreground">{t("generate.previewHint")}</span></div>
              {preview.data ? <div className="grid gap-2 rounded-lg border border-border bg-muted/15 p-3"><div className="flex flex-wrap gap-2 text-xs"><Badge variant="info">{preview.data.model}</Badge><Badge variant="secondary">{preview.data.endpoint}</Badge><Badge variant="muted">{preview.data.language} · {preview.data.batchSize}</Badge></div><pre className="mono max-h-96 overflow-auto whitespace-pre-wrap text-[11px]">{JSON.stringify(preview.data.body, null, 2)}</pre></div> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {activeJob ? (
        <Card>
          <CardHeader className="flex-row items-start justify-between">
            <div><CardTitle className="flex items-center gap-2">{t("generate.progress")} <JobStatusTag status={activeJob.status} /></CardTitle><p className="mt-1 text-xs text-muted-foreground">{activeJob.stage}</p></div>
            {!["completed", "failed", "cancelled"].includes(activeJob.status) ? (
              <div className="flex gap-2">
                {activeJob.status === "paused" ? <Button size="sm" onClick={() => resume.mutate(activeJob.id)}><PlayCircle /> {t("generate.resume")}</Button> : <Button size="sm" variant="outline" onClick={() => pause.mutate(activeJob.id)}><PauseCircle /> {t("generate.pause")}</Button>}
                <Button size="sm" variant="destructive" onClick={() => cancel.mutate(activeJob.id)}><StopCircle /> {t("generate.cancel")}</Button>
              </div>
            ) : null}
          </CardHeader>
          <CardContent className="grid gap-4">
            <Progress value={activeJob.progress} />
            <div className="grid grid-cols-4 gap-2 text-center">
              {[[t("generate.generated"), activeJob.generatedCount], [t("generate.accepted"), activeJob.acceptedCount], [t("generate.rejected"), activeJob.rejectedCount], [t("generate.count"), activeJob.targetCount]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-muted/40 p-3"><div className="text-xl font-semibold">{value}</div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div></div>)}
            </div>
            {activeJob.error ? <Alert variant="warning"><AlertTitle>{activeJob.error}</AlertTitle></Alert> : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader><CardTitle>{t("common.job")}</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>{t("common.createdAt")}</TableHead><TableHead>{t("common.status")}</TableHead><TableHead>{t("common.progress")}</TableHead><TableHead>{t("generate.accepted")}</TableHead><TableHead>{t("generate.rejected")}</TableHead><TableHead className="w-24" /></TableRow></TableHeader>
            <TableBody>
              {jobs.data?.map((job) => <TableRow key={job.id}><TableCell className="text-xs text-muted-foreground">{formatDate(job.createdAt, i18n.language)}</TableCell><TableCell><JobStatusTag status={job.status} /></TableCell><TableCell className="w-44"><Progress value={job.progress} /></TableCell><TableCell>{job.acceptedCount}</TableCell><TableCell>{job.rejectedCount}</TableCell><TableCell><Button size="sm" variant="ghost" onClick={() => setActiveId(job.id)}>{t("common.learnMore")}</Button></TableCell></TableRow>)}
            </TableBody>
          </Table>
          {!jobs.data?.length ? <p className="py-8 text-center text-sm text-muted-foreground">{t("generate.noJobs")}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
