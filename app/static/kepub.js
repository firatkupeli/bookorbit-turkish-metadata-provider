// Conversion uses the pinned, self-hosted upstream Kepubify WebAssembly package.
export function checkConversionWarning(filename, message) {
  // Upstream's polyglot writer reports this standard EPUB XML attribute because
  // HTML parsers treat it as an ordinary attribute. It is not discarded content.
  if (message === 'attribute "epub:type" is in namespace "http://www.idpf.org/2007/ops" for XML parsers and in no namespace for HTML parsers (will not warn again for this prefix and namespace)') return;
  throw new Error('Bu EPUB güvenle dönüştürülemiyor. Orijinal biçimde indirebilirsin.');
}
export async function convertToKepub(blob, progress) {
  const {convert, AlreadyKepubError} = await import('/assets/vendor/kepubify/worker.js');
  const controller = new AbortController();
  const timer = setTimeout(()=>controller.abort(),120000);
  try {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    try {
      const result = await convert(bytes, {
        signal:controller.signal,
        reprocessKepub:false,
        progress:percent=>progress?.(Math.round(percent*100)),
        warn:checkConversionWarning
      });
      if(result.byteLength>25*1024*1024) throw new Error('Dönüştürülen KEPUB 25 MiB sınırını aşıyor.');
      return new Blob([result],{type:'application/epub+zip'});
    } catch(error) {
      if(error instanceof AlreadyKepubError) return blob;
      if(error.name==='AbortError') throw new Error('KEPUB dönüşüm süresi aşıldı. Daha küçük bir kitapla dene.');
      throw error;
    }
  } finally {clearTimeout(timer);}
}
