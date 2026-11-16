import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, RefreshCw, X } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { acceptSample, apiErrorMessage, getSample, listProjects, listSamples, reannotateSample, rejectSample, updateAnnotation } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { StateView } from "@/components/StateView";
import { StatusTag } from "@/components/StatusTag";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatPercent } from "@/lib/format";
import type { Annotation, Question, SampleDetail } from "@/types/api";

function initial(question: Question, annotation?: Annotation) {
  if (!annotation) return undefined;
  if (question.type === "choice") return annotation.answer.choice;
  if (question.type === "noul") return annotation.answer.noul;
  return annotation.answer.score;
}

function AnswerEditor({ sample, question, annotation, onSaved }: { sample: SampleDetail; question: Question; annotation?: Annotation; onSaved: () => void }) {
  const { t } = useTranslation();
  const [value, setValue] = useState<unknown>(() => initial(question, annotation));
  const [note, setNote] = useState("");
  const save = useMutation({
    mutationFn: () => updateAnnotation(sample.id, question.id, value, note || undefined),
    onSuccess: () => { toast.success(t("review.saved")); onSaved(); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const options = question.type === "choice" && question.criteria && !Array.isArray(question.criteria)
    ? Object.entries(question.criteria).map(([key, description]) => ({ value: key, label: description ? `${key} · ${description}` : key }))
    : question.type === "score" && Array.isArray(question.criteria)
      ? question.criteria.map((label, index) => ({ value: String(index), label: `${index} · ${label}` }))
      : [];

  return (
    <Card className={cn("bg-muted/15", !annotation && "border-amber-500/50")}>
      <CardHeader className="flex-row items-start justify-between">
        <CardTitle className="flex flex-wrap items-center gap-2"><code className="mono rounded bg-muted px-1.5 py-0.5 text-xs">{question.key}</code><Badge variant={question.type === "choice" ? "info" : question.type === "noul" ? "success" : "purple"}>{question.type}</Badge>{!annotation ? <Badge variant="warning">{t("common.missing")}</Badge> : null}</CardTitle>
        {annotation ? <span className="text-xs text-muted-foreground">{t("common.confidence")}: {formatPercent(annotation.confidence)}</span> : null}
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-xs text-muted-foreground">{question.instructions}</p>
        <div className="flex flex-wrap items-center gap-2">
          {question.type === "choice" ? <Select className="min-w-64" value={typeof value === "string" ? value : ""} onChange={(event) => setValue(event.target.value)}><option value="">{t("review.choicePlaceholder")}</option>{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</Select> : null}
          {question.type === "noul" ? <div className="flex items-center gap-2"><Input className="w-36" type="number" min={0} max={1} step={0.01} value={typeof value === "number" ? value : ""} onChange={(event) => setValue(Number(event.target.value))} /><span className="text-xs text-muted-foreground">{t("review.noulHint")}</span></div> : null}
          {question.type === "score" ? options.length ? <Select className="min-w-56" value={typeof value === "number" ? String(value) : ""} onChange={(event) => setValue(Number(event.target.value))}><option value="">{t("review.choicePlaceholder")}</option>{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</Select> : <div className="flex items-center gap-2"><Input className="w-32" type="number" min={0} max={100} value={typeof value === "number" ? value : ""} onChange={(event) => setValue(Number(event.target.value))} /><span className="text-xs text-muted-foreground">{t("review.scoreHint")}</span></div> : null}
          <Button size="sm" disabled={save.isPending || value === undefined || value === ""} onClick={() => save.mutate()}>{t("review.saveAnswer")}</Button>
        </div>
        {annotation?.probabilities ? <div className="flex flex-wrap gap-1"><span className="text-xs text-muted-foreground">{t("review.probabilities")}:</span>{Object.entries(annotation.probabilities).map(([key, probability]) => <Badge key={key} variant="muted">{key}: {formatPercent(probability)}</Badge>)}</div> : null}
        <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder={t("common.optional")} />
      </CardContent>
    </Card>
  );
}

export function ReviewPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("sample") ?? "";
  const [projectFilter, setProjectFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [rejectNote, setRejectNote] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const queue = useQuery({ queryKey: ["samples", "pending", projectFilter], queryFn: () => listSamples({ status: "pending", projectId: projectFilter || undefined }) });
  const sample = useQuery({ queryKey: ["sample", selectedId], queryFn: () => getSample(selectedId), enabled: Boolean(selectedId) });

  useEffect(() => {
    const pending = new Set(queue.data?.map((item) => item.id) ?? []);
    setSelectedIds((current) => current.filter((id) => pending.has(id)));
  }, [queue.data]);

  useEffect(() => {
    if (!selectedId && queue.data?.length) {
      const next = new URLSearchParams(searchParams);
      next.set("sample", queue.data[0].id);
      setSearchParams(next, { replace: true });
    }
  }, [queue.data, searchParams, selectedId, setSearchParams]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["samples"] });
    queryClient.invalidateQueries({ queryKey: ["sample", selectedId] });
    queryClient.invalidateQueries({ queryKey: ["project"] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };
  const accept = useMutation({ mutationFn: () => acceptSample(selectedId), onSuccess: () => { toast.success(t("review.accepted")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const reject = useMutation({ mutationFn: () => rejectSample(selectedId, rejectNote || undefined), onSuccess: () => { toast.success(t("review.rejected")); setRejectOpen(false); setRejectNote(""); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const reannotate = useMutation({ mutationFn: () => reannotateSample(selectedId), onSuccess: () => { toast.success(t("review.reannotated")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const batchAccept = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => acceptSample(id)));
      const failed = results.filter((item) => item.status === "rejected").length;
      return { ok: ids.length - failed, failed };
    },
    onSuccess: ({ ok, failed }) => {
      if (ok) toast.success(`${t("review.acceptSelected")}: ${ok}`);
      if (failed) toast.error(`${t("review.batchPartial")}: ${failed}`);
      setSelectedIds([]);
      invalidate();
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const batchReject = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(ids.map((id) => rejectSample(id)));
      const failed = results.filter((item) => item.status === "rejected").length;
      return { ok: ids.length - failed, failed };
    },
    onSuccess: ({ ok, failed }) => {
      if (ok) toast.success(`${t("review.rejectSelected")}: ${ok}`);
      if (failed) toast.error(`${t("review.batchPartial")}: ${failed}`);
      setSelectedIds([]);
      invalidate();
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });

  const detail = sample.data;
  const annotations = new Map(detail?.annotations.map((item) => [item.questionId, item]) ?? []);
  const projectName = (projectId: string) => projects.data?.find((project) => project.id === projectId)?.name ?? projectId.slice(0, 8);

  return (
    <div>
      <PageHeader title={t("review.title")} subtitle={t("review.subtitle")} />
      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3"><CardTitle>{t("review.queue")} · {queue.data?.length ?? 0}</CardTitle><Select className="w-36" value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}><option value="">{t("review.allProjects")}</option>{projects.data?.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select></CardHeader>
          <CardContent className="space-y-2">
            <label className="flex items-center gap-2 border-b border-border pb-2 text-xs font-medium text-muted-foreground">
              <Checkbox
                checked={Boolean(queue.data?.length) && selectedIds.length === queue.data?.length}
                onCheckedChange={(checked) => setSelectedIds(checked === true ? (queue.data?.map((item) => item.id) ?? []) : [])}
              />
              {t("review.selectAll")}
            </label>
            <div className="scrollbar-thin max-h-[calc(100vh-320px)] space-y-2 overflow-auto">
              {queue.isLoading ? <Skeleton className="h-40 w-full" /> : queue.data?.length ? queue.data.map((item) => {
                const preview = Object.values(item.state).find((value) => typeof value === "string");
                return (
                  <div key={item.id} className={cn("flex gap-2 rounded-lg border border-border p-2 transition-colors hover:bg-muted/50", selectedId === item.id && "border-primary/40 bg-primary/5")}>
                    <Checkbox className="mt-1" checked={selectedIds.includes(item.id)} onCheckedChange={(checked) => setSelectedIds((current) => checked === true ? [...new Set([...current, item.id])] : current.filter((id) => id !== item.id))} />
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => { const next = new URLSearchParams(searchParams); next.set("sample", item.id); setSearchParams(next); }}>
                      <div className="mb-1 flex flex-wrap gap-1"><Badge variant="secondary">{projectName(item.projectId)}</Badge><Badge variant="muted">{item.language.toUpperCase()}</Badge></div>
                      <p className="line-clamp-2 text-xs text-muted-foreground">{preview ? String(preview) : JSON.stringify(item.state)}</p>
                    </button>
                  </div>
                );
              }) : <Empty title={t("review.noPending")} />}
            </div>
            {selectedIds.length ? (
              <div className="flex items-center justify-between gap-3 border-t border-border pt-3">
                <span className="text-xs font-medium text-muted-foreground">{t("review.selectedCount", { count: selectedIds.length })}</span>
                <div className="flex items-center gap-1.5">
                  <Button size="sm" disabled={batchAccept.isPending} onClick={() => batchAccept.mutate(selectedIds)}><Check /> {t("review.acceptSelected")}</Button>
                  <Button size="sm" variant="destructive" disabled={batchReject.isPending} onClick={() => { if (window.confirm(t("review.batchRejectedConfirm"))) batchReject.mutate(selectedIds); }}><X /> {t("review.rejectSelected")}</Button>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div>
          {!selectedId ? <Empty title={t("review.selectSample")} /> : sample.isLoading ? <Card><CardContent className="pt-5"><Skeleton className="h-96 w-full" /></CardContent></Card> : detail ? (
            <div className="grid gap-4">
              <Card>
                <CardHeader className="flex-row items-start justify-between"><div><CardTitle className="flex flex-wrap items-center gap-2">{projectName(detail.projectId)} <StatusTag status={detail.status} /><Badge variant="secondary">{detail.source}</Badge><Badge variant="muted">{detail.language.toUpperCase()}</Badge></CardTitle><p className="mt-1 text-xs text-muted-foreground">#{detail.id.slice(0, 8)}</p></div>
                  <div className="flex gap-2"><Button variant="outline" size="sm" disabled={reannotate.isPending} onClick={() => reannotate.mutate()}><RefreshCw /> {t("review.reannotate")}</Button><Button size="sm" disabled={accept.isPending || detail.missingQuestionIds.length > 0} onClick={() => accept.mutate()}><Check /> {t("review.accept")}</Button><Button size="sm" variant="destructive" onClick={() => setRejectOpen(true)}><X /> {t("review.reject")}</Button></div>
                </CardHeader>
                <CardContent>{detail.missingQuestionIds.length ? <Alert variant="warning"><AlertTitle>{t("review.missingAnswers")}</AlertTitle><p className="text-sm">{detail.missingQuestionIds.map((id) => detail.questions.find((question) => question.id === id)?.key).filter(Boolean).join(", ")}</p></Alert> : null}</CardContent>
              </Card>
              <Card><CardHeader><CardTitle>{t("review.statePreview")}</CardTitle></CardHeader><CardContent><StateView state={detail.state} /><div className="mt-3 flex flex-wrap gap-1">{Object.entries(detail.meta).map(([key, value]) => <Badge key={key} variant="muted">{key}: {String(value)}</Badge>)}</div></CardContent></Card>
              <div className="grid gap-3">{detail.questions.map((question) => <AnswerEditor key={`${detail.id}-${question.id}-${annotations.get(question.id)?.updatedAt ?? "missing"}`} sample={detail} question={question} annotation={annotations.get(question.id)} onSaved={invalidate} />)}</div>
            </div>
          ) : <Empty title={t("errors.load")} />}
        </div>
      </div>

      {rejectOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-4 backdrop-blur-sm">
          <Card className="w-full max-w-md"><CardHeader><CardTitle>{t("review.reject")}</CardTitle></CardHeader><CardContent className="grid gap-3"><Input value={rejectNote} onChange={(event) => setRejectNote(event.target.value)} placeholder={t("review.rejectNote")} /><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setRejectOpen(false)}>{t("common.cancel")}</Button><Button variant="destructive" disabled={reject.isPending} onClick={() => reject.mutate()}>{t("review.reject")}</Button></div></CardContent></Card>
        </div>
      ) : null}
    </div>
  );
}
