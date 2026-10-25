"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteApplication,
  listApplications,
  updateApplicationStatus,
} from "../lib/api";
import type { ApplicationListItem, ApplicationStatus } from "../lib/types";
import { Skeleton } from "@/components/control-ui/ui/skeleton";

const statuses: ApplicationStatus[] = [
  "Saved",
  "Applied",
  "Interview",
  "Rejected",
  "Selected",
];

type ApplicationTrackerProps = {
  refreshKey: number;
  onDeleted?: (id: number) => void;
};

export default function ApplicationTracker({
  refreshKey,
  onDeleted,
}: ApplicationTrackerProps) {
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const loadRequestId = useRef(0);

  const loadApplications = useCallback(async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setIsLoading(true);
    setError("");
    try {
      const rows = await listApplications();
      if (requestId !== loadRequestId.current) {
        return;
      }
      setApplications(rows);
    } catch (caughtError) {
      if (requestId !== loadRequestId.current) {
        return;
      }
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load saved applications.",
      );
    } finally {
      if (requestId === loadRequestId.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadApplications();
  }, [loadApplications, refreshKey]);

  const changeStatus = async (id: number, status: ApplicationStatus) => {
    if (mutatingId) return;
    setMessage("");
    setError("");
    setMutatingId(id);
    try {
      await updateApplicationStatus(id, status);
      setMessage("Status updated.");
      await loadApplications();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Status update failed.",
      );
    } finally {
      setMutatingId(null);
    }
  };

  const removeApplication = async (id: number) => {
    if (mutatingId) return;
    setMessage("");
    setError("");
    setMutatingId(id);
    try {
      await deleteApplication(id);
      setMessage("Application deleted.");
      onDeleted?.(id);
      if (!onDeleted) {
        await loadApplications();
      }
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Delete failed.",
      );
    } finally {
      setMutatingId(null);
    }
  };

  return (
    <section className="tracker-table-shell">
      <div className="tracker-toolbar">
        <div>
          <h4>Saved applications</h4>
          <p>Update status or remove opportunities from your local tracker.</p>
        </div>
        <button
          type="button"
          onClick={loadApplications}
          className="tracker-refresh"
          disabled={isLoading}
        >
          {isLoading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {message ? <p className="state-message success">{message}</p> : null}
      {error ? <p className="state-message error">{error}</p> : null}

      <div className="tracker-table-scroll" aria-busy={isLoading}>
        <table className="tracker-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Role</th>
              <th>Score</th>
              <th>Level</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && applications.length === 0 ? (
              <>
                <tr className="tracker-sr-only-row"><td colSpan={7} role="status">Loading saved applications…</td></tr>
                {[0, 1, 2].map((row) => (
                  <tr key={`skeleton-${row}`} className="tracker-skeleton-row" aria-hidden="true">
                    {statuses.slice(0, 2).map((_, cell) => <td key={cell}><Skeleton variant="shimmer" className="tracker-skeleton" /></td>)}
                    {[0, 1, 2, 3, 4].map((cell) => <td key={cell}><Skeleton variant="shimmer" className="tracker-skeleton tracker-skeleton-short" /></td>)}
                  </tr>
                ))}
              </>
            ) : error && applications.length === 0 ? (
              <tr>
                <td colSpan={7} className="tracker-state-cell">
                  <strong>Applications unavailable</strong>
                  <span>Refresh to try loading your saved applications again.</span>
                </td>
              </tr>
            ) : applications.length ? (
              applications.map((application) => (
                <tr key={application.id}>
                  <td>{application.company_name || "Unknown"}</td>
                  <td>{application.role_title || "Unknown"}</td>
                  <td>{application.match_score ?? "-"}</td>
                  <td>{application.match_level || "-"}</td>
                  <td>
                    <select
                      value={application.status}
                      aria-label={`Status for ${application.company_name || "application"} — ${application.role_title || "role"}`}
                      className={`tracker-status-select tracker-status-${application.status.toLowerCase()}`}
                      disabled={mutatingId === application.id}
                      onChange={(event) =>
                        changeStatus(
                          application.id,
                          event.target.value as ApplicationStatus,
                        )
                      }
                    >
                      {statuses.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{new Date(application.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => removeApplication(application.id)}
                      className="tracker-delete"
                      disabled={mutatingId === application.id}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : isLoading ? null : (
              <tr>
                <td colSpan={7} className="tracker-empty">
                  <strong>No applications saved yet.</strong>
                  <span>Your saved opportunities will appear here.</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
