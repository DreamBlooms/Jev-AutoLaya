import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, FlaskConical, Loader2, PlayCircle, Plus, Terminal, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, getConfig, listArtifacts, listProjects, listQuestions, runPlayground } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatPercent } from "@/lib/format";
import type { ModelArtifact, PlaygroundQuestionInput, PlaygroundResult, Question, QuestionType } from "@/types/api";

const TRAINED_KINDS: Record<string, string> = {
  "laya-fit": "calibration",
  "laya-finetuned": "checkpoint",
  "gliner-finetuned": "gliner_checkpoint",
};

const DEFAULT_STATE = JSON.stringify({
  ticket: "I was charged twice this month, please refund the duplicate.",
}, null, 2);

type PresetKind = "" | "noul" | "choice" | "score" | "mixed";
type QuestionSource = "project" | "custom";

interface DraftOption { key: string; description: string }
interface DraftQuestion { id: string; key: string; type: QuestionType; instructions: string; options: DraftOption[]; scoreLabels: string; noulTrue: string; noulFalse: string }

function uid() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function newQuestion(type: QuestionType = "choice"): DraftQuestion {
  return { id: uid(), key: "", type, instructions: "", options: type === "choice" ? [{ key: "", description: "" }] : [], scoreLabels: "", noulTrue: "", noulFalse: "" };
}

function toDraft(question: Question): DraftQuestion {
  return {
    id: uid(),
    key: question.key,
    type: question.type,
    instructions: question.instructions,
    options: question.type === "choice" && question.criteria && !Array.isArray(question.criteria)
      ? Object.entries(question.criteria).map(([key, description]) => ({ key, description }))
      : [],
    scoreLabels: question.type === "score" && Array.isArray(question.criteria) ? question.criteria.join(", ") : "",
    noulTrue: question.type === "noul" && question.criteria && !Array.isArray(question.criteria) ? String(question.criteria.true ?? "") : "",
    noulFalse: question.type === "noul" && question.criteria && !Array.isArray(question.criteria) ? String(question.criteria.false ?? "") : "",
  };
}

function typeVariant(type: string) {
  return type === "noul" ? "success" : type === "score" ? "purple" : "info";
}

function percent(value: unknown) {
  return typeof value === "number" ? formatPercent(value) : "—";
}

function answerValue(question: PlaygroundQuestionInput, answer: Record<string, unknown> | undefined) {
  if (!answer) return "—";
  if (question.type === "choice") return String(answer.choice ?? "—");
  if (question.type === "noul") return percent(answer.noul);
  const score = answer.score;
  if (question.type === "score" && typeof score === "number" && Array.isArray(question.criteria)) {
    return `${Math.round(score * 100) / 100} · ${question.criteria[score] ?? "—"}`;
  }
  return score === undefined ? "—" : String(score);
}

export function PlaygroundPage() {
  const { t, i18n } = useTranslation();
  const [projectId, setProjectId] = useState("");
  const [model, setModel] = useState("laya-base");
  const [artifactId, setArtifactId] = useState("");
  const [stateJson, setStateJson] = useState(DEFAULT_STATE);
  const [drafts, setDrafts] = useState<DraftQuestion[]>([]);
  const [questionSource, setQuestionSource] = useState<QuestionSource>("project");
  const [presetKind, setPresetKind] = useState<PresetKind>("");
  const [presetLanguage, setPresetLanguage] = useState<"zh" | "en">(i18n.language.startsWith("zh") ? "zh" : "en");
  const [resultQuestions, setResultQuestions] = useState<PlaygroundQuestionInput[]>([]);
  const [requestModel, setRequestModel] = useState("{{MODEL}}");
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8100");
  const [curlText, setCurlText] = useState("");
  const loadedProject = useRef<string | null>(null);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const config = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const questions = useQuery({
    queryKey: ["questions", projectId],
    queryFn: () => listQuestions(projectId),
    enabled: Boolean(projectId),
  });
  const artifacts = useQuery({
    queryKey: ["artifacts", projectId],
    queryFn: () => listArtifacts(projectId),
    enabled: Boolean(projectId),
  });

  useEffect(() => {
    if (!projectId && projects.data?.length) setProjectId(projects.data[0].id);
  }, [projectId, projects.data]);

  useEffect(() => {
    if (!projectId) {
      setQuestionSource("custom");
      loadedProject.current = null;
      return;
    }
    if (questionSource === "project" && questions.data && loadedProject.current !== projectId) {
      setDrafts(questions.data.map(toDraft));
      setPresetKind("");
      loadedProject.current = projectId;
    }
  }, [projectId, questionSource, questions.data]);

  const trainedKind = TRAINED_KINDS[model];
  const modelArtifacts = trainedKind
    ? (artifacts.data ?? []).filter((item) => item.kind === trainedKind).sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
    : [];
  const hasFit = (artifacts.data ?? []).some((item) => item.kind === "calibration");
  const hasLayaCheckpoint = (artifacts.data ?? []).some((item) => item.kind === "checkpoint");
  const hasGlinerCheckpoint = (artifacts.data ?? []).some((item) => item.kind === "gliner_checkpoint");
  const selectedRuntimeReady = model.startsWith("gliner") ? config.data?.glinerRuntimeReady : config.data?.layaRuntimeReady;
  const modelSource = (() => {
    if (trainedKind) return artifactId ? modelArtifacts.find((item) => item.id === artifactId)?.path ?? "—" : modelArtifacts[0]?.path ?? t("playground.noArtifact");
    if (model === "laya-multi-base") return config.data?.layaModels?.multilingual ?? "—";
    if (model === "laya-base") return config.data?.layaModels?.default ?? "—";
    if (model === "gliner-multi-base") return config.data?.glinerModels?.multilingual ?? "—";
    return config.data?.glinerModels?.english ?? "—";
  })();

  const presetText = (language: "zh" | "en") => i18n.getFixedT(language);

  const presetDrafts = (kind: Exclude<PresetKind, "">, language = presetLanguage): DraftQuestion[] => {
    const pt = presetText(language);
    if (kind === "noul") {
      return [{
        ...newQuestion("noul"),
        key: "is_sandwich",
        instructions: pt("playground.presets.sandwich.question"),
        noulTrue: pt("playground.presets.sandwich.true"),
        noulFalse: pt("playground.presets.sandwich.false"),
      }];
    }
    if (kind === "choice") {
      return [{
        ...newQuestion("choice"),
        key: "sky_color",
        instructions: pt("playground.presets.sky.question"),
        options: [
          { key: "blue", description: pt("playground.presets.sky.blue") },
          { key: "gray", description: pt("playground.presets.sky.gray") },
          { key: "red", description: pt("playground.presets.sky.red") },
          { key: "green", description: pt("playground.presets.sky.green") },
        ],
      }];
    }
    if (kind === "score") {
      return [{
        ...newQuestion("score"),
        key: "urgency",
        instructions: pt("playground.presets.urgency.question"),
        options: [],
        scoreLabels: [pt("playground.presets.urgency.low"), pt("playground.presets.urgency.medium"), pt("playground.presets.urgency.high")].join(", "),
      }];
    }
    return [
      {
        ...newQuestion("noul"),
        key: "is_billing",
        instructions: pt("playground.presets.mixedExample.noul.question"),
        noulTrue: pt("playground.presets.mixedExample.noul.true"),
        noulFalse: pt("playground.presets.mixedExample.noul.false"),
      },
      {
        ...newQuestion("choice"),
        key: "team",
        instructions: pt("playground.presets.mixedExample.choice.question"),
        options: [
          { key: "billing", description: pt("playground.presets.mixedExample.choice.billing") },
          { key: "technical", description: pt("playground.presets.mixedExample.choice.technical") },
          { key: "sales", description: pt("playground.presets.mixedExample.choice.sales") },
        ],
      },
      {
        ...newQuestion("score"),
        key: "priority",
        instructions: pt("playground.presets.mixedExample.score.question"),
        options: [],
        scoreLabels: [
          pt("playground.presets.mixedExample.score.low"),
          pt("playground.presets.mixedExample.score.medium"),
          pt("playground.presets.mixedExample.score.high"),
        ].join(", "),
      },
    ];
  };

  const presetState = (kind: Exclude<PresetKind, "">, language = presetLanguage) => {
    const pt = presetText(language);
    if (kind === "mixed") return pt("playground.presets.mixedExample.state");
    const key = kind === "noul" ? "sandwich" : kind === "choice" ? "sky" : "urgency";
    return pt(`playground.presets.${key}.state`);
  };

  const applyPreset = (kind: PresetKind, language = presetLanguage) => {
    setPresetKind(kind);
    setQuestionSource("custom");
    loadedProject.current = null;
    if (kind) {
      setDrafts(presetDrafts(kind, language));
      run.reset();
      setResultQuestions([]);
    }
  };

  const loadProjectSchema = () => {
    setQuestionSource("project");
    loadedProject.current = null;
  };

  const markCustom = () => {
    setQuestionSource("custom");
    run.reset();
  };

  const updateQuestion = (id: string, patch: Partial<DraftQuestion>) => {
    setDrafts((current) => current.map((question) => question.id === id ? { ...question, ...patch } : question));
    markCustom();
  };

  const updateOption = (id: string, index: number, patch: Partial<DraftOption>) => {
    setDrafts((current) => current.map((question) => {
      if (question.id !== id) return question;
      const options = [...question.options];
      options[index] = { ...options[index], ...patch };
      return { ...question, options };
    }));
    markCustom();
  };

  const buildQuestions = (): PlaygroundQuestionInput[] | null => {
    if (!drafts.length) {
      toast.error(t("playground.noQuestions"));
      return null;
    }
    const seen = new Set<string>();
    const payload: PlaygroundQuestionInput[] = [];
    for (const question of drafts) {
      const key = question.key.trim();
      if (!key) {
        toast.error(t("playground.invalidQuestion"));
        return null;
      }
      if (seen.has(key)) {
        toast.error(t("playground.duplicateKey"));
        return null;
      }
      seen.add(key);
      if (question.type === "choice") {
        const criteria = Object.fromEntries(question.options.map((option) => [option.key.trim(), option.description.trim()]).filter(([optionKey]) => optionKey));
        if (!Object.keys(criteria).length) {
          toast.error(t("playground.missingOptions"));
          return null;
        }
        payload.push({ key, type: "choice", instructions: question.instructions.trim(), criteria });
      } else if (question.type === "score") {
        const labels = question.scoreLabels.split(",").map((label) => label.trim()).filter(Boolean);
        if (!labels.length) {
          toast.error(t("playground.missingScoreLabels"));
          return null;
        }
        payload.push({ key, type: "score", instructions: question.instructions.trim(), criteria: labels });
      } else {
        const criteria: Record<string, string> = {};
        if (question.noulTrue.trim()) criteria.true = question.noulTrue.trim();
        if (question.noulFalse.trim()) criteria.false = question.noulFalse.trim();
        payload.push({ key, type: "noul", instructions: question.instructions.trim(), criteria: Object.keys(criteria).length ? criteria : null });
      }
    }
    return payload;
  };

  const run = useMutation({
    mutationFn: (request: { state: unknown; questions: PlaygroundQuestionInput[] }) => runPlayground({
      projectId: projectId || undefined,
      model,
      state: request.state,
      questions: request.questions,
      artifactId: trainedKind ? artifactId || undefined : undefined,
      device: config.data?.devicePreference ?? "auto",
    }),
    onSuccess: (_, request) => setResultQuestions(request.questions),
    onError: (error) => toast.error(apiErrorMessage(error, t("playground.failed"))),
  });

  const parseState = () => {
    try {
      const parsed: unknown = JSON.parse(stateJson);
      if (parsed === null || parsed === "" || !["string", "object"].includes(typeof parsed)) throw new Error("invalid");
      return parsed;
    } catch {
      toast.error(t("playground.invalidJson"));
      return undefined;
    }
  };

  const systemOneBody = (state: unknown, questions: PlaygroundQuestionInput[]) => {
    const body: Record<string, unknown> = {
      model: requestModel.trim() || "{{MODEL}}",
      state,
      questions: Object.fromEntries(questions.map((question) => [
        question.key,
        {
          type: question.type,
          instructions: question.instructions,
          ...(question.criteria !== null ? { criteria: question.criteria } : {}),
        },
      ])),
    };
    return body;
  };

  const execute = () => {
    const state = parseState();
    if (state === undefined) return;
    const payload = buildQuestions();
    if (!payload) return;
    run.mutate({ state, questions: payload });
  };

  const generateCurl = () => {
    const state = parseState();
    if (state === undefined) return;
    const payload = buildQuestions();
    if (!payload) return;
    const body = systemOneBody(state, payload);
    const json = JSON.stringify(body, null, 2).replace(/'/g, "'\''");
    const base = (baseUrl.trim() || "{{BASE_URL}}").replace(/\/+$/, "");
    const endpoint = base.endsWith("/v1/systemone") ? base : `${base}/v1/systemone`;
    setCurlText(`curl -X POST '${endpoint}' \\\n  -H 'Content-Type: application/json' \\\n  -d '${json}'`);
  };

  const copyCurl = async () => {
    if (!curlText) return;
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(curlText);
      } else {
        throw new Error("clipboard unavailable");
      }
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = curlText;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    toast.success(t("playground.copied"));
  };

  const result = run.data as PlaygroundResult | undefined;
  const info = (result?.modelInfo ?? {}) as { role?: string; target?: string; source?: string; artifact?: ModelArtifact };
  const roleLabel = info.role === "fit" ? t("evaluate.roleFit") : info.role === "finetuned" ? t("evaluate.roleFinetuned") : t("evaluate.roleBase");
  const roleVariant = info.role === "fit" ? "warning" : info.role === "finetuned" ? "success" : "secondary";
  const selectedModelLabel = model === "laya-fit" ? t("evaluate.layaFit") : model === "laya-finetuned" ? t("evaluate.layaFinetuned") : model === "laya-multi-base" ? t("evaluate.layaMultiBase") : model === "laya-base" ? t("evaluate.layaBase") : model === "gliner-finetuned" ? t("evaluate.glinerFinetuned") : model === "gliner-multi-base" ? t("evaluate.glinerMultiBase") : t("evaluate.glinerBase");

  return (
    <div>
      <PageHeader title={t("playground.title")} subtitle={t("playground.subtitle")} />
      <div className="grid gap-5">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><FlaskConical className="size-4" /> {t("playground.modelConfig")}</CardTitle><p className="text-xs text-muted-foreground">{t("playground.hint")}</p></CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="grid gap-2"><Label>{t("common.project")}</Label><Select value={projectId} onChange={(event) => { const next = event.target.value; setProjectId(next); setArtifactId(""); loadedProject.current = null; run.reset(); setResultQuestions([]); if (!next) { setQuestionSource("custom"); if (TRAINED_KINDS[model]) setModel("laya-base"); } }}><option value="">{t("playground.noProject")}</option>{projects.data?.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select></div>
              <div className="grid gap-2"><Label>{t("playground.model")}</Label><Select value={model} onChange={(event) => { setModel(event.target.value); setArtifactId(""); run.reset(); setResultQuestions([]); }}>
                <optgroup label={t("playground.baseModels")}>
                  <option value="laya-base" disabled={!config.data?.layaRuntimeReady}>{t("evaluate.layaBase")}</option>
                  <option value="laya-multi-base" disabled={!config.data?.layaRuntimeReady}>{t("evaluate.layaMultiBase")}</option>
                  <option value="gliner-base" disabled={!config.data?.glinerRuntimeReady}>{t("evaluate.glinerBase")}</option>
                  <option value="gliner-multi-base" disabled={!config.data?.glinerRuntimeReady}>{t("evaluate.glinerMultiBase")}</option>
                </optgroup>
                <optgroup label={t("playground.trainedModels")}>
                  <option value="laya-fit" disabled={!projectId || !hasFit || !config.data?.layaRuntimeReady}>{t("evaluate.layaFit")}</option>
                  <option value="laya-finetuned" disabled={!projectId || !hasLayaCheckpoint || !config.data?.layaRuntimeReady}>{t("evaluate.layaFinetuned")}</option>
                  <option value="gliner-finetuned" disabled={!projectId || !hasGlinerCheckpoint || !config.data?.glinerRuntimeReady}>{t("evaluate.glinerFinetuned")}</option>
                </optgroup>
              </Select></div>
              <div className="grid gap-2"><Label>{t("playground.version")}</Label><Select value={artifactId} disabled={!trainedKind} onChange={(event) => { setArtifactId(event.target.value); run.reset(); setResultQuestions([]); }}><option value="">{t("playground.latest")}</option>{modelArtifacts.map((artifact) => <option key={artifact.id} value={artifact.id}>{artifact.name} · {formatDate(artifact.createdAt, i18n.language)}</option>)}</Select></div>
            </div>
            <div className="grid min-w-0 gap-2"><Label>{t("playground.source")}</Label><div className="flex h-9 min-w-0 items-center overflow-hidden rounded-lg border border-border bg-muted/25 px-3"><span className="min-w-0 flex-1 truncate font-mono text-xs" title={modelSource}>{modelSource}</span></div></div>
          </CardContent>
        </Card>

        <div className="grid items-stretch gap-5 xl:grid-cols-2">
          <Card className="flex flex-col">
            <CardHeader><CardTitle>{t("playground.input")}</CardTitle></CardHeader>
            <CardContent className="flex flex-1 flex-col gap-4">
              <div className="flex flex-1 flex-col gap-2"><Label>{t("playground.stateJson")}</Label><Textarea className="mono min-h-72 flex-1 resize-y text-xs" value={stateJson} onChange={(event) => setStateJson(event.target.value)} /></div>
              {!selectedRuntimeReady ? <Alert variant="warning"><AlertTitle>{t("playground.runtimeMissing")}</AlertTitle></Alert> : null}
              <div className="mt-auto flex flex-wrap items-center gap-3"><Button disabled={!drafts.length || !selectedRuntimeReady || (Boolean(trainedKind) && !projectId) || run.isPending} onClick={execute}>{run.isPending ? <Loader2 className="animate-spin" /> : <PlayCircle />}{run.isPending ? t("playground.running") : t("playground.run")}</Button><span className="text-xs text-muted-foreground">{t("playground.loadHint")}</span></div>
              {run.error ? <Alert variant="destructive"><AlertTitle>{t("playground.failed")}</AlertTitle><AlertDescription className="whitespace-pre-wrap">{apiErrorMessage(run.error, t("playground.failed"))}</AlertDescription></Alert> : null}
            </CardContent>
          </Card>

          <Card className="flex flex-col">
            <CardHeader><CardTitle>{t("playground.schema")}</CardTitle><p className="text-xs text-muted-foreground">{t("playground.schemaHint")}</p></CardHeader>
            <CardContent className="flex flex-1 flex-col gap-4">
              <div className="grid gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" variant={questionSource === "project" ? "default" : "outline"} disabled={!projectId} onClick={loadProjectSchema}>{t("playground.fromProject")}</Button>
                  <Button size="sm" variant={questionSource === "custom" ? "default" : "outline"} onClick={() => setQuestionSource("custom")}>{t("playground.customQuestions")}</Button>
                  <Button size="sm" variant="outline" className="ml-auto" disabled={!presetKind} onClick={() => { if (presetKind) setStateJson(JSON.stringify({ text: presetState(presetKind) }, null, 2)); }}>{t("playground.loadPresetState")}</Button>
                </div>
                <div className="grid items-end gap-2 sm:grid-cols-2">
                  <div className="grid gap-2"><Label>{t("playground.presetLabel")}</Label><Select value={presetLanguage} onChange={(event) => { const language = event.target.value as "zh" | "en"; setPresetLanguage(language); if (presetKind) applyPreset(presetKind, language); }}>
                    <option value="zh">简体中文</option>
                    <option value="en">English</option>
                  </Select></div>
                  <div className="grid gap-2"><Label>{t("playground.presetQuestion")}</Label><Select value={presetKind} onChange={(event) => applyPreset(event.target.value as PresetKind)}>
                    <option value="">{t("playground.presets.custom")}</option>
                    <option value="noul">{t("playground.presets.noul")}</option>
                    <option value="choice">{t("playground.presets.choice")}</option>
                    <option value="score">{t("playground.presets.score")}</option>
                    <option value="mixed">{t("playground.presets.mixed")}</option>
                  </Select></div>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{t("playground.questionsHint")}</p>
              <div className="flex flex-1 flex-col gap-3">
                {drafts.map((question) => (
                  <div key={question.id} className="grid gap-3 rounded-lg border border-border p-3">
                    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_130px_36px]">
                      <Input value={question.key} placeholder={t("schema.questionKey")} onChange={(event) => updateQuestion(question.id, { key: event.target.value })} />
                      <Select value={question.type} onChange={(event) => { const type = event.target.value as QuestionType; updateQuestion(question.id, { type, options: type === "choice" ? [{ key: "", description: "" }] : [], scoreLabels: "", noulTrue: "", noulFalse: "" }); }}><option value="choice">Choice</option><option value="noul">Noul</option><option value="score">Score</option></Select>
                      <Button size="icon" variant="ghost" className="text-destructive" onClick={() => { setDrafts((current) => current.filter((item) => item.id !== question.id)); markCustom(); }}><Trash2 /></Button>
                    </div>
                    <Input value={question.instructions} placeholder={t("common.instructions")} onChange={(event) => updateQuestion(question.id, { instructions: event.target.value })} />
                    <div className="flex flex-wrap items-center gap-2"><Badge variant={typeVariant(question.type)}>{question.type}</Badge><code className="mono text-[10px] text-muted-foreground">{question.key || "—"}</code></div>
                    {question.type === "choice" ? (
                      <div className="grid gap-2">
                        <div className="text-xs font-medium text-muted-foreground">{t("schema.choiceOptions")}</div>
                        {question.options.map((option, index) => (
                          <div key={index} className="flex gap-2">
                            <Input className="w-36" value={option.key} placeholder={t("schema.optionKey")} onChange={(event) => updateOption(question.id, index, { key: event.target.value })} />
                            <Input value={option.description} placeholder={t("schema.optionDescription")} onChange={(event) => updateOption(question.id, index, { description: event.target.value })} />
                            <Button size="icon" variant="ghost" onClick={() => { setDrafts((current) => current.map((item) => item.id === question.id ? { ...item, options: item.options.filter((_, optionIndex) => optionIndex !== index) } : item)); markCustom(); }}><Trash2 /></Button>
                          </div>
                        ))}
                        <Button size="sm" variant="outline" onClick={() => { setDrafts((current) => current.map((item) => item.id === question.id ? { ...item, options: [...item.options, { key: "", description: "" }] } : item)); markCustom(); }}><Plus /> {t("schema.addOption")}</Button>
                      </div>
                    ) : null}
                    {question.type === "score" ? <div className="grid gap-2"><Label>{t("schema.scoreLabels")}</Label><Input value={question.scoreLabels} onChange={(event) => updateQuestion(question.id, { scoreLabels: event.target.value })} /><p className="text-xs text-muted-foreground">{t("schema.scoreLabelsHint")}</p></div> : null}
                    {question.type === "noul" ? <div className="grid gap-2"><div className="grid gap-2 sm:grid-cols-2"><Input value={question.noulTrue} placeholder={t("playground.noulTrue")} onChange={(event) => updateQuestion(question.id, { noulTrue: event.target.value })} /><Input value={question.noulFalse} placeholder={t("playground.noulFalse")} onChange={(event) => updateQuestion(question.id, { noulFalse: event.target.value })} /></div><p className="text-xs text-muted-foreground">{t("schema.noulHint")}</p></div> : null}
                  </div>
                ))}
              </div>
              <Button size="sm" variant="outline" className="mt-auto self-start" onClick={() => { setDrafts((current) => [...current, newQuestion()]); markCustom(); }}><Plus /> {t("schema.addQuestion")}</Button>
            </CardContent>
          </Card>
        </div>


        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2"><CardTitle>{t("playground.result")}</CardTitle>{result ? <Badge variant={roleVariant}>{roleLabel}</Badge> : null}{result ? <Badge variant="outline">{info.target === "gliner" ? "GLiNER2.5" : "Laya"}</Badge> : null}{result?.latencyMs !== null && result?.latencyMs !== undefined ? <Badge variant="muted">{t("playground.latency")}: {Math.round(result.latencyMs)} ms</Badge> : null}</div>
            {result ? <div className="grid min-w-0 gap-1"><p className="truncate font-mono text-xs text-muted-foreground" title={info.source ?? modelSource}>{selectedModelLabel} · {info.source ?? modelSource}</p>{info.artifact ? <p className="truncate text-xs text-muted-foreground">{info.artifact.name} · {formatDate(info.artifact.createdAt, i18n.language)}</p> : null}</div> : <p className="text-xs text-muted-foreground">{t("playground.empty")}</p>}
          </CardHeader>
          <CardContent>
            {result ? (
              <div className="grid gap-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {resultQuestions.map((question) => {
                    const answer = result.answers[question.key];
                    return (
                      <div key={question.key} className="rounded-lg border border-border bg-muted/15 p-3">
                        <div className="flex flex-wrap items-center gap-2"><code className="mono rounded bg-muted px-1.5 py-0.5 text-xs">{question.key}</code><Badge variant={typeVariant(question.type)}>{question.type}</Badge></div>
                        <div className="mt-3 text-lg font-semibold">{answerValue(question, answer)}</div>
                        {answer ? <div className="mt-2 flex flex-wrap gap-1"><Badge variant="muted">{t("playground.confidence")}: {percent(answer.confidence)}</Badge>{answer.probabilities && typeof answer.probabilities === "object" ? Object.entries(answer.probabilities as Record<string, unknown>).map(([key, value]) => <Badge key={key} variant="secondary">{key}: {percent(value)}</Badge>) : null}</div> : <p className="mt-2 text-xs text-muted-foreground">{t("playground.missing")}</p>}
                      </div>
                    );
                  })}
                </div>
                <details className="rounded-lg border border-border bg-muted/15 p-3">
                  <summary className="cursor-pointer text-xs font-medium">{t("playground.raw")}</summary>
                  <pre className="mono mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-[11px]">{JSON.stringify(result, null, 2)}</pre>
                </details>
              </div>
            ) : <Empty title={t("playground.empty")} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Terminal className="size-4" /> {t("playground.curlTitle")}</CardTitle><p className="text-xs text-muted-foreground">{t("playground.curlHint")}</p></CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2"><Label>{t("playground.baseUrl")}</Label><Input className="mono text-xs" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="{{BASE_URL}}" /><p className="text-xs text-muted-foreground">{t("playground.baseUrlHint")}</p></div>
              <div className="grid gap-2"><Label>{t("playground.requestModel")}</Label><Input className="mono text-xs" value={requestModel} onChange={(event) => setRequestModel(event.target.value)} placeholder="{{MODEL}}" /><p className="text-xs text-muted-foreground">{t("playground.requestModelHint")}</p></div>
            </div>
            <div className="flex flex-wrap gap-2"><Button onClick={generateCurl}><Terminal /> {t("playground.generateCurl")}</Button><Button variant="outline" disabled={!curlText} onClick={copyCurl}><Copy /> {t("playground.copyCurl")}</Button></div>
            {curlText ? <pre className="mono max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/25 p-3 text-[11px]">{curlText}</pre> : <p className="text-xs text-muted-foreground">{t("playground.curlEmpty")}</p>}
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
