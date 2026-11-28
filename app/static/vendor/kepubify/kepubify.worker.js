import {
  AlreadyKepubError,
  call
} from "./chunk-3E3Y2FKS.js";

// src/kepubify.worker.ts
var scope = self;
scope.onmessage = async ({ data: { module, fn, input, options } }) => {
  try {
    const output = await call(module, fn, input, {
      ...options,
      warn: options.warn ? (name, msg) => scope.postMessage({ warn: [name, msg] }) : void 0,
      progress: options.progress ? (percent) => scope.postMessage({ progress: percent }) : void 0
    });
    scope.postMessage({ output }, [output.buffer]);
  } catch (err) {
    scope.postMessage({
      error: err instanceof Error ? err.message : String(err),
      alreadyKepub: err instanceof AlreadyKepubError
    });
  }
};
