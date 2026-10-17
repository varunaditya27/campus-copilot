"use client";

import { useCallback, useState } from "react";
import { getAnalytics } from "@/lib/adminApi";
import { BarList, Donut, LineChart, SERIES, StackedBar, WordCloud } from "../_components/Charts";
import { useLoad } from "../_components/useLoad";
import { Banner, Loading, PageHeader, inputClass } from "../_components/ui";

const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value * 100)}%`);

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-surface p-4">
      <p className="text-small text-muted">{label}</p>
      <p className="mt-1 text-3xl font-medium text-ink">{value}</p>
      {note && <p className="mt-1 text-small text-muted">{note}</p>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-surface p-5">
      <h2 className="mb-4 text-lg font-medium text-ink">{title}</h2>
      {children}
    </section>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const load = useCallback(() => getAnalytics(days), [days]);
  const { data, error } = useLoad(load, "Could not load analytics.");

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics">
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Time range" className={`${inputClass} w-auto`}>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </PageHeader>
      {error && <Banner kind="error">{error}</Banner>}
      {!error && !data && <Loading what="analytics" />}

      {data && (
        <>
          <p className="text-small text-muted">
            {data.from} to {data.to} (UTC). Counts only questions answered since usage tracking began; the questions
            themselves are not kept.
          </p>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="Questions" value={String(data.totals.questions)} />
            <Stat label="Active students" value={String(data.totals.active_students)} />
            <Stat label="Conversations" value={String(data.totals.sessions)} />
            <Stat
              label="Questions per conversation"
              value={data.messages_per_session.average === null ? "—" : String(data.messages_per_session.average)}
            />
          </div>

          <Panel title="Active students per day">
            <LineChart points={data.daily_active_users} />
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Most-used tools">
              {data.tool_usage.length ? (
                <Donut slices={data.tool_usage.map((t) => ({ label: t.tool, value: t.count }))} />
              ) : (
                <p className="text-small text-muted">No tool calls in this period.</p>
              )}
            </Panel>
            <Panel title="Most-cited knowledge documents">
              {data.top_documents.length ? (
                <BarList rows={data.top_documents.map((d) => ({ label: d.document, value: d.count }))} />
              ) : (
                <p className="text-small text-muted">No documents were cited.</p>
              )}
            </Panel>
          </div>

          <Panel title="What students ask about">
            {data.top_terms.length ? (
              <WordCloud terms={data.top_terms} />
            ) : (
              <p className="text-small text-muted">
                Words appear once at least two questions have used them, so nothing personal is shown.
              </p>
            )}
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Agent">
              <div className="grid grid-cols-2 gap-4">
                <Stat
                  label="Tool calls per reply"
                  value={data.agent.avg_tool_calls_per_reply === null ? "—" : String(data.agent.avg_tool_calls_per_reply)}
                  note={`${data.agent.replies_with_tools} of ${data.agent.replies} replies used tools`}
                />
                <Stat
                  label="Actions approved"
                  value={percent(data.agent.actions.accept_rate)}
                  note={`of ${data.agent.actions.decided} decided`}
                />
              </div>
              <div className="mt-5">
                <p className="mb-2 text-small text-muted">
                  {data.agent.actions.proposed} proposed actions
                </p>
                <StackedBar
                  parts={[
                    { label: "Confirmed", value: data.agent.actions.confirmed, colour: SERIES[0] },
                    { label: "Failed after approval", value: data.agent.actions.failed, colour: SERIES[1] },
                    { label: "Cancelled", value: data.agent.actions.cancelled, colour: SERIES[2] },
                    { label: "Expired", value: data.agent.actions.expired, colour: SERIES[3] },
                    { label: "Waiting", value: data.agent.actions.waiting, colour: SERIES[4] },
                  ]}
                />
              </div>
            </Panel>
            <Panel title="Retrieval">
              <div className="grid grid-cols-2 gap-4">
                <Stat
                  label="Replies with no passage"
                  value={percent(data.rag.zero_context_rate)}
                  note={`${data.rag.zero_context_replies} of ${data.rag.replies}`}
                />
                <Stat label="Average distance / cache hits" value="—" note="Not recorded" />
              </div>
              <p className="mt-4 text-small text-muted">{data.rag.notes}</p>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
