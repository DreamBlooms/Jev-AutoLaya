import {
  ArrowRight,
  Boxes,
  Check,
  CheckSquare2,
  CircleCheckBig,
  Compass,
  Database,
  Download,
  FolderKanban,
  GraduationCap,
  ListChecks,
  MousePointerClick,
  PlayCircle,
  Plus,
  Settings,
  Sparkles,
  Timer,
  Upload,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { BrandMark } from "@/components/BrandMark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "autolaya-onboarding-v3";
const OPEN_EVENT = "autolaya:onboarding";

const STEPS = [
  { key: "intro", icon: Compass },
  { key: "schema", icon: Workflow },
  { key: "seeds", icon: Upload },
  { key: "generate", icon: Sparkles },
  { key: "review", icon: ListChecks },
  { key: "dataset", icon: Database },
  { key: "training", icon: GraduationCap },
  { key: "done", icon: CircleCheckBig },
] as const;

const MOCK_NAV = [
  { key: "projects", icon: FolderKanban },
  { key: "review", icon: CheckSquare2 },
  { key: "datasets", icon: Database },
  { key: "models", icon: Boxes },
  { key: "settings", icon: Settings },
] as const;

const PROJECT_TABS = ["schema", "seeds", "generate", "samples", "datasets", "training", "evaluation"] as const;

type StepKey = (typeof STEPS)[number]["key"];
type NavKey = (typeof MOCK_NAV)[number]["key"];
type ProjectTab = (typeof PROJECT_TABS)[number];

function Dim({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("opacity-60", className)}>{children}</div>;
}

function Focus({ children, marker, className }: { children: ReactNode; marker: string; className?: string }) {
  return (
    <div className={cn("relative z-10 rounded-lg ring-2 ring-sky-500 ring-offset-2 ring-offset-background shadow-md shadow-sky-500/15", className)}>
      {children}
      <span className="pointer-events-none absolute -right-2 -top-2 z-20 inline-flex items-center gap-1 rounded-full bg-sky-500 px-1.5 py-0.5 text-[9px] font-semibold text-white shadow-md">
        <MousePointerClick className="size-2.5" /> {marker}
      </span>
    </div>
  );
}

function MockApp({
  navKey,
  title,
  subtitle,
  tabs,
  activeTab,
  children,
}: {
  navKey: NavKey;
  title: string;
  subtitle: string;
  tabs?: boolean;
  activeTab?: ProjectTab;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex overflow-hidden rounded-xl border border-border bg-background shadow-sm">
      <aside className="hidden w-28 shrink-0 border-r border-border bg-muted/30 p-2 opacity-70 sm:block">
        <div className="px-1 text-[10px] font-semibold tracking-tight">AutoLaya</div>
        <div className="mt-2 grid gap-0.5">
          {MOCK_NAV.map((item) => {
            const Icon = item.icon;
            const active = item.key === navKey;
            return (
              <div key={item.key} className={cn("flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[9px]", active ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}>
                <Icon className="size-3" /> {t(`nav.${item.key}`)}
              </div>
            );
          })}
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2 border-b border-border p-3 opacity-80">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{title}</div>
            <div className="truncate text-[10px] text-muted-foreground">{subtitle}</div>
          </div>
          <div className="flex shrink-0 gap-1"><Badge variant="secondary">EN</Badge><Badge variant="secondary">中文</Badge></div>
        </div>
        {tabs ? (
          <div className="flex flex-wrap gap-1 border-b border-border px-3 py-2 text-[10px] opacity-80">
            {PROJECT_TABS.map((tab) => (
              <span key={tab} className={cn("rounded-md px-1.5 py-0.5", tab === activeTab ? "bg-primary text-primary-foreground" : "text-muted-foreground")}>{t(`project.tabs.${tab}`)}</span>
            ))}
          </div>
        ) : null}
        <div className="p-3">{children}</div>
      </div>
    </div>
  );
}

function IntroMock() {
  const { t } = useTranslation();
  return (
    <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-7 text-center">
      <BrandMark className="size-24 text-foreground" />
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">{t("onboarding.intro.welcome")}</h2>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">{t("onboarding.intro.desc")}</p>
      </div>
      <div className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-xs font-medium text-muted-foreground shadow-sm">
        <Timer className="size-3.5" /> {t("onboarding.intro.time")}
      </div>
    </div>
  );
}

function SchemaMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="schema">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="text-[10px] text-muted-foreground">{t("schema.subtitle")}</div>
        <Focus marker="1"><Button size="sm"><Plus /> {t("schema.addQuestion")}</Button></Focus>
      </div>
      <Dim className="mt-3 grid gap-2">
        <div className="grid gap-1 rounded-lg border border-border p-2 sm:grid-cols-[90px_70px_minmax(0,1fr)]">
          <code className="mono rounded bg-muted px-1 py-0.5 text-[10px]">team</code>
          <Badge variant="info">Choice</Badge>
          <div className="flex flex-wrap gap-1"><Badge variant="muted">billing</Badge><Badge variant="muted">technical</Badge><Badge variant="muted">sales</Badge></div>
          <p className="text-[10px] text-muted-foreground sm:col-span-3">{t("onboarding.mock.teamQuestion")}</p>
        </div>
        <div className="grid gap-1 rounded-lg border border-border p-2 sm:grid-cols-[90px_70px_minmax(0,1fr)]">
          <code className="mono rounded bg-muted px-1 py-0.5 text-[10px]">urgent</code>
          <Badge variant="success">Noul</Badge>
          <span className="text-[10px] text-muted-foreground">0 – 1</span>
          <p className="text-[10px] text-muted-foreground sm:col-span-3">{t("onboarding.mock.urgentQuestion")}</p>
        </div>
        <div className="rounded-lg border border-dashed border-border p-2 text-[10px] text-muted-foreground">{t("onboarding.mock.schemaHint")}</div>
      </Dim>
    </MockApp>
  );
}

function SeedsMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="seeds">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] text-muted-foreground">{t("seeds.subtitle")}</div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Dim className="flex items-center gap-1.5">
            <span className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-background px-2 text-[10px]"><Download className="size-3" /> {t("seeds.downloadTemplate")}</span>
            <span className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-background px-2 text-[10px]"><Upload className="size-3" /> {t("seeds.upload")}</span>
          </Dim>
          <Focus marker="1"><span className="inline-flex h-7 items-center gap-1 rounded-md bg-primary px-2 text-[10px] text-primary-foreground"><Plus className="size-3" /> {t("seeds.addSeed")}</span></Focus>
        </div>
      </div>
      <Dim className="mt-3 grid gap-2">
        <div className="rounded-lg border border-border p-3">
          <div className="text-[10px] font-medium text-muted-foreground">{t("seeds.stateJson")}</div>
          <pre className="mono mt-1 overflow-auto rounded-md bg-muted/60 p-2 text-[10px]">{`{"ticket": "${t("onboarding.mock.ticket")}"}`}</pre>
          <div className="mt-2 text-[10px] font-medium text-muted-foreground">{t("seeds.labelsJson")}</div>
          <pre className="mono mt-1 rounded-md bg-muted/60 p-2 text-[10px]">{`{"team": "billing"}`}</pre>
        </div>
      </Dim>
    </MockApp>
  );
}

function GenerateMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="generate">
      <Dim className="grid gap-2 sm:grid-cols-3">
        {[[t("generate.teacher"), t("generate.teacherJev")], [t("generate.count"), "200"], [t("generate.difficulty"), "50 · 35 · 15 (%)"]].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-border p-2"><div className="text-[9px] text-muted-foreground">{label}</div><div className="mt-1 text-[11px] font-medium">{value}</div></div>
        ))}
      </Dim>
      <Dim className="mt-2 rounded-lg border border-border p-3">
        <div className="flex items-center justify-between gap-2"><span className="text-[11px] font-semibold">{t("generate.progress")}</span><Badge variant="info">{t("common.running")}</Badge></div>
        <Progress value={72} className="mt-2" />
        <div className="mt-2 grid grid-cols-3 gap-1 text-center text-[9px]">
          {[["142", t("generate.generated")], ["126", t("generate.accepted")], ["16", t("generate.rejected")]].map(([value, label]) => <div key={label} className="rounded bg-muted/40 p-1.5"><div className="text-sm font-semibold">{value}</div><div className="text-muted-foreground">{label}</div></div>)}
        </div>
      </Dim>
      <div className="mt-2 flex justify-end"><Focus marker="1"><Button size="sm"><PlayCircle /> {t("generate.start")}</Button></Focus></div>
    </MockApp>
  );
}

function ReviewMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="review" title={t("review.title")} subtitle={t("review.subtitle")}>
      <div className="grid gap-2 sm:grid-cols-[160px_minmax(0,1fr)]">
        <div className="grid content-start gap-2">
          <Focus marker="1"><div className="rounded-lg border border-primary/40 bg-primary/5 p-2 text-[10px]"><Badge variant="secondary">EN</Badge><p className="mt-1 line-clamp-3 text-muted-foreground">{t("onboarding.mock.ticket")}</p></div></Focus>
          <Dim><div className="rounded-lg border border-border p-2 text-[10px]"><Badge variant="secondary">EN</Badge><p className="mt-1 line-clamp-2 text-muted-foreground">The API returns 500 after login.</p></div></Dim>
        </div>
        <div className="grid content-start gap-2">
          <Dim className="grid gap-2">
            <div className="rounded-lg border border-border p-2"><div className="flex items-center justify-between"><Badge variant="info">billing</Badge><span className="text-[9px] text-muted-foreground">93%</span></div><p className="mt-1 text-[10px] text-muted-foreground">{t("onboarding.mock.teamQuestion")}</p><div className="mt-1 rounded-md border border-emerald-500/40 bg-emerald-500/5 px-2 py-1 text-[11px]">billing</div></div>
            <div className="rounded-lg border border-border p-2"><div className="flex items-center justify-between"><Badge variant="secondary">urgent</Badge><span className="text-[9px] text-muted-foreground">12%</span></div><p className="mt-1 text-[10px] text-muted-foreground">{t("onboarding.mock.urgentQuestion")}</p><div className="mt-1 rounded-md border border-border bg-muted/30 px-2 py-1 text-[11px]">0.12</div></div>
          </Dim>
          <div className="flex justify-end"><Focus marker="2"><Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-600/90"><Check /> {t("review.accept")}</Button></Focus></div>
        </div>
      </div>
    </MockApp>
  );
}

function DatasetMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="datasets">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] text-muted-foreground">{t("datasets.freezeHint")}</div>
        <Focus marker="1"><Button size="sm"><Database /> {t("datasets.freeze")}</Button></Focus>
      </div>
      <Dim className="mt-3 rounded-lg border border-border p-3">
        <div className="flex items-center justify-between gap-2"><div className="text-[11px] font-semibold">{t("datasets.version")} v1</div><Badge variant="success">{t("datasets.frozen")}</Badge></div>
        <div className="mt-2 flex flex-wrap gap-1"><Badge variant="info">train: 160</Badge><Badge variant="secondary">validation: 20</Badge><Badge variant="warning">test: 20</Badge></div>
        <div className="mt-2 rounded-md border border-border p-2"><div className="text-[9px] font-medium text-muted-foreground">team</div><div className="mt-1 flex flex-wrap gap-1"><Badge variant="muted">billing: 72</Badge><Badge variant="muted">technical: 68</Badge><Badge variant="muted">sales: 40</Badge></div></div>
        <div className="mt-2 flex flex-wrap gap-1"><span className="rounded border border-border px-2 py-1 text-[9px]">Laya</span><span className="rounded border border-border px-2 py-1 text-[9px]">Canonical</span><span className="rounded border border-border px-2 py-1 text-[9px]">GLiNER</span></div>
      </Dim>
    </MockApp>
  );
}

function TrainingMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="training">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_100px_100px]">
        <div>
          <div className="mb-1 text-[9px] text-muted-foreground">{t("train.targetBase")}</div>
          <Focus marker="1"><div className="flex h-7 items-center rounded-md border border-border bg-background px-2 text-[10px]">convaiinnovations/laya-typed-decisions</div></Focus>
        </div>
        <Dim><div className="mb-1 text-[9px] text-muted-foreground">{t("train.snapshot")}</div><div className="flex h-7 items-center rounded-md border border-border px-2 text-[10px]">v1</div></Dim>
        <Dim><div className="mb-1 text-[9px] text-muted-foreground">{t("train.device")}</div><div className="flex h-7 items-center rounded-md border border-border px-2 text-[10px]">auto · ROCm</div></Dim>
      </div>
      <Dim className="mt-2 grid grid-cols-4 gap-2">
        {[[t("train.mode"), t("train.finetune")], [t("train.epochs"), "4"], [t("train.microBatch"), "8"], [t("train.gradAccum"), "8"]].map(([label, value]) => <div key={label} className="rounded-md border border-border p-2"><div className="text-[9px] text-muted-foreground">{label}</div><div className="text-[10px] font-medium">{value}</div></div>)}
      </Dim>
      <Dim className="mt-2 flex flex-wrap gap-1"><Badge variant="secondary">{t("train.freezeEncoder")}: {t("common.no")}</Badge><Badge variant="secondary">{t("train.shuffleOptions")}: {t("common.yes")}</Badge><Badge variant="info">loss: rlcd</Badge></Dim>
      <div className="mt-3 flex justify-end"><Focus marker="2"><Button size="sm"><GraduationCap /> {t("train.start")}</Button></Focus></div>
    </MockApp>
  );
}

function DoneMock() {
  const { t } = useTranslation();
  return (
    <MockApp navKey="projects" title={t("onboarding.mock.projectName")} subtitle={t("onboarding.mock.domain")} tabs activeTab="training">
      <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3 opacity-90">
        <div className="flex items-center gap-2 text-[11px] font-semibold"><CircleCheckBig className="size-4 text-emerald-600" /> {t("train.completed")}</div>
        <Progress value={100} className="mt-2" />
        <div className="mt-2 grid grid-cols-4 gap-1 text-center text-[9px]">
          {[["91%", t("evaluate.accuracy")], ["0.89", t("evaluate.macroF1")], ["100%", t("common.progress")], ["v1", t("train.snapshot")]].map(([value, label]) => <div key={label} className="rounded bg-background/80 p-1.5"><div className="text-sm font-semibold">{value}</div><div className="text-muted-foreground">{label}</div></div>)}
        </div>
      </div>
      <Dim className="mt-2 rounded-lg border border-border p-2"><div className="text-[9px] uppercase tracking-wide text-muted-foreground">{t("train.artifact")}</div><div className="mt-1 font-mono text-[10px]">Support Triage · laya · 8f3c2a1d</div></Dim>
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Dim><Button size="sm" variant="outline">{t("project.tabs.evaluation")}</Button></Dim>
        <Focus marker="1"><Button size="sm">{t("models.deploy")}</Button></Focus>
      </div>
    </MockApp>
  );
}

function MockStep({ step }: { step: StepKey }) {
  if (step === "intro") return <IntroMock />;
  if (step === "schema") return <SchemaMock />;
  if (step === "seeds") return <SeedsMock />;
  if (step === "generate") return <GenerateMock />;
  if (step === "review") return <ReviewMock />;
  if (step === "dataset") return <DatasetMock />;
  if (step === "training") return <TrainingMock />;
  return <DoneMock />;
}

export function Onboarding() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(() => !localStorage.getItem(STORAGE_KEY));
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  const finish = () => {
    localStorage.setItem(STORAGE_KEY, "done");
    setOpen(false);
  };

  useEffect(() => {
    const reopen = () => { setStep(0); setOpen(true); };
    window.addEventListener(OPEN_EVENT, reopen);
    return () => window.removeEventListener(OPEN_EVENT, reopen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) finish(); }}>
      <DialogContent className="max-w-6xl gap-0 overflow-hidden p-0">
        <DialogTitle className="sr-only">{t("onboarding.badge")}</DialogTitle>
        <div className="grid h-[82vh] max-h-[82vh] lg:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="hidden overflow-y-auto border-r border-sidebar-border bg-sidebar p-4 text-sidebar-foreground lg:block">
            <div className="px-1">
              <div className="text-[17px] font-semibold tracking-tight">{t("app.name")}</div>
              <div className="mt-1 text-[11px] leading-relaxed text-sidebar-foreground/55">{t("app.tagline")}</div>
              <div className="mt-4 text-[9px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/45">{t("onboarding.badge")}</div>
            </div>
            <div className="mt-3 grid gap-1">
              {STEPS.map((item, index) => {
                const Icon = item.icon;
                const active = index === step;
                const done = index < step;
                return (
                  <button key={item.key} type="button" onClick={() => setStep(index)} className={cn("flex items-center gap-2 rounded-lg px-2 py-2 text-left text-xs transition-colors", active ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground shadow-sm ring-1 ring-inset ring-sidebar-border dark:ring-white/15" : "text-sidebar-foreground/65 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground")}>
                    <span className={cn("grid size-6 shrink-0 place-items-center rounded-full border text-[10px]", active ? "border-sidebar-border bg-background/40 text-sidebar-primary dark:bg-white/10 dark:text-white" : done ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-500 dark:text-emerald-300" : "border-sidebar-border text-sidebar-foreground/55")}>{done ? <Check className="size-3" /> : <Icon className="size-3" />}</span>
                    <span>{t(`onboarding.steps.${item.key}.title`)}</span>
                  </button>
                );
              })}
            </div>
            <div className="mt-5 rounded-lg border border-sidebar-border/80 bg-sidebar-accent/50 p-3 text-[9px] leading-relaxed">
              <p className="text-sidebar-foreground/45">{t("onboarding.mockNote1")}</p>
              <p className="mt-1 text-sidebar-foreground/70">{t("onboarding.mockNote2")}</p>
            </div>
          </aside>
          <section className="flex min-h-0 min-w-0 flex-col">
            {current.key === "intro" ? (
              <div className="flex items-center justify-between border-b border-border p-4 pr-12"><Badge variant="info">{t("onboarding.step", { current: step, total: STEPS.length })}</Badge><span className="text-xs text-muted-foreground lg:hidden">{t("app.name")}</span></div>
            ) : (
              <div className="border-b border-border p-5 pr-12">
                <div className="flex flex-wrap items-center gap-2"><Badge variant="info">{t("onboarding.step", { current: step, total: STEPS.length })}</Badge><span className="text-xs text-muted-foreground lg:hidden">{t(`onboarding.steps.${current.key}.title`)}</span></div>
                <h2 className="mt-2 text-xl font-semibold">{t(`onboarding.steps.${current.key}.title`)}</h2>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(`onboarding.steps.${current.key}.desc`)}</p>
              </div>
            )}
            <div className="flex-1 overflow-y-auto bg-muted/10 p-4 sm:p-5"><MockStep step={current.key} /></div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4">
              <Button variant="ghost" onClick={finish}>{t("onboarding.skip")}</Button>
              <div className="flex gap-2">
                <Button variant="outline" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>{t("onboarding.back")}</Button>
                {step === STEPS.length - 1 ? <Button className="bg-emerald-600 text-white hover:bg-emerald-600/90" onClick={finish}>{t("onboarding.finish")}</Button> : <Button onClick={() => setStep((value) => Math.min(STEPS.length - 1, value + 1))}>{t("onboarding.next")} <ArrowRight /></Button>}
              </div>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
