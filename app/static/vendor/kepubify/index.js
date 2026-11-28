import {
  AlreadyKepubError,
  call,
  contentInput,
  dec,
  getModule,
  setModule
} from "./chunk-3E3Y2FKS.js";

// src/index.ts
async function convert(epub, options = {}) {
  return call(await getModule(), "convert", epub, options);
}
async function transformContent(html, options = {}) {
  const [input, o] = contentInput(html, options);
  return dec.decode(await call(await getModule(), "transform_content", input, o));
}
export {
  AlreadyKepubError,
  convert,
  setModule,
  transformContent
};
