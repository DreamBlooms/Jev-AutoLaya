import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";

export function StatusTag({ status }: { status: string }) {
  const { t } = useTranslation();
  const variant = status === "accepted" ? "success" : status === "rejected" ? "destructive" : status === "paused" ? "warning" : "warning";
  const label = status === "accepted" ? t("common.accepted") : status === "rejected" ? t("common.rejected") : status === "paused" ? t("common.paused") : t("common.pending");
  return <Badge variant={variant}>{label}</Badge>;
}

export function JobStatusTag({ status }: { status: string }) {
  const { t } = useTranslation();
  const variant = status === "completed" ? "success" : status === "failed" ? "destructive" : status === "cancelled" ? "muted" : status === "paused" ? "warning" : "info";
  return <Badge variant={variant}>{status === "paused" ? t("common.paused") : status}</Badge>;
}
