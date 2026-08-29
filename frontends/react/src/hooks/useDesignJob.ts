import { useCallback, useEffect, useRef, useState } from "react";
import { getDesignStatus } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

/** Polls GET /designs/{id} every 2s until the job reaches done/error. */
export function useDesignJob() {
  const [job, setJob] = useState<JobStatus | null>(null);
  const timerRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      setJob({ job_id: jobId, status: "queued", files: null, warnings: null, error: null });

      timerRef.current = window.setInterval(async () => {
        try {
          const status = await getDesignStatus(jobId);
          setJob(status);
          if (status.status === "done" || status.status === "error") {
            stopPolling();
          }
        } catch (err) {
          stopPolling();
          setJob((prev) =>
            prev
              ? { ...prev, status: "error", error: err instanceof Error ? err.message : String(err) }
              : prev
          );
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling]
  );

  useEffect(() => stopPolling, [stopPolling]);

  return { job, startPolling, stopPolling };
}
