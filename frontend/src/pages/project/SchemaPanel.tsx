import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { apiErrorMessage, createQuestion, deleteQuestion, listQuestions, updateQuestion } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { Question, QuestionType } from "@/types/api";

interface OptionDraft { key: string; description: string }
interface QuestionDraft { key: string; type: QuestionType; instructions: string; options: OptionDraft[]; scoreLabels: string }

const emptyDraft: QuestionDraft = { key: "", type: "choice", instructions: "", options: [{ key: "", description: "" }], scoreLabels: "" };

function typeLabel(type: string, t: (key: string) => string) {
  return type === "choice" ? t("schema.typeChoice") : type === "noul" ? t("schema.typeNoul") : t("schema.typeScore");
}

export function SchemaPanel({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Question | null>(null);
  const [draft, setDraft] = useState<QuestionDraft>(emptyDraft);
  const questions = useQuery({ queryKey: ["questions", projectId], queryFn: () => listQuestions(projectId) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["questions", projectId] });
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const save = useMutation({
    mutationFn: () => {
      const criteria = draft.type === "choice"
        ? Object.fromEntries(draft.options.map((item) => [item.key.trim(), item.description.trim()]))
        : draft.type === "score"
          ? draft.scoreLabels.split(",").map((item) => item.trim()).filter(Boolean)
          : null;
      const payload = { key: draft.key.trim(), type: draft.type, instructions: draft.instructions.trim(), criteria };
      return editing ? updateQuestion(projectId, editing.id, payload) : createQuestion(projectId, payload);
    },
    onSuccess: () => {
      toast.success(editing ? t("schema.questionUpdated") : t("schema.questionCreated"));
      setOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteQuestion(projectId, id),
    onSuccess: () => { toast.success(t("schema.questionDeleted")); invalidate(); },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))),
  });

  const openCreate = () => { setEditing(null); setDraft(emptyDraft); setOpen(true); };
  const openEdit = (question: Question) => {
    setEditing(question);
    setDraft({
      key: question.key,
      type: question.type,
      instructions: question.instructions,
      options: question.type === "choice" && question.criteria && !Array.isArray(question.criteria)
        ? Object.entries(question.criteria).map(([key, description]) => ({ key, description }))
        : [{ key: "", description: "" }],
      scoreLabels: question.type === "score" && Array.isArray(question.criteria) ? question.criteria.join(", ") : "",
    });
    setOpen(true);
  };

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div><CardTitle>{t("schema.title")}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{t("schema.subtitle")}</p></div>
        <Button size="sm" onClick={openCreate}><Plus /> {t("schema.addQuestion")}</Button>
      </CardHeader>
      <CardContent>
        {questions.data?.length ? (
          <Table>
            <TableHeader><TableRow><TableHead>{t("common.key")}</TableHead><TableHead>{t("common.type")}</TableHead><TableHead>{t("common.instructions")}</TableHead><TableHead>{t("common.criteria")}</TableHead><TableHead className="w-24" /></TableRow></TableHeader>
            <TableBody>
              {questions.data.map((question) => (
                <TableRow key={question.id}>
                  <TableCell><code className="mono rounded bg-muted px-1.5 py-0.5 text-xs">{question.key}</code></TableCell>
                  <TableCell><Badge variant={question.type === "choice" ? "info" : question.type === "noul" ? "success" : "purple"}>{typeLabel(question.type, t)}</Badge></TableCell>
                  <TableCell className="max-w-md text-muted-foreground">{question.instructions || "—"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {(Array.isArray(question.criteria) ? question.criteria : Object.keys(question.criteria ?? {})).map((item) => <Badge key={item} variant="muted">{item}</Badge>)}
                      {!question.criteria ? "—" : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(question)}><Pencil /></Button>
                      <Button variant="ghost" size="icon" className="text-destructive" onClick={() => { if (window.confirm(t("schema.deleteConfirm"))) remove.mutate(question.id); }}><Trash2 /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : <Empty title={t("schema.noQuestions")} action={<Button onClick={openCreate}><Plus /> {t("schema.addQuestion")}</Button>} />}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>{editing ? t("schema.editQuestion") : t("schema.addQuestion")}</DialogTitle></DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
              <div className="grid gap-2"><Label>{t("schema.questionKey")}</Label><Input value={draft.key} onChange={(event) => setDraft({ ...draft, key: event.target.value })} placeholder="team" /></div>
              <div className="grid gap-2"><Label>{t("schema.questionType")}</Label><Select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value as QuestionType })}><option value="choice">Choice</option><option value="noul">Noul</option><option value="score">Score</option></Select></div>
            </div>
            <div className="grid gap-2"><Label>{t("common.instructions")}</Label><Textarea value={draft.instructions} onChange={(event) => setDraft({ ...draft, instructions: event.target.value })} placeholder={t("schema.instructionsPlaceholder")} /></div>
            {draft.type === "choice" ? (
              <div className="grid gap-2">
                <Label>{t("schema.choiceOptions")}</Label>
                {draft.options.map((option, index) => (
                  <div key={index} className="flex gap-2">
                    <Input className="w-40" value={option.key} placeholder={t("schema.optionKey")} onChange={(event) => { const options = [...draft.options]; options[index] = { ...option, key: event.target.value }; setDraft({ ...draft, options }); }} />
                    <Input value={option.description} placeholder={t("schema.optionDescription")} onChange={(event) => { const options = [...draft.options]; options[index] = { ...option, description: event.target.value }; setDraft({ ...draft, options }); }} />
                    <Button variant="ghost" size="icon" onClick={() => setDraft({ ...draft, options: draft.options.filter((_, i) => i !== index) })}><Trash2 /></Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={() => setDraft({ ...draft, options: [...draft.options, { key: "", description: "" }] })}><Plus /> {t("schema.addOption")}</Button>
              </div>
            ) : null}
            {draft.type === "score" ? <div className="grid gap-2"><Label>{t("schema.scoreLabels")}</Label><Input value={draft.scoreLabels} onChange={(event) => setDraft({ ...draft, scoreLabels: event.target.value })} placeholder="can wait, this week, today" /><p className="text-xs text-muted-foreground">{t("schema.scoreLabelsHint")}</p></div> : null}
            {draft.type === "noul" ? <p className="text-xs text-muted-foreground">{t("schema.noulHint")}</p> : null}
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button><Button disabled={!draft.key.trim() || save.isPending} onClick={() => save.mutate()}>{t("common.save")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
