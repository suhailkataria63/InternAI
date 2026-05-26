"use client";

import { useEffect, useState } from "react";
import {
  deleteApplication,
  listApplications,
  updateApplicationStatus,
} from "../lib/api";
import type { ApplicationListItem, ApplicationStatus } from "../lib/types";

const statuses: ApplicationStatus[] = [
  "Saved",
  "Applied",
  "Interview",
  "Rejected",
  "Selected",
];

type ApplicationTrackerProps = {
  refreshKey: number;
};

export default function ApplicationTracker({ refreshKey }: ApplicationTrackerProps) {
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadApplications = async () => {
    setIsLoading(true);
    setError("");
    try {
      const rows = await listApplications();
      setApplications(rows);
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load saved applications.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadApplications();
  }, [refreshKey]);

  const changeStatus = async (id: number, status: ApplicationStatus) => {
    setMessage("");
    setError("");
    try {
      await updateApplicationStatus(id, status);
      setMessage("Status updated.");
      await loadApplications();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Status update failed.",
      );
    }
  };

  const removeApplication = async (id: number) => {
    setMessage("");
    setError("");
    try {
      await deleteApplication(id);
      setMessage("Application deleted.");
      await loadApplications();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error ? caughtError.message : "Delete failed.",
      );
    }
  };

  return (
    <section className="tracker-table-shell">
      <div className="tracker-toolbar">
        <div>
          <h4>Saved applications</h4>
          <p>Update status or remove opportunities from your local tracker.</p>
        </div>
        <button type="button" onClick={loadApplications} className="tracker-refresh">
          Refresh
        </button>
      </div>

      {message ? <p className="state-message success">{message}</p> : null}
      {error ? <p className="state-message error">{error}</p> : null}

      <div className="tracker-table-scroll">
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
            {isLoading ? (
              <tr>
                <td colSpan={7} className="tracker-empty">
                  Loading saved applications...
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
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="tracker-empty">
                  No saved applications yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
