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
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Application Tracker
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Saved applications from the orchestrator pipeline.
          </p>
        </div>
        <button
          type="button"
          onClick={loadApplications}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {message ? (
        <p className="mt-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="border-b border-slate-200 py-3 pr-4">Company</th>
              <th className="border-b border-slate-200 py-3 pr-4">Role</th>
              <th className="border-b border-slate-200 py-3 pr-4">Score</th>
              <th className="border-b border-slate-200 py-3 pr-4">Level</th>
              <th className="border-b border-slate-200 py-3 pr-4">Status</th>
              <th className="border-b border-slate-200 py-3 pr-4">Created</th>
              <th className="border-b border-slate-200 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-500">
                  Loading saved applications...
                </td>
              </tr>
            ) : applications.length ? (
              applications.map((application) => (
                <tr key={application.id} className="align-top">
                  <td className="border-b border-slate-100 py-3 pr-4 font-medium text-slate-900">
                    {application.company_name || "Unknown"}
                  </td>
                  <td className="border-b border-slate-100 py-3 pr-4 text-slate-700">
                    {application.role_title || "Unknown"}
                  </td>
                  <td className="border-b border-slate-100 py-3 pr-4 text-slate-700">
                    {application.match_score ?? "-"}
                  </td>
                  <td className="border-b border-slate-100 py-3 pr-4 text-slate-700">
                    {application.match_level || "-"}
                  </td>
                  <td className="border-b border-slate-100 py-3 pr-4">
                    <select
                      value={application.status}
                      onChange={(event) =>
                        changeStatus(
                          application.id,
                          event.target.value as ApplicationStatus,
                        )
                      }
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-slate-500 focus:ring-4 focus:ring-slate-100"
                    >
                      {statuses.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="border-b border-slate-100 py-3 pr-4 text-slate-600">
                    {new Date(application.created_at).toLocaleDateString()}
                  </td>
                  <td className="border-b border-slate-100 py-3">
                    <button
                      type="button"
                      onClick={() => removeApplication(application.id)}
                      className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 transition hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-6 text-center text-slate-500">
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
