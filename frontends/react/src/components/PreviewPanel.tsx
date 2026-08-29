import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { InteractiveLineChart, type ChartSeries } from "@/components/chart/InteractiveLineChart";
import { getPreview } from "@/lib/api";
import type { PreviewPayload } from "@/lib/types";

type Tab = "plan" | "profile" | "bruckner";

/** Fetches GET /designs/{id}/preview once the job is done and renders the
 * plan axis+edges, TN/projet profile, and Bruckner curve as independent,
 * interactive (pan/zoom + hover) charts. Kept in its own component so it
 * can be developed/tested independently of the form and job-status panel. */
export function PreviewPanel({ jobId }: { jobId: string | null }) {
  const [data, setData] = useState<PreviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("profile");

  useEffect(() => {
    if (!jobId) {
      setData(null);
      return;
    }
    let cancelled = false;
    getPreview(jobId)
      .then((payload) => { if (!cancelled) setData(payload); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : String(err)); });
    return () => { cancelled = true; };
  }, [jobId]);

  if (!jobId) return null;

  if (error) {
    return (
      <Card>
        <CardContent className="text-sm text-accent">Aperçu indisponible : {error}</CardContent>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card>
        <CardContent className="text-sm text-muted">Chargement de l'aperçu…</CardContent>
      </Card>
    );
  }

  const profileSeries: ChartSeries[] = [
    { name: "TN", color: "#2f9e44", points: data.profile.pk.map((pk, i) => [pk, data.profile.tn[i]] as [number, number]) },
    { name: "Projet", color: "#d92727", points: data.profile.pk.map((pk, i) => [pk, data.profile.projet[i]] as [number, number]) },
  ];
  const bruckerSeries: ChartSeries[] = [
    {
      name: "M(PK)",
      color: "#7048e8",
      points: data.bruckner.pk.map((pk, i) => [pk, data.bruckner.m[i]] as [number, number]),
      fillBaseline: 0,
    },
  ];
  const planSeries: ChartSeries[] = [
    { name: "Axe", color: "#202a3a", points: data.plan.axis as [number, number][] },
    { name: "Bord gauche", color: "#8f9bb3", points: data.plan.edges_left as [number, number][] },
    { name: "Bord droit", color: "#8f9bb3", points: data.plan.edges_right as [number, number][] },
  ];

  const tabs: { id: Tab; label: string }[] = [
    { id: "profile", label: "Profil en long" },
    { id: "bruckner", label: "Bruckner" },
    { id: "plan", label: "Tracé en plan" },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Aperçu interactif</CardTitle>
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold ${
                tab === t.id ? "bg-navy text-white" : "text-navy hover:bg-navy/5"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {tab === "profile" && (
          <InteractiveLineChart series={profileSeries} xLabel="PK (m)" yLabel="Cote (m)" />
        )}
        {tab === "bruckner" && (
          <InteractiveLineChart series={bruckerSeries} xLabel="PK (m)" yLabel="M(PK) [m³]" />
        )}
        {tab === "plan" && (
          <InteractiveLineChart series={planSeries} xLabel="X" yLabel="Y" aspectLock />
        )}
      </CardContent>
    </Card>
  );
}
