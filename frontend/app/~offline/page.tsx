"use client";

export default function OfflinePage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-10">
      <h1 className="text-3xl font-medium tracking-[-0.03em] text-ink">You are offline</h1>
      <p className="mt-2 text-body text-muted">
        This page needs a connection. Pages you opened recently are still available, and you can
        try again when you are back online.
      </p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="mt-6 min-h-11 bg-accent px-5 py-2.5 text-small font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98]"
      >
        Try again
      </button>
    </main>
  );
}
