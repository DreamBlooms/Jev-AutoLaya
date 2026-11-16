import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckSquare2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { getProject } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DatasetsPanel } from "@/pages/project/DatasetsPanel";
import { EvaluationPanel } from "@/pages/project/EvaluationPanel";
import { GeneratePanel } from "@/pages/project/GeneratePanel";
import { SamplesPanel } from "@/pages/project/SamplesPanel";
import { SchemaPanel } from "@/pages/project/SchemaPanel";
import { SeedsPanel } from "@/pages/project/SeedsPanel";
import { TrainingPanel } from "@/pages/project/TrainingPanel";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId), enabled: Boolean(projectId) });

  if (project.isLoading) {
    return <Card><CardContent className="space-y-4 pt-5"><Skeleton className="h-8 w-64" /><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }
  if (project.isError || !project.data) {
    return <Empty title={t("common.notFound")} action={<Button variant="outline" onClick={() => navigate("/")}><ArrowLeft /> {t("common.back")}</Button>} />;
  }
  const data = project.data;
  const stats = [
    [t("common.questionCount"), data.questionCount],
    [t("common.seedCount"), data.seedCount],
    [t("common.sampleCount"), data.sampleCount],
    [t("common.pendingCount"), data.pendingCount],
    [t("common.snapshotCount"), data.snapshotCount],
  ];

  return (
    <div>
      <Button variant="ghost" size="sm" className="-ml-2 mb-2 text-muted-foreground" onClick={() => navigate("/")}>
        <ArrowLeft /> {t("projects.title")}
      </Button>
      <PageHeader
        title={data.name}
        subtitle={data.domain || t("project.overview")}
        extra={
          <div className="flex flex-wrap items-center gap-2">
            {data.languages.map((language) => <Badge key={language} variant="secondary">{language.toUpperCase()}</Badge>)}
            <Button onClick={() => navigate("/review")}>
              <CheckSquare2 /> {t("nav.review")} ({data.pendingCount})
            </Button>
          </div>
        }
      />
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {stats.map(([label, value]) => (
          <Card key={String(label)} className="py-3"><CardContent><div className="text-2xl font-semibold">{value}</div><div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div></CardContent></Card>
        ))}
      </div>

      <Tabs defaultValue="schema">
        <TabsList className="h-auto flex-wrap justify-start bg-transparent p-0">
          {[
            ["schema", "schema"], ["seeds", "seeds"], ["generate", "generate"], ["samples", "samples"],
            ["datasets", "datasets"], ["training", "training"], ["evaluation", "evaluation"],
          ].map(([value, label]) => (
            <TabsTrigger key={value} value={value} className="rounded-lg border border-transparent px-3 py-2 data-[state=active]:border-border">
              {t(`project.tabs.${label}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="schema"><SchemaPanel projectId={projectId} /></TabsContent>
        <TabsContent value="seeds"><SeedsPanel projectId={projectId} /></TabsContent>
        <TabsContent value="generate"><GeneratePanel projectId={projectId} languages={data.languages} /></TabsContent>
        <TabsContent value="samples"><SamplesPanel projectId={projectId} /></TabsContent>
        <TabsContent value="datasets"><DatasetsPanel projectId={projectId} /></TabsContent>
        <TabsContent value="training"><TrainingPanel projectId={projectId} /></TabsContent>
        <TabsContent value="evaluation"><EvaluationPanel projectId={projectId} /></TabsContent>
      </Tabs>
    </div>
  );
}
