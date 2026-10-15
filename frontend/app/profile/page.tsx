"use client";

import { useEffect, useState } from "react";
import { ApiError, getProfile, saveInterests } from "@/lib/api";
import { EVENT_CATEGORIES } from "@/lib/categories";
import type { EventCategory, StudentProfile } from "@/lib/types";
import RequireAuth from "../components/auth/RequireAuth";
import StudentsOnly from "../components/auth/StudentsOnly";
import { FormError } from "../components/auth/AuthForm";

export default function ProfilePage() {
  return (
    <RequireAuth>
      <StudentsOnly>
        <Profile />
      </StudentsOnly>
    </RequireAuth>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </dt>
      <dd className="mt-1 text-[15px] text-ink">{value}</dd>
    </div>
  );
}

function Profile() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [interests, setInterests] = useState<EventCategory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getProfile().then(
      (loaded) => {
        setProfile(loaded);
        setInterests(loaded.preferences.interests);
      },
      (err) =>
        setError(err instanceof ApiError ? err.message : "Could not load your profile."),
    );
  }, []);

  function toggle(category: EventCategory) {
    setSaved(false);
    setInterests((current) =>
      current.includes(category)
        ? current.filter((c) => c !== category)
        : [...current, category],
    );
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const updated = await saveInterests(interests);
      setProfile(updated);
      setInterests(updated.preferences.interests);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your interests.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto px-6 py-10">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
        Your profile
      </p>
      <h1 className="mt-2 font-display text-3xl font-medium tracking-tight text-ink">
        {profile?.name ?? "Loading…"}
      </h1>

      {profile && (
        <>
          <dl className="mt-8 grid grid-cols-2 gap-x-8 gap-y-5 border-y border-line py-6">
            <Detail label="Student ID" value={profile.student_id} />
            <Detail label="Program" value={profile.program} />
            <Detail label="Year" value={String(profile.year)} />
            <Detail label="Semester" value={String(profile.semester)} />
            {profile.section && <Detail label="Section" value={profile.section} />}
            {profile.electives.length > 0 && (
              <div className="col-span-2">
                <Detail
                  label="Electives this semester"
                  value={profile.electives.map((e) => e.name).join(", ")}
                />
              </div>
            )}
          </dl>

          <form onSubmit={handleSave} className="mt-8">
            <h2 className="font-display text-xl font-medium text-ink">
              What are you interested in?
            </h2>
            <p className="mt-1 text-[13.5px] text-ink-soft">
              The assistant uses this to suggest events and tailor its answers.
            </p>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {EVENT_CATEGORIES.map(({ value, label }) => (
                <label
                  key={value}
                  className="flex cursor-pointer items-center gap-3 border border-line bg-cream-raised px-3.5 py-3 text-[14px] text-ink has-[:checked]:border-brass has-[:checked]:bg-cream"
                >
                  <input
                    type="checkbox"
                    checked={interests.includes(value)}
                    onChange={() => toggle(value)}
                    className="h-4 w-4 accent-navy"
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="mt-5 space-y-3">
              <FormError message={error} />
              <button
                type="submit"
                disabled={busy}
                className="bg-navy px-5 py-2.5 font-mono text-[12px] uppercase tracking-[0.14em] text-cream transition-colors duration-150 hover:bg-brass disabled:opacity-60"
              >
                {busy ? "Saving…" : "Save interests"}
              </button>
              {saved && (
                <p className="font-mono text-[12px] text-forest">Saved.</p>
              )}
            </div>
          </form>
        </>
      )}
      {!profile && <FormError message={error} />}
    </main>
  );
}
