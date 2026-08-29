import "@testing-library/jest-dom/vitest";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverStub;
globalThis.scrollTo = vi.fn();

Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value() {
    const canvas = this;
    return {
      canvas,
      clearRect() {},
      fillText() {},
      getImageData: () => ({ data: new Uint8ClampedArray(120_000).fill(1) }),
      measureText: (text: string) => ({ width: Math.max(text.length * 10, 10) }),
    };
  },
});
