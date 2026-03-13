function toggleScheduleFields(rootId){
  const root=document.getElementById(rootId); if(!root) return;
  const kind=root.querySelector('[name=schedule_kind]').value;
  root.querySelectorAll('[data-schedule-kind]').forEach(el=>{
    el.style.display = el.dataset.scheduleKind===kind ? 'block':'none';
  });
}
document.addEventListener('change',(e)=>{
  if(e.target && e.target.name==='schedule_kind'){
    const form=e.target.closest('[data-schedule-form]');
    if(form && form.id) toggleScheduleFields(form.id);
  }
});
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('[data-schedule-form]').forEach(f=>toggleScheduleFields(f.id));
});
