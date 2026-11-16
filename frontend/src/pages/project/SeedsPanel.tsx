import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, Plus, Send, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { DropdownMenu } from "radix-ui";
import { toast } from "sonner";

import { apiErrorMessage, deleteSeed, importSeeds, listSeeds, promoteSeed, promoteSeeds, seedTemplateUrl, uploadSeeds } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/format";

function parseObject(value: string, message: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(message);
  return parsed as Record<string, unknown>;
}

export function SeedsPanel({ projectId }: { projectId: string }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState('{\n  "ticket": "I was charged twice this month."\n}');
  const [labels, setLabels] = useState('{\n  "team": "billing"\n}');
  const [language, setLanguage] = useState("en");
  const fileInput = useRef<HTMLInputElement>(null);
  const seeds = useQuery({ queryKey: ["seeds", projectId], queryFn: () => listSeeds(projectId) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["seeds", projectId] });
    queryClient.invalidateQueries({ queryKey: ["samples", projectId] });
    queryClient.invalidateQueries({ queryKey: ["samples"] });
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const importer = useMutation({
    mutationFn: (file: File) => uploadSeeds(projectId, file),
    onSuccess: (result) => {
      toast.success(t("seeds.imported", { count: result.imported }));
      invalidate();
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("seeds.importFailed"))),
  });
  const create = useMutation({
    mutationFn: () => importSeeds(projectId, [{ state: parseObject(state, t("seeds.invalidJson")), labels: parseObject(labels || "{}", t("seeds.invalidJson")), language }]),
    onSuccess: () => { toast.success(t("common.saved")); setOpen(false); invalidate(); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const send = useMutation({ mutationFn: promoteSeed, onSuccess: () => { toast.success(t("seeds.promoted")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const sendAll = useMutation({ mutationFn: () => promoteSeeds(projectId), onSuccess: () => { toast.success(t("seeds.promotedAll")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))) });
  const remove = useMutation({ mutationFn: deleteSeed, onSuccess: () => { toast.success(t("seeds.seedDeleted")); invalidate(); }, onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))) });

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div><CardTitle>{t("seeds.title")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("seeds.subtitle")}</p></div>
        <div className="flex flex-wrap justify-end gap-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button size="sm" variant="outline"><Download /> {t("seeds.downloadTemplate")} <ChevronDown /></Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" sideOffset={4} className="z-50 min-w-40 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-lg">
                <DropdownMenu.Item asChild>
                  <a href={seedTemplateUrl(projectId, "jsonl")} download className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm outline-none hover:bg-accent focus:bg-accent">{t("seeds.templateJsonl")}</a>
                </DropdownMenu.Item>
                <DropdownMenu.Item asChild>
                  <a href={seedTemplateUrl(projectId, "csv")} download className="flex cursor-pointer items-center rounded-md px-3 py-2 text-sm outline-none hover:bg-accent focus:bg-accent">{t("seeds.templateCsv")}</a>
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          <Button size="sm" variant="outline" disabled={importer.isPending} onClick={() => fileInput.current?.click()}>
            <Upload /> {t("seeds.upload")}
          </Button>
          <Button size="sm" variant="outline" disabled={!seeds.data?.length} onClick={() => sendAll.mutate()}><Send /> {t("seeds.promoteAll")}</Button>
          <Button size="sm" onClick={() => setOpen(true)}><Plus /> {t("seeds.addSeed")}</Button>
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
        {seeds.data?.length ? (
          <Table>
            <TableHeader><TableRow><TableHead>{t("common.state")}</TableHead><TableHead>{t("common.labels")}</TableHead><TableHead>{t("common.language")}</TableHead><TableHead>{t("common.createdAt")}</TableHead><TableHead className="w-40" /></TableRow></TableHeader>
            <TableBody>
              {seeds.data.map((seed) => (
                <TableRow key={seed.id}>
                  <TableCell><pre className="mono max-h-28 max-w-md overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(seed.state, null, 2)}</pre></TableCell>
                  <TableCell><div className="flex flex-wrap gap-1">{Object.entries(seed.labels).map(([key, value]) => <Badge key={key} variant="info">{key}: {typeof value === "string" ? value : JSON.stringify(value)}</Badge>)}</div></TableCell>
                  <TableCell><Badge variant="secondary">{seed.language.toUpperCase()}</Badge></TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDate(seed.createdAt, i18n.language)}</TableCell>
                  <TableCell><div className="flex justify-end gap-1"><Button size="sm" variant="outline" onClick={() => send.mutate(seed.id)}><Send /> {t("seeds.promote")}</Button><Button size="icon" variant="ghost" className="text-destructive" onClick={() => remove.mutate(seed.id)}><Trash2 /></Button></div></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : <Empty title={t("seeds.noSeeds")} action={<Button onClick={() => setOpen(true)}><Plus /> {t("seeds.addSeed")}</Button>} />}
      </CardContent>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{t("seeds.addSeed")}</DialogTitle></DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2"><Label>{t("seeds.stateJson")}</Label><Textarea className="mono min-h-40 text-xs" value={state} onChange={(event) => setState(event.target.value)} /></div>
            <div className="grid gap-2"><Label>{t("seeds.labelsJson")}</Label><Textarea className="mono min-h-28 text-xs" value={labels} onChange={(event) => setLabels(event.target.value)} /><p className="text-xs text-muted-foreground">{t("seeds.labelsHint")}</p></div>
            <div className="grid gap-2"><Label>{t("seeds.language")}</Label><Select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="zh">简体中文</option></Select></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button><Button disabled={create.isPending} onClick={() => create.mutate()}>{t("common.import")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
