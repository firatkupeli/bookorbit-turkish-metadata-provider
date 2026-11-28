// Offline integration test for the pinned upstream converter (no npm install).
import {readFile, writeFile} from 'node:fs/promises';
import {convert, AlreadyKepubError} from '../app/static/vendor/kepubify/index.js';
import {checkConversionWarning} from '../app/static/kepub.js';

const source=new Uint8Array(await readFile(process.argv[2]));
const result=await convert(source,{warn:checkConversionWarning});
await writeFile(process.argv[3],result);
try {
  await convert(result);
  throw new Error('Existing KEPUB was converted again');
} catch(error) {
  if(!(error instanceof AlreadyKepubError)) throw error;
}
console.log('Real EPUB to KEPUB conversion passed; existing KEPUB is detected.');
