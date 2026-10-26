(function(root){
'use strict';
const browsers=['chrome.exe','msedge.exe','brave.exe','vivaldi.exe','opera.exe'];
function http(value){try{return typeof value==='string'&&value.length<=4096&&!/[\r\n\0]/.test(value)&&['http:','https:'].includes(new URL(value).protocol);}catch{return false;}}
function normalize(data){
 if(!data||data.format!=='backhere-browser'||data.version!==1||!browsers.includes(data.browser)||!Array.isArray(data.windows)||data.windows.length>64)throw Error('Invalid BackHere browser file');
 const windows=data.windows.filter(w=>!w.incognito).map(w=>{
  if(!Array.isArray(w.tabs)||w.tabs.length>200)throw Error('Maximum 200 tabs per window');
  const tabs=w.tabs.map(t=>{if(!t||!http(t.url))throw Error('Only HTTP/HTTPS tabs can be restored');return {url:t.url,title:typeof t.title==='string'?t.title.slice(0,512):'',active:t.active===true,pinned:t.pinned===true};});
  return {tabs};
 }).filter(w=>w.tabs.length);
 if(!windows.length)throw Error('No restorable tabs');
 return {format:'backhere-browser',version:1,browser:data.browser,windows};
}
const api={http,normalize,browsers};
if(typeof module!=='undefined')module.exports=api;else root.BackHereBrowser=api;
})(globalThis);
