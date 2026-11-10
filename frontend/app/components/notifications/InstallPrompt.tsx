"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

// The install offer that Chrome, Edge and Android browsers send. Safari on iPhone and iPad sends none.
type InstallOffer = Event & { prompt: () => Promise<unknown> };

const never = () => () => {};

// Lets a student put the app on their home screen.
export default function InstallPrompt() {
  const [offer, setOffer] = useState<InstallOffer | null>(null);
  const installed = useSyncExternalStore(
    never,
    () => window.matchMedia("(display-mode: standalone)").matches,
    () => false,
  );
  const onIos = useSyncExternalStore(
    never,
    () => /iPad|iPhone|iPod/.test(navigator.userAgent),
    () => false,
  );

  useEffect(() => {
    const remember = (event: Event) => {
      event.preventDefault(); // keep the offer, so it is shown here instead of by the browser
      setOffer(event as InstallOffer);
    };
    window.addEventListener("beforeinstallprompt", remember);
    return () => window.removeEventListener("beforeinstallprompt", remember);
  }, []);

  if (installed || (!offer && !onIos)) return null;

  return (
    <section className="mt-10">
      <h2 className="text-xl font-medium text-ink">Install the app</h2>
      {offer ? (
        <>
          <p className="mt-1 mb-4 text-small text-muted">
            Open Campus Copilot from your home screen, like any other app.
          </p>
          <button
            type="button"
            onClick={() => offer.prompt().then(() => setOffer(null))}
            className="min-h-11 bg-accent px-5 py-2.5 text-small font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98]"
          >
            Install the app
          </button>
        </>
      ) : (
        <p className="mt-1 text-small text-muted">
          To install, tap the Share button, then Add to Home Screen.
        </p>
      )}
    </section>
  );
}
