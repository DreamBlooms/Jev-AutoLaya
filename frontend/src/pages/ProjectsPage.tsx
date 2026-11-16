import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { apiErrorMessage, createProject, deleteProject, listProjects } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/format";

export function ProjectsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [languages, setLanguages] = useState(["zh", "en"]);

  const projects = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const create = useMutation({
    mutationFn: () => createProject({ name: name.trim(), domain, languages }),
    onSuccess: (project) => {
      toast.success(t("projects.open"));
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      setName("");
      setDomain("");
      navigate(`/projects/${project.id}`);
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.save"))),
  });
  const remove = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      toast.success(t("projects.projectDeleted"));
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => toast.error(apiErrorMessage(error, t("errors.delete"))),
  });

  const toggleLanguage = (language: string, checked: boolean) => {
    setLanguages((current) => (checked ? [...new Set([...current, language])] : current.filter((item) => item !== language)));
  };

  return (
    <div>
      <PageHeader
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
        extra={
          <Button onClick={() => setOpen(true)}>
            <Plus /> {t("projects.new")}
          </Button>
        }
      />

      {projects.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <Card key={item}><CardContent className="space-y-3"><Skeleton className="h-4 w-24" /><Skeleton className="h-7 w-3/4" /><Skeleton className="h-16 w-full" /></CardContent></Card>
          ))}
        </div>
      ) : projects.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.data.map((project) => (
            <Card key={project.id} className="group transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg">
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[11px] font-semibold tracking-wider text-muted-foreground">{project.domain || t("common.domain")}</span>
                    {project.languages.map((language) => <Badge key={language} variant="secondary">{language.toUpperCase()}</Badge>)}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => { if (window.confirm(t("projects.deleteConfirm"))) remove.mutate(project.id); }}
                  >
                    <Trash2 />
                  </Button>
                </div>
                <CardTitle className="text-xl">{project.name}</CardTitle>
                <p className="line-clamp-2 text-sm text-muted-foreground">{project.domain || t("projects.domainPlaceholder")}</p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-4 gap-2 rounded-lg border border-border/70 bg-muted/25 p-3 text-center">
                  {[
                    [t("common.questionCount"), project.questionCount],
                    [t("common.seedCount"), project.seedCount],
                    [t("common.sampleCount"), project.sampleCount],
                    [t("common.pendingCount"), project.pendingCount],
                  ].map(([label, value]) => (
                    <div key={String(label)}>
                      <div className="text-lg font-semibold">{value}</div>
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
              <div className="flex items-center justify-between border-t border-border/70 px-5 pt-4">
                <span className="text-xs text-muted-foreground">{formatDate(project.createdAt, i18n.language)}</span>
                <Button variant="ghost" size="sm" onClick={() => navigate(`/projects/${project.id}`)}>
                  <FolderOpen /> {t("projects.open")}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Empty
          title={t("projects.noProjects")}
          action={<Button onClick={() => setOpen(true)}><Plus /> {t("projects.new")}</Button>}
        />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projects.createTitle")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="project-name">{t("common.name")}</Label>
              <Input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder={t("projects.namePlaceholder")} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="project-domain">{t("common.domain")}</Label>
              <Textarea id="project-domain" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder={t("projects.domainPlaceholder")} />
            </div>
            <div className="grid gap-2">
              <Label>{t("projects.languages")}</Label>
              <div className="flex gap-3">
                {[{ value: "zh", label: "简体中文" }, { value: "en", label: "English" }].map((item) => (
                  <label key={item.value} className="flex flex-1 items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
                    <Checkbox checked={languages.includes(item.value)} onCheckedChange={(value) => toggleLanguage(item.value, value === true)} />
                    {item.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
            <Button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>{t("common.create")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
