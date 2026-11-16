import { Boxes, CheckSquare2, Database, FlaskConical, FolderKanban, Languages, Menu, Moon, Settings, Sun, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Onboarding } from "@/components/Onboarding";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";

const nav = [
  { key: "projects", href: "/", icon: FolderKanban },
  { key: "review", href: "/review", icon: CheckSquare2 },
  { key: "playground", href: "/playground", icon: FlaskConical },
  { key: "datasets", href: "/datasets", icon: Database },
  { key: "models", href: "/models", icon: Boxes },
  { key: "settings", href: "/settings", icon: Settings },
] as const;

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const language = i18n.language.startsWith("zh") ? "zh" : "en";
  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <Link to="/" onClick={onNavigate} className="relative block overflow-hidden px-5 pb-5 pt-6">
        <BrandMark className="pointer-events-none absolute -right-6 -top-8 size-24 text-sidebar-foreground/[0.028]" />
        <span className="relative z-10 block">
          <span className="block text-[17px] font-semibold leading-tight tracking-tight">{t("app.name")}</span>
          <span className="mt-1 block text-[11px] leading-relaxed text-sidebar-foreground/55">{t("app.tagline")}</span>
        </span>
      </Link>
      <nav className="flex-1 space-y-1 px-3">
        {nav.map((item) => {
          const active = item.href === "/" ? location.pathname === "/" || location.pathname.startsWith("/projects/") : location.pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              to={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/72 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active &&
                  "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm ring-1 ring-inset ring-sidebar-border dark:ring-white/15",
              )}
            >
              <Icon className={cn("size-4", active && "text-sidebar-primary dark:text-white")} />
              {t(`nav.${item.key}`)}
            </Link>
          );
        })}
      </nav>
      <div className="px-3 pb-5">
        <div className="rounded-xl border border-sidebar-border/80 bg-sidebar-accent/50 p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-sidebar-foreground/65">
            <Languages className="size-3.5" />
            {t("common.language")}
          </div>
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-sidebar p-1">
            {[{ value: "zh", label: "中文" }, { value: "en", label: "EN" }].map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => i18n.changeLanguage(item.value)}
                className={cn(
                  "rounded-md px-2 py-1.5 text-xs font-medium text-sidebar-foreground/60 transition-colors",
                  language === item.value &&
                    "bg-sidebar-accent text-sidebar-accent-foreground ring-1 ring-inset ring-sidebar-border/80 dark:ring-white/15",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const theme = useAppStore((state) => state.theme);
  const toggleTheme = useAppStore((state) => state.toggleTheme);
  const selected = nav.find((item) => (item.href === "/" ? location.pathname === "/" || location.pathname.startsWith("/projects/") : location.pathname.startsWith(item.href)))?.key ?? "projects";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-sidebar-border lg:block">
        <Sidebar />
      </aside>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button type="button" aria-label="Close menu" className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="relative h-full w-64 shadow-2xl">
            <button type="button" className="absolute right-3 top-3 z-10 rounded-md p-2 text-sidebar-foreground/70 hover:bg-sidebar-accent" onClick={() => setMobileOpen(false)}>
              <X className="size-4" />
            </button>
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/80 bg-background/80 px-4 backdrop-blur-xl sm:px-7">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)}>
              <Menu className="size-5" />
            </Button>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">AutoLaya</div>
              <div className="text-sm font-semibold">{t(`nav.${selected}`)}</div>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
        </header>
        <main className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-7 sm:py-8">
          <Outlet />
        </main>
      </div>
      <Onboarding />
    </div>
  );
}
