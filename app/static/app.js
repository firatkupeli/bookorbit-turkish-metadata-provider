'use strict';
const $ = id => document.getElementById(id);
const fields = ['title','authors','translators','publisher','isbn','published_date','language','description'];
const labels = {title:'Kitap adı',authors:'Yazarlar',translators:'Çevirmenler',publisher:'Yayınevi',isbn:'ISBN',published_date:'Yayın tarihi',language:'Dil',description:'Açıklama'};
let file = null, selected = null, current = null, coverId = null, coverUrl = null, coverHash = null, loadNumber = 0;
let prepared = null;
let manualCover=null,manualUrl=null,manualInfo=null,manualHash=null;
const sourceNames={kitapyurdu:'Kitapyurdu','1000kitap':'1000Kitap',all:'Tüm kaynaklar'};
let busy = false;
function status(message, error=false) { $('status').textContent=message; $('status').classList.toggle('error',error); }
function values(id) { return $(id).value.split('\n').map(s=>s.trim()).filter(Boolean); }
function metadata() { return Object.fromEntries(fields.map(id=>[id, ['authors','translators'].includes(id)?values(id):$(id).value.trim()])); }
function writeFields(data) { for(const id of fields) $(id).value=Array.isArray(data[id])?data[id].join('\n'):(data[id]||''); }
function exportOptions() { return {metadata:metadata(),cover_provider_id:$('use-cover').checked?coverId:null,expected_cover_sha256:$('use-cover').checked?coverHash:$('use-manual-cover').checked?manualHash:null,upgrade_epub3:$('upgrade-epub3').checked}; }
function imageLabel(info) {return info?`${info.width} × ${info.height} px · ${info.format==='JPEG'?'JPG':info.format} · ${info.bytes>=1000000?(info.bytes/1000000).toFixed(2)+' MB':Math.max(1,Math.round(info.bytes/1000))+' KB'}`:'Ölçü bilgisi yok';}
function clearManualCover(){manualCover=null;manualInfo=null;manualHash=null;if(manualUrl)URL.revokeObjectURL(manualUrl);manualUrl=null;$('manual-cover-preview').hidden=true;$('use-manual-cover').checked=false;$('use-manual-cover').disabled=true;}
function clearSourceCover(){loadNumber++;coverId=null;coverHash=null;if(coverUrl)URL.revokeObjectURL(coverUrl);coverUrl=null;$('found-cover').hidden=true;$('source-cover-card').hidden=true;$('use-cover').checked=false;$('use-cover').disabled=true;if(!$('use-manual-cover').checked)$('keep-cover').checked=true;}
function fingerprint() { return JSON.stringify({options:exportOptions(),format:$('output-format').value}); }
function syncButtons() { $('check-book').disabled=!file||busy;$('restore-original').disabled=!file||busy;$('confirm-download').disabled=!prepared||busy; }
function invalidateReview() { prepared=null;syncButtons(); }
const errors = {search_deadline_exceeded:'Arama zaman aşımına uğradı. Aynı sorguyla biraz sonra tekrar dene.',unauthorized:'Erişim anahtarı gerekli veya yanlış. Bağlantı ayarını kontrol et.',provider_busy:'Sağlayıcı başka bir arama yapıyor. Biraz sonra tekrar dene.',editor_busy:'Düzenleyici başka bir EPUB işliyor. Biraz sonra tekrar dene.',provider_rate_limited:'İstek sınırına ulaşıldı. Biraz sonra tekrar dene.',source_rate_limited:'Kaynak istekleri geçici olarak sınırladı. Biraz sonra tekrar dene.',invalid_isbn:'ISBN kontrol basamağı geçersiz.',upload_too_large:'EPUB en fazla 25 MiB olabilir.',source_robots_disallowed:'Kaynak otomatik erişime izin vermiyor.',source_access_refused:'Kaynak otomatik erişimi reddetti. Diğer kaynağı veya manuel düzenlemeyi kullanabilirsin.',source_network_error:'Kaynağa bağlanılamadı. Biraz sonra tekrar dene.',source_search_markup_changed:'Kaynağın arama yapısı değişmiş. Diğer kaynağı kullanabilirsin.',source_book_markup_changed:'Kaynak kitap bilgisi okunamadı.',source_robots_unavailable:'Kaynağın erişim kuralları şu anda doğrulanamıyor.',source_timeout:'Kaynak yanıtı zaman aşımına uğradı.',book_not_found:'Kitap kaydı bulunamadı.',query_author_or_isbn_required:'ISBN, kitap adı veya yazar gir.',same_origin_required:'Bu işlemi sağlayıcının kendi web sayfasından yap.'};
async function api(path, options={}) {
  const token=$('token').value.trim().replace(/^Bearer\s+/i,'');
  const headers=new Headers(options.headers||{}); headers.set('X-BookOrbit-Web','1');
  if(token) headers.set('Authorization','Bearer '+token);
  const response=await fetch(path,{...options,headers,credentials:'omit',cache:'no-store'});
  if(!response.ok) { let body={}; try { body=await response.json(); } catch {} const retry=response.headers.get('retry-after'); throw new Error((body.message||errors[body.error]||'İşlem tamamlanamadı. Kaynak erişimini ve dosyayı kontrol et.')+(retry?` (${retry} saniye sonra tekrar deneyebilirsin.)`:'')); }
  return response;
}
async function action(button, message, work) {
  if(busy) return;
  busy=true; const buttons=[...document.querySelectorAll('button')], states=buttons.map(b=>b.disabled);
  $('workspace').inert=true;$('review-dialog').inert=true;
  buttons.forEach(b=>b.disabled=true); status(message);
  try { await work(); } catch(error) { status(error.message||'Bağlantı kurulamadı.',true); }
  finally { buttons.forEach((b,i)=>b.disabled=states[i]); busy=false;$('workspace').inert=false;$('review-dialog').inert=false;syncButtons();if($('review-dialog').open)$('close-review').focus(); }
}
async function loadFile(candidate) {
  if(!candidate||busy) return;
  if(!/\.(?:epub|kepub)$/i.test(candidate.name)||candidate.size>25*1024*1024) {status('En fazla 25 MiB boyutunda bir EPUB veya KEPUB seç.',true);return;}
  await action(null,'EPUB okunuyor…',async()=>{
    const fd=new FormData();fd.append('file',candidate);
    const data=await (await api('/web/epub/read',{method:'POST',body:fd})).json();
    file=candidate;current=data;selected=null;clearManualCover();clearSourceCover();invalidateReview();
    $('source-report').replaceChildren(makeText('Dosyan henüz denetlenmedi. Yüklenen kitabı kontrol edebilir veya düzenleyip çıktı raporunu inceleyebilirsin.','report-hint'));
    if(coverUrl){URL.revokeObjectURL(coverUrl);coverUrl=null;}
    $('found-cover').hidden=true;$('use-cover').checked=false;$('use-cover').disabled=true;
    $('cover-help').textContent='Mevcut kapak korunacak.';
    writeFields(data.metadata);$('search-isbn').value=data.metadata.isbn||'';$('search-title').value=data.metadata.title||'';$('search-author').value=(data.metadata.authors||[]).join(' ');
    $('dropzone').classList.add('hidden');$('book-preview').classList.remove('hidden');$('filename').textContent=candidate.name;
    $('current-cover').hidden=!data.cover;$('current-cover').src=data.cover||'';$('cover-placeholder').classList.toggle('hidden',Boolean(data.cover));$('cover-title').textContent=data.metadata.title||'Kitabın';
    $('current-cover-info').textContent=data.cover_info?imageLabel(data.cover_info):'';
    $('version').textContent=(data.input_format==='kepub'?'KEPUB · ':'')+'EPUB '+data.epub_version;$('metadata-fields').disabled=false;$('results').replaceChildren();$('match').classList.add('hidden');$('output-format').value='original';$('upgrade-epub3').checked=false;$('upgrade-epub3').disabled=data.epub_version.startsWith('3.');updateFormat();
    $('step1').classList.remove('current');$('step2').classList.add('current');$('step3').classList.remove('current');
    status('Kitabın hazır. Bir kaynakta baskını ara veya bilgilerini elle düzenle.');
  });
}
$('file').addEventListener('change',()=>{loadFile($('file').files[0]);$('file').value='';});
$('dropzone').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('file').click();}});
for(const type of ['dragenter','dragover']) $('dropzone').addEventListener(type,event=>{event.preventDefault();$('dropzone').classList.add('dragover');});
for(const type of ['dragleave','drop']) $('dropzone').addEventListener(type,event=>{event.preventDefault();$('dropzone').classList.remove('dragover');});
$('dropzone').addEventListener('drop',event=>loadFile(event.dataTransfer.files[0]));
$('search-form').addEventListener('submit',event=>{event.preventDefault();action($('search'),sourceNames[$('source-select').value]+' üzerinde aranıyor…',async()=>{
  if(!file) throw new Error('Önce düzenleyeceğin EPUB’u yükle.');
  const params=new URLSearchParams({source:$('source-select').value,query:$('search-title').value.trim(),author:$('search-author').value.trim(),isbn:$('search-isbn').value.trim(),limit:'5'});
  const data=await (await api('/web/search?'+params)).json();
  clearSourceCover();$('results').replaceChildren();$('match').classList.add('hidden');selected=null;invalidateReview();
  for(const book of data.matches){
    const button=document.createElement('button');button.type='button';button.className='result';
    const title=document.createElement('strong');title.textContent=book.title;
    const detail=document.createElement('span');detail.textContent=[sourceNames[book.providerId.split(':')[0]],(book.authors||[]).join(', '),book.publisher,book.publishedYear,book.pages?book.pages+' sayfa':null,book.isbn13||book.isbn10].filter(Boolean).join(' · ');
    button.append(title,detail);button.addEventListener('click',()=>selectBook(book,button));$('results').append(button);
  }
  status(data.matches.length?`${data.matches.length} baskı bulundu. ISBN, yayınevi ve yazarı kontrol ederek birini seç.`+(data.partial?' Arama kısmen tamamlandı.':''):'Sonuç bulunamadı. Kitap adı ve yazarı da girerek tekrar ara.');
});});
function selectBook(book,button) {
  if(busy)return;
  selected=book;clearSourceCover();const sequence=loadNumber;invalidateReview();
  document.querySelectorAll('.result').forEach(n=>n.classList.toggle('selected',n===button));
  $('match-title').textContent=book.title;$('match-details').textContent=[book.publisher,book.publishedDate,book.pages?book.pages+' sayfa':null].filter(Boolean).join(' · ');
  const url=new URL(book.url),source=book.providerId.split(':')[0];$('match-link').href=url.protocol==='https:'&&['www.kitapyurdu.com','1000kitap.com'].includes(url.hostname)?url.href:'#';$('match-link').textContent=(sourceNames[source]||'Kaynak')+' ↗';
  $('match').classList.remove('hidden');$('field-choices').replaceChildren();$('use-cover').checked=false;$('use-cover').disabled=true;$('found-cover').hidden=true;
  const proposed={title:book.title,authors:book.authors,translators:book.translators,publisher:book.publisher,isbn:book.isbn13||book.isbn10,published_date:book.publishedDate||book.publishedYear,language:book.languageCode,description:book.description};
  selected.proposed=proposed;
  for(const id of fields){
    const value=proposed[id];if(!value||(Array.isArray(value)&&!value.length))continue;
    const label=document.createElement('label');label.className='field-choice';const check=document.createElement('input');check.type='checkbox';check.checked=true;check.dataset.field=id;
    const span=document.createElement('span'),name=document.createElement('b'),content=document.createElement('span');name.textContent=labels[id];content.className='value';content.textContent=Array.isArray(value)?value.join(', '):value;span.append(name,content);label.append(check,span);$('field-choices').append(label);
  }
  status('Bu baskı doğruysa aktarılacak alanları seç. Dolu alanları koruma seçeneği açık.');
  if(book.cover&&current.can_replace_cover!==false){
    api('/web/cover/'+encodeURIComponent(book.providerId)).then(async response=>({blob:await response.blob(),hash:response.headers.get('x-cover-sha256'),info:{width:Number(response.headers.get('x-image-width')),height:Number(response.headers.get('x-image-height')),bytes:Number(response.headers.get('x-image-bytes')),format:response.headers.get('x-image-format')}})).then(({blob,hash,info})=>{
      if(sequence!==loadNumber)return;if(coverUrl)URL.revokeObjectURL(coverUrl);coverUrl=URL.createObjectURL(blob);$('found-cover').src=coverUrl;$('found-cover').hidden=false;$('source-cover-card').hidden=false;$('found-cover-info').textContent=(sourceNames[source]||'Kaynak')+' · '+imageLabel(info);$('use-cover').disabled=false;coverId=book.providerId;coverHash=hash;
    }).catch(()=>{if(sequence===loadNumber)$('cover-help').textContent='Kaynak kapağı alınamadı; mevcut kapak korunacak.';});
  }
}
$('apply').addEventListener('click',()=>{
  if(!selected||!file)return;
  const gaps=$('fill-gaps').checked;
  for(const check of $('field-choices').querySelectorAll('input:checked')){
    const id=check.dataset.field;if(gaps&&$(id).value.trim())continue;
    const value=selected.proposed[id];$(id).value=Array.isArray(value)?value.join('\n'):value;
  }
  invalidateReview();
  $('step2').classList.remove('current');$('step3').classList.add('current');status('Seçili bilgiler aktarıldı. Son kez gözden geçirip EPUB’unu indir.');
});
function updateCoverChoice(){invalidateReview();$('cover-help').textContent=$('use-cover').checked?'Seçilen kaynağın kapağı kullanılacak.':$('use-manual-cover').checked?'Yüklediğin kapak kullanılacak.':'Mevcut kapak korunacak.';}
for(const id of ['keep-cover','use-cover','use-manual-cover'])$(id).addEventListener('change',updateCoverChoice);
$('source-select').addEventListener('change',()=>{clearSourceCover();selected=null;$('results').replaceChildren();$('match').classList.add('hidden');$('source-label').textContent=sourceNames[$('source-select').value];$('source-help').textContent=$('source-select').value==='1000kitap'?'Deneysel kaynak. ISBN ile birlikte kitap adı ve yazarı da gir.':'ISBN, kitap adı ve yazarla doğru baskıyı bul.';invalidateReview();updateCoverChoice();});
async function loadManualCover(candidate){
  if(!candidate||busy)return;if(!/\.(jpe?g|png)$/i.test(candidate.name)||candidate.size>5*1024*1024){status('En fazla 5 MiB boyutunda bir JPG veya PNG seç.',true);return;}
  if(!file){status('Önce bir EPUB veya KEPUB yükle.',true);return;}
  await action(null,'Kapak ve görsel ölçüleri kontrol ediliyor…',async()=>{
    const form=new FormData();form.append('cover',candidate);const data=await(await api('/web/cover/inspect',{method:'POST',body:form})).json();
    clearManualCover();manualCover=candidate;manualInfo=data.info;manualHash=data.sha256;manualUrl=URL.createObjectURL(candidate);
    $('manual-cover-image').src=manualUrl;$('manual-cover-preview').hidden=false;$('manual-cover-info').textContent=imageLabel(manualInfo);$('use-manual-cover').disabled=false;$('use-manual-cover').checked=true;updateCoverChoice();status('Kapak hazır. Ölçüleri karşılaştırabilir, indirmeden önce son görünümü inceleyebilirsin.');
  });
}
$('manual-cover-input').addEventListener('change',()=>{loadManualCover($('manual-cover-input').files[0]);$('manual-cover-input').value='';});
$('manual-cover-dropzone').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('manual-cover-input').click();}});
for(const type of ['dragenter','dragover'])$('manual-cover-dropzone').addEventListener(type,event=>{event.preventDefault();$('manual-cover-dropzone').classList.add('dragover');});
for(const type of ['dragleave','drop'])$('manual-cover-dropzone').addEventListener(type,event=>{event.preventDefault();$('manual-cover-dropzone').classList.remove('dragover');});
$('manual-cover-dropzone').addEventListener('drop',event=>loadManualCover(event.dataTransfer.files[0]));
$('remove-manual-cover').addEventListener('click',()=>{if(busy)return;const selected=$('use-manual-cover').checked;clearManualCover();if(selected)$('keep-cover').checked=true;updateCoverChoice();});
function updateFormat(){
  const kepub=$('output-format').value==='kepub';
  const upgrade=$('upgrade-epub3').checked;
  $('upgrade-help').textContent=current?.epub_version.startsWith('3.')?'Bu kitap zaten EPUB 3. Mevcut sürümü korunacak.':upgrade?'İçindekiler EPUB 3’e aktarılacak; indirmeden önce kitap içi bağlantılar kontrol edilecek.':'İsteğe bağlı. İçindekiler, bölüm sırası, görseller ve fontlar korunarak dönüştürülür.';
  $('format-help').textContent=kepub?'EPUB, Kepubify ile bu tarayıcıda Kobo biçimine dönüştürülür. Mevcut KEPUB yeniden dönüştürülmez.':'EPUB veya mevcut KEPUB yapısı korunur.';
  $('download-label').textContent='Değişiklikleri incele';
  $('download-note').textContent=kepub?'Kobo okuma işaretleri eklenir; metin ve kitap kimliği korunur.':'Metin, bölüm sırası ve kitap kimliği korunur. Yeni dosya indirilir.';
}
$('output-format').addEventListener('change',()=>{invalidateReview();updateFormat();});
$('upgrade-epub3').addEventListener('change',()=>{invalidateReview();updateFormat();});
for(const id of fields) $(id).addEventListener('input',invalidateReview);
$('edit-form').addEventListener('submit',event=>{event.preventDefault();action($('download'),'Karşılaştırma için kitabın hazırlanıyor…',async()=>{
  if(!file)throw new Error('Önce bir EPUB yükle.');
  const signature=fingerprint();
  if(prepared?.fingerprint===signature){renderReview();$('review-dialog').showModal();return;}
  const fd=new FormData();fd.append('file',file);fd.append('options',JSON.stringify(exportOptions()));
  if($('use-manual-cover').checked&&manualCover)fd.append('cover',manualCover);
  const response=await api('/web/epub/export',{method:'POST',body:fd});let blob=await response.blob();
  const header=response.headers.get('content-disposition')||'',match=header.match(/filename\*=UTF-8''([^;]+)/i);
  let name=match?decodeURIComponent(match[1]):file.name.replace(/\.(?:kepub\.)?epub$|\.kepub$/i,'-metadata.epub');
  if($('output-format').value==='kepub'){
    status('Kobo KEPUB tarayıcıda hazırlanıyor…');
    const {convertToKepub}=await import('/assets/kepub.js');
    blob=await convertToKepub(blob,percent=>status(`Kobo KEPUB hazırlanıyor… %${percent}`));
    name=name.replace(/(?:\.kepub)?\.epub$/i,'.kepub.epub');
  }
  status('Hazırlanan kitap kontrol ediliyor…');
  const checkData=new FormData();checkData.append('file',blob,name);
  const data=await (await api('/web/epub/check',{method:'POST',body:checkData})).json();
  prepared={blob,name,data,fingerprint:signature};renderReview();$('review-dialog').showModal();
  status('Karşılaştırma hazır. Bilgileri, kapağı ve kontrol raporunu inceleyebilirsin.');
});});

function makeText(value,className,tag='p') {const node=document.createElement(tag);node.textContent=value;if(className)node.className=className;return node;}
function displayValue(value) {return (Array.isArray(value)?value.join('\n'):value)||'—';}
function renderReport(target,report) {
  target.replaceChildren();
  const label=report.errors?`${report.errors} hata · ${report.warnings} uyarı`:report.warnings?`${report.warnings} uyarı`:'Denetlenen alanlarda sorun bulunmadı';
  target.append(makeText(label,'report-badge '+(report.errors?'has-errors':report.warnings?'has-warnings':'is-clear')));
  const stats=report.stats;target.append(makeText(`${stats.files} dosya · ${stats.reading_order} okuma öğesi · ${stats.images} görsel · ${stats.checked_documents} belge denetlendi`,'report-stats'));
  if(report.issues.length){
    const details=document.createElement('details');details.open=report.errors>0;const summary=document.createElement('summary');summary.textContent='Bulguları göster';details.append(summary);
    const list=document.createElement('ul');list.className='report-issues';
    for(const issue of report.issues){const item=document.createElement('li');item.className=issue.severity;item.append(makeText((issue.severity==='error'?'Hata: ':'Uyarı: ')+issue.message,'', 'span'));if(issue.file)item.append(makeText(issue.file,'issue-file','small'));list.append(item);}
    details.append(list);target.append(details);
  }
  if(report.issues_truncated)target.append(makeText('İlk 100 bulgu gösteriliyor.','report-hint'));
  target.append(makeText(report.scope,'report-scope'));
}
function comparisonRow(label,before,after) {
  const row=document.createElement('article');row.className='comparison-row';row.append(makeText(label,'','h3'));
  for(const [name,value] of [['Önce',before],['Sonra',after]]){const cell=document.createElement('div');cell.className='comparison-cell';cell.append(makeText(name,'comparison-label','span'),makeText(displayValue(value),'comparison-value'));row.append(cell);}
  return row;
}
function renderReview() {
  const data=prepared.data,changed=fields.filter(id=>JSON.stringify(current.metadata[id]||'')!==JSON.stringify(data.metadata[id]||''));
  const coverChanged=current.cover!==data.cover;
  const formatChanged=current.input_format!==data.input_format||current.epub_version!==data.epub_version;
  $('review-summary').textContent=changed.length||coverChanged||formatChanged?`${changed.length} bilgi alanı değişiyor · Kapak ${coverChanged?'değişiyor':'korunuyor'}${formatChanged?' · Dosya biçimi güncelleniyor':''}`:'Bilgiler, kapak ve dosya biçimi korunuyor.';
  const rows=$('review-changes');rows.replaceChildren();
  for(const id of changed)rows.append(comparisonRow(labels[id],current.metadata[id],data.metadata[id]));
  if(!changed.length)rows.append(makeText('Kitabın bilgi alanlarında değişiklik yok.','report-hint'));
  if(formatChanged){const format=value=>(value.input_format==='kepub'?'Kobo KEPUB':'EPUB')+' · EPUB '+value.epub_version;rows.append(comparisonRow('Dosya biçimi',format(current),format(data)));}
  const unchanged=fields.filter(id=>!changed.includes(id));
  if(unchanged.length){const details=document.createElement('details');details.className='unchanged-fields';const summary=document.createElement('summary');summary.textContent=`Korunan alanlar (${unchanged.length})`;details.append(summary);for(const id of unchanged)details.append(makeText(labels[id]+': '+displayValue(data.metadata[id]),'unchanged-value'));rows.append(details);}
  const covers=$('review-cover');covers.replaceChildren(makeText('Kapak karşılaştırması','','h3'));
  const coverGrid=document.createElement('div');coverGrid.className='cover-comparison';
  for(const [label,book] of [['Önce',current],['Sonra',data]]){const figure=document.createElement('figure');figure.append(makeText(label,'comparison-label','figcaption'));if(book.cover){const image=document.createElement('img');image.src=book.cover;image.alt=label+' kapak';figure.append(image,makeText(imageLabel(book.cover_info),'image-metrics'));}else figure.append(makeText(book.has_cover?'Bu kapağın önizlemesi gösterilemiyor.':'Kapak görseli yok.','cover-empty'));coverGrid.append(figure);}
  covers.append(coverGrid);renderReport($('output-report'),data.report);
  $('confirm-download').textContent=(data.input_format==='kepub'?'KEPUB indir':data.epub_version.startsWith('3.')?'EPUB 3 indir':'EPUB indir')+' ↓';
}
$('check-book').addEventListener('click',()=>action($('check-book'),'Yüklenen kitap kontrol ediliyor…',async()=>{
  if(!file)return;const form=new FormData();form.append('file',file);const data=await(await api('/web/epub/check',{method:'POST',body:form})).json();renderReport($('source-report'),data.report);status('Yüklenen kitabın kontrol raporu hazır.');
}));
$('restore-original').addEventListener('click',()=>{
  if(!file||busy)return;writeFields(current.metadata);clearManualCover();clearSourceCover();selected=null;
  if(coverUrl){URL.revokeObjectURL(coverUrl);coverUrl=null;}
  $('found-cover').hidden=true;$('use-cover').checked=false;$('use-cover').disabled=true;$('cover-help').textContent='Mevcut kapak korunacak.';
  $('match').classList.add('hidden');document.querySelectorAll('.result').forEach(node=>node.classList.remove('selected'));
  $('output-format').value='original';$('upgrade-epub3').checked=false;invalidateReview();updateFormat();
  $('step2').classList.add('current');$('step3').classList.remove('current');status('İlk yüklenen bilgiler ve kapak geri getirildi. Çıktı seçenekleri sıfırlandı.');
});
for(const id of ['close-review','back-to-edit'])$(id).addEventListener('click',()=>{if(!busy)$('review-dialog').close();});
$('review-dialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('confirm-download').addEventListener('click',()=>{
  if(!prepared||busy)return;if(prepared.fingerprint!==fingerprint()){invalidateReview();$('review-dialog').close();status('Bilgiler değişti. Karşılaştırmayı yeniden hazırla.');return;}
  const link=document.createElement('a'),url=URL.createObjectURL(prepared.blob);link.href=url;link.download=prepared.name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  $('review-dialog').close();$('step2').classList.remove('current');$('step3').classList.add('current');status('İncelediğin kitap indirildi. Orijinal dosyan yerinde duruyor.');
});
