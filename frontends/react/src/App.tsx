import { useState } from "react";
import { Header } from "@/components/Header";
import { MissionBand } from "@/components/MissionBand";
import { ContactFooter } from "@/components/ContactFooter";
import { SiteFooter } from "@/components/SiteFooter";
import { DesignForm, type DesignFormSubmitPayload } from "@/components/DesignForm";
import { JobStatusPanel } from "@/components/JobStatusPanel";
import { PreviewPanel } from "@/components/PreviewPanel";
import { createDesign, ApiError } from "@/lib/api";
import { useDesignJob } from "@/hooks/useDesignJob";

export default function App() {
  const { job, startPolling } = useDesignJob();
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function handleSubmit(payload: DesignFormSubmitPayload) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const { job_id } = await createDesign(payload);
      startPolling(job_id);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Échec de l'envoi du formulaire.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <Header />
      <MissionBand />

      <main className="mx-auto mt-6 max-w-6xl px-6 pb-10">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <DesignForm onSubmit={handleSubmit} submitting={submitting} />

          <div className="flex flex-col gap-6">
            {submitError && (
              <div className="rounded-md border border-accent/40 bg-accent/5 p-3 text-sm text-accent">
                {submitError}
              </div>
            )}
            <JobStatusPanel job={job} />
            {job?.status === "done" && <PreviewPanel jobId={job.job_id} />}
          </div>
        </div>
      </main>

      <ContactFooter />
      <SiteFooter />
    </div>
  );
}
