import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; Radix's Checkbox (via react-use-size) needs
// one to mount at all.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver =
    ResizeObserverStub as unknown as typeof ResizeObserver;
}
