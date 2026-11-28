import {
  AlreadyKepubError,
  contentInput,
  dec,
  getModule,
  setModule
} from "./chunk-3E3Y2FKS.js";

// src/worker.ts
var createWorker = () => {
  if (typeof Worker == "undefined") {
    throw new Error("kepubify: Web Workers are not available (use the main module instead)");
  }
  return new Worker(new URL("./kepubify.worker.js", import.meta.url), { type: "module" });
};
function setWorker(create) {
  createWorker = create;
}
async function convert(epub, options = {}) {
  return run("convert", epub, options);
}
async function transformContent(html, options = {}) {
  const [input, o] = contentInput(html, options);
  return dec.decode(await run("transform_content", input, o));
}
async function run(fn, input, o) {
  const { signal, warn, progress, ...options } = o;
  signal?.throwIfAborted();
  const module = await getModule();
  signal?.throwIfAborted();
  const w = createWorker();
  return new Promise((resolve, reject) => {
    const stop = (err) => {
      w.terminate();
      signal?.removeEventListener("abort", abort);
      if (err !== void 0) reject(err);
    };
    const abort = () => stop(signal.reason);
    signal?.addEventListener("abort", abort);
    w.onmessage = ({ data: m }) => {
      try {
        if ("progress" in m) progress?.(m.progress);
        else if ("warn" in m) warn?.(...m.warn);
        else if ("output" in m) stop(), resolve(m.output);
        else stop(m.alreadyKepub ? new AlreadyKepubError(m.error) : new Error(m.error));
      } catch (err) {
        stop(err);
      }
    };
    w.onerror = (e) => (e.preventDefault(), stop(new Error(`kepubify: worker: ${e.message}`)));
    w.onmessageerror = () => stop(new Error("kepubify: worker: message can't be deserialized"));
    w.postMessage({ module, fn, input, options: { ...options, warn: !!warn, progress: !!progress } });
  });
}
export {
  AlreadyKepubError,
  convert,
  setModule,
  setWorker,
  transformContent
};
