const DATABASE='fieldnotes-research-v1';
export const LEGACY_KEY='fieldnotes.workspace.v1';
let connection;
function database(){
  if(!connection)connection=new Promise((resolve,reject)=>{
    const request=indexedDB.open(DATABASE,1);
    request.onupgradeneeded=()=>request.result.createObjectStore('workspace');
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
  });
  return connection;
}
export async function loadWorkspace(){
  try{
    const db=await database();const saved=await new Promise((resolve,reject)=>{const req=db.transaction('workspace').objectStore('workspace').get('current');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
    if(saved)return saved;
  }catch{}
  try{return JSON.parse(localStorage.getItem(LEGACY_KEY));}catch{return null;}
}
export async function saveWorkspace(value){
  try{
    const db=await database();await new Promise((resolve,reject)=>{const tx=db.transaction('workspace','readwrite');tx.objectStore('workspace').put(value,'current');tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});
    localStorage.removeItem(LEGACY_KEY);return;
  }catch(error){
    // A clear error banner is shown if both browser persistence options fail.
    localStorage.setItem(LEGACY_KEY,JSON.stringify(value));
  }
}
