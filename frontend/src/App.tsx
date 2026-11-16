import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";

import { Layout } from "@/components/Layout";
import { DatasetsPage } from "@/pages/DatasetsPage";
import { ModelsPage } from "@/pages/ModelsPage";
import { PlaygroundPage } from "@/pages/PlaygroundPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { ReviewPage } from "@/pages/ReviewPage";
import { SettingsPage } from "@/pages/SettingsPage";

function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="text-center">
        <div className="text-5xl font-black text-muted-foreground/40">404</div>
        <p className="mt-2 text-sm text-muted-foreground">{t("common.notFound")}</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/playground" element={<PlaygroundPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <Toaster richColors closeButton />
    </>
  );
}
