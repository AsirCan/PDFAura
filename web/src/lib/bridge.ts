// The page's one line to Python.
//
// Calls go to window.pywebview.api (src/app/bridge.py) and return promises.
// What Python sends unasked arrives as events: src/app/events.py calls
// window.__aura.emit(name, data), defined here before anything else runs.
// In a plain browser (npm run dev) and in tests there is no pywebview; a
// fake bridge stands in (fake-bridge.ts).
import type { Api, Events } from "./types";

type Handler<K extends keyof Events> = (data: Events[K]) => void;
const handlers = new Map<string, Set<(data: unknown) => void>>();

export function on<K extends keyof Events>(name: K, handler: Handler<K>): () => void {
  let set = handlers.get(name);
  if (!set) {
    set = new Set();
    handlers.set(name, set);
  }
  set.add(handler as (data: unknown) => void);
  return () => set.delete(handler as (data: unknown) => void);
}

export function emit<K extends keyof Events>(name: K, data: Events[K]): void {
  for (const handler of handlers.get(name) ?? []) {
    try {
      handler(data);
    } catch (error) {
      console.error(`event ${name}`, error);
    }
  }
}

declare global {
  interface Window {
    __aura?: { emit: (name: string, data: unknown) => void };
    pywebview?: { api: Api };
  }
}

window.__aura = { emit: (name, data) => emit(name as keyof Events, data as never) };

let current: Api | null = null;

/** The bridge in use; connect() must have finished. */
export function api(): Api {
  if (!current) throw new Error("bridge not connected");
  return current;
}

/** Use this bridge from now on (tests and the dev fake). */
export function useBridge<T extends Api>(bridge: T): T {
  current = bridge;
  return bridge;
}

/** Wait for pywebview's bridge; in a plain browser, fall back to the fake. */
export async function connect(): Promise<Api> {
  if (current) return current;
  if (window.pywebview?.api) return useBridge(window.pywebview.api);
  const ready = new Promise<Api | null>((resolve) => {
    window.addEventListener("pywebviewready", () => resolve(window.pywebview?.api ?? null), { once: true });
    // pywebview injects its bridge as the page loads; in a plain browser it
    // never comes.
    setTimeout(() => resolve(window.pywebview?.api ?? null), import.meta.env.DEV ? 400 : 10000);
  });
  const real = await ready;
  if (real) return useBridge(real);
  if (!import.meta.env.DEV) throw new Error("pywebview bridge did not load");
  const { createFakeBridge } = await import("./fake-bridge");
  return useBridge(createFakeBridge());
}
