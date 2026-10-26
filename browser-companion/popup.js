'use strict';
const $=id=>document.getElementById(id);let saved=null;
if(navigator.userAgent.includes('Edg/'))$('browser').value='msedge.exe';
function status(message){$('status').textContent=message;}
$('export').addEventListener('click',async()=>{
 try{
  const all=await chrome.windows.getAll({populate:true,windowTypes:['normal']});let skipped=0;
  const windows=all.filter(w=>!w.incognito).map(w=>({tabs:(w.tabs||[]).filter(t=>{const yes=BackHereBrowser.http(t.url);if(!yes)skipped++;return yes;}).map(t=>({url:t.url,title:(t.title||'').slice(0,512),active:t.active,pinned:t.pinned}))})).filter(w=>w.tabs.length);
  const data=BackHereBrowser.normalize({format:'backhere-browser',version:1,browser:$('browser').value,windows});
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);
  try{await chrome.downloads.download({url,filename:`BackHere-browser-${new Date().toISOString().slice(0,10)}.json`,saveAs:true});status(`Save requested: ${windows.length} windows. ${skipped} unsupported pages excluded. Check your downloads.`);}finally{setTimeout(()=>URL.revokeObjectURL(url),60000);}
 }catch(e){status(e.message);}
});
$('file').addEventListener('change',async()=>{
 saved=null;$('restore').disabled=true;
 try{const file=$('file').files[0];if(!file)return;if(file.size>5000000)throw Error('File exceeds 5 MB');saved=BackHereBrowser.normalize(JSON.parse(await file.text()));status(`${saved.windows.length} windows, ${saved.windows.reduce((n,w)=>n+w.tabs.length,0)} tabs ready. New windows will open.`);$('restore').disabled=false;}catch(e){status(e.message);}
});
$('restore').addEventListener('click',async()=>{
 if(!saved)return;$('restore').disabled=true;let opened=0;
 try{for(const w of saved.windows){const made=await chrome.windows.create({url:w.tabs.map(t=>t.url),focused:false});for(let i=0;i<w.tabs.length;i++){if(made.tabs?.[i])await chrome.tabs.update(made.tabs[i].id,{pinned:w.tabs[i].pinned});}const active=w.tabs.findIndex(t=>t.active);if(active>=0&&made.tabs?.[active])await chrome.tabs.update(made.tabs[active].id,{active:true});opened++;}status(`Opened ${opened} windows. Existing windows were preserved.`);}catch(e){status(`Opened ${opened} windows before error: ${e.message}. Retry may duplicate them.`);}finally{$('restore').disabled=false;}
});
