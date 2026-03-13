function filterSidebar(){
  const q=(document.getElementById('sidebarSearch')?.value||'').toLowerCase();
  document.querySelectorAll('.side-page').forEach(el=>{
    const hit=el.textContent.toLowerCase().includes(q);
    el.style.display=hit?'block':'none';
  });
}
document.addEventListener('input',(e)=>{if(e.target?.id==='sidebarSearch') filterSidebar();});
