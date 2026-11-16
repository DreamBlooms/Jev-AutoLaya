import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { DropdownMenu } from "radix-ui";
import { toast } from "sonner";

import { apiErrorMessage, createSample, deleteSample, importSamples, listSamples, sampleTemplateUrl } from "@/api/client";
import { StatusTag } from "@/components/StatusTag";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/format";

function parseObject(value: string, message: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(message);
  return parsed as Record<string, unknown>;
}

export function SamplesPanel({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState('{\n  "ticket": "I need a refund for this invoice."\n}');
  const [labels, setLabels] = useState('{\n  "team": "billing"\n}');
  const [language, setLanguage] = useState("en");
  const [difficulty, setDifficulty] = useState("medium");
  const [heldout, setHeldout] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const samples = useQuery({ queryKey: ["samples", projectId], queryFn: () => listSamples({ projectId }) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["samples", projectId] });
    queryClient.invalidateQueries({ queryKey: ["samples"] });
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };
  const importer = useMutation({
    mutationFn: (file: File) => importSamples(projectId, file),
    onSuccess: (result) => {
      toast.success(t("samples.imported", { count: result.imported }));
      invalidate();
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("samples.importFailed"))),
  });
  const create = useMutation({
    mutationFn: () => createSample(projectId, {
      state: parseObject(state, t("samples.invalidJson")),
      labels: parseObject(labels || "{}", t("samples.invalidJson")),
      meta: heldout ? { heldout: true } : undefined,
      language,
      difficulty,
    }),
    onSuccess: (sample) => { toast.success(t("common.saved")); invalidate(); setOpen(false); navigate(`/review?sample=${sample.id}`); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const remove = useMutation({ mutationFn: deleteSample, onSuccess: () => { toast.success(t("samples.sampleDeleted")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))) });

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div><CardTitle>{t("samples.title")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("samples.subtitle")}</p></div>
        <div className="flex flex-wrap justify-end gap-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button size="sm" variant="outline"><Download /> {t("samples.downloadTemplate")} <ChevronDown /></Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-40 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg">
                <DropdownMenu.Item asChild>
                  <a href={sampleTemplateUrl(projectId, "jsonl")} download className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm outline-none hover:bg-accent focus:bg-accent">{t("samples.templateJsonl")}</a>
                </DropdownMenu.Item>
                <DropdownMenu.Item asChild>
                  <a href={sampleTemplateUrl(projectId, "csv")} download className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm outline-none hover:bg-accent focus:bg-accent">{t("samples.templateCsv")}</a>
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          <Button size="sm" variant="outline" disabled={importer.isPending} onClick={() => fileInput.current?.click()}>
            <Upload /> {t("samples.upload")}
          </Button>
          <Button size="sm" onClick={() => setOpen(true)}><Plus /> {t("samples.addSample")}</Button>
          <input
            ref={fileInput}
            type="file"
            accept=".jsonl,.ndjson,.csv"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) importer.mutate(file);
            }}
          />
        </div>
      </CardHeader>
      <CardContent>
        {samples.data?.length ? (
          <Table>
            <TableHeader><TableRow><TableHead>{t("common.state")}</TableHead><TableHead>{t("common.status")}</TableHead><TableHead>{t("common.answer")}</TableHead><TableHead>{t("common.source")}</TableHead><TableHead>{t("common.language")}</TableHead><TableHead>{t("common.createdAt")}</TableHead><TableHead className="w-36" /></TableRow></TableHeader>
            <TableBody>
              {samples.data.map((sample) => {
                const preview = Object.values(sample.state).find((value) => typeof value === "string");
                return (
                  <TableRow key={sample.id}>
                    <TableCell className="max-w-md"><p className="line-clamp-2 text-sm">{preview ? String(preview) : JSON.stringify(sample.state)}</p></TableCell>
                    <TableCell><StatusTag status={sample.status} /></TableCell>
                    <TableCell><Badge variant="muted">{sample.annotationCount}</Badge></TableCell>
                    <TableCell><Badge variant="secondary">{sample.source}</Badge></TableCell>
                    <TableCell className="text-xs text-muted-foreground">{sample.language.toUpperCase()}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDate(sample.createdAt, i18n.language)}</TableCell>
                    <TableCell><div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => navigate(`/review?sample=${sample.id}`)}><Pencil /> {t("common.edit")}</Button><Button size="icon" variant="ghost" className="text-destructive" onClick={() => remove.mutate(sample.id)}><Trash2 /></Button></div></TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : <Empty title={t("samples.noSamples")} action={<Button onClick={() => setOpen(true)}><Plus /> {t("samples.addSample")}</Button>} />}
      </CardContent>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{t("samples.createTitle")}</DialogTitle></DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2"><Label>{t("samples.stateJson")}</Label><Textarea className="mono min-h-40 text-xs" value={state} onChange={(event) => setState(event.target.value)} /></div>
            <div className="grid gap-2"><Label>{t("samples.labelsJson")}</Label><Textarea className="mono min-h-28 text-xs" value={labels} onChange={(event) => setLabels(event.target.value)} /></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2"><Label>{t("common.language")}</Label><Select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="zh">简体中文</option></Select></div>
              <div className="grid gap-2"><Label>{t("review.difficulty")}</Label><Select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></Select></div>
            </div>
            <label className="flex items-center justify-between rounded-lg border border-border p-3 text-sm"><span><span className="font-medium">{t("samples.heldout")}</span><span className="mt-1 block text-xs text-muted-foreground">{t("samples.heldoutHint")}</span></span><Switch checked={heldout} onCheckedChange={setHeldout} /></label>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button><Button disabled={create.isPending} onClick={() => create.mutate()}>{t("common.create")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
