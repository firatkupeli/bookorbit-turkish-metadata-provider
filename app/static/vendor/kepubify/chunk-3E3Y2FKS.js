// src/kepubify.ts
var AlreadyKepubError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "AlreadyKepubError";
  }
};
var compiled;
function setModule(module) {
  compiled = Promise.resolve(module);
}
function getModule() {
  return compiled ??= compile(new URL("kepubify.wasm", import.meta.url));
}
var enc = new TextEncoder();
var dec = new TextDecoder();
function contentInput(html, options) {
  if (typeof html == "string") {
    return [enc.encode(html), { ...options, charset: options.charset || "utf-8" }];
  }
  return [html, options];
}
async function compile(url) {
  if (url.protocol == "file:" && typeof process != "undefined" && process.versions?.node) {
    const { readFile } = await import("node:fs/promises");
    const { fileURLToPath } = await import("node:url");
    return WebAssembly.compile(await readFile(fileURLToPath(url)));
  }
  return WebAssembly.compileStreaming(fetch(url));
}
var flags = [
  "fullScreenFixes",
  "smartypants",
  "detectCover",
  "reprocessKepub",
  "warn",
  "progress"
];
function encodeOptions(o) {
  const parts = [];
  const u32 = (v) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, v, true);
    parts.push(b);
  };
  const str = (s) => {
    const b = enc.encode(s);
    u32(b.length);
    parts.push(b);
  };
  const tri = (v) => v === void 0 ? 0 : v ? 1 : 2;
  parts.push(new Uint8Array([
    flags.reduce((v, k, i) => v | (o[k] ? 1 << i : 0), 0),
    tri(o.hyphenate),
    tri(o.dummyTitlepage)
  ]));
  str(o.charset ?? "");
  u32(o.css?.length ?? 0);
  for (const s of o.css ?? []) str(s);
  u32(o.replace?.length ?? 0);
  for (const r of o.replace ?? []) str(r.find), str(r.replace);
  const buf = new Uint8Array(parts.reduce((n, b) => n + b.length, 0));
  let p = 0;
  for (const b of parts) buf.set(b, p), p += b.length;
  return buf;
}
async function instantiate(module, o) {
  let x, dv, output = "";
  const view = () => dv?.buffer == x.memory.buffer ? dv : dv = new DataView(x.memory.buffer);
  const bytes = (p, n) => new Uint8Array(x.memory.buffer, p, n);
  const wasi = {};
  const ENOSYS = 52, EBADF = 8;
  for (const { module: m, name } of WebAssembly.Module.imports(module)) {
    if (m == "wasi_snapshot_preview1") wasi[name] = () => ENOSYS;
    else if (m != "kepubify") throw new Error(`unexpected import ${m}.${name}`);
  }
  wasi.args_sizes_get = wasi.environ_sizes_get = (n, size) => (view().setUint32(n, 0, true), view().setUint32(size, 0, true), 0);
  wasi.fd_prestat_get = () => EBADF;
  wasi.fd_write = (fd, iovs, iovsLen, nwritten) => {
    if (fd != 1 && fd != 2) return EBADF;
    let n = 0;
    for (let i = 0; i < iovsLen; i++) {
      const p = view().getUint32(iovs + i * 8, true), l = view().getUint32(iovs + i * 8 + 4, true);
      output += dec.decode(bytes(p, l));
      n += l;
    }
    view().setUint32(nwritten, n, true);
    return 0;
  };
  wasi.clock_time_get = (_id, _precision, out) => (view().setBigUint64(out, BigInt(Math.round(performance.now() * 1e6)), true), 0);
  wasi.random_get = (p, n) => (crypto.getRandomValues(bytes(p, n)), 0);
  wasi.proc_exit = (code) => {
    throw new Error(`kepubify: wasm exited with code ${code}${output ? `: ${output.trim()}` : ""}`);
  };
  const kepubify = {
    warn: (name, nameLen, msg, msgLen) => o.warn?.(dec.decode(bytes(name, nameLen)), dec.decode(bytes(msg, msgLen))),
    progress: (percent) => o.progress?.(percent)
  };
  x = (await WebAssembly.instantiate(module, { wasi_snapshot_preview1: wasi, kepubify })).exports;
  x._initialize();
  return { x, view, bytes };
}
async function call(module, fn, input, o) {
  const { x, view, bytes } = await instantiate(module, o);
  const opts = encodeOptions(o);
  const ip = x.alloc(input.length);
  bytes(ip, input.length).set(input);
  const op = x.alloc(opts.length);
  bytes(op, opts.length).set(opts);
  const r = x[fn](ip, input.length, op, opts.length);
  const [status, p, n] = [0, 4, 8].map((i) => view().getUint32(r + i, true));
  const out = bytes(p, n).slice();
  switch (status) {
    case 0:
      return out;
    case 2:
      throw new AlreadyKepubError(dec.decode(out));
    default:
      throw new Error(`kepubify: ${dec.decode(out)}`);
  }
}

export {
  AlreadyKepubError,
  setModule,
  getModule,
  dec,
  contentInput,
  call
};
