(function(){
  "use strict";
  function quietTitles(){
    document.querySelectorAll('[title]').forEach(function(el){
      if(el.matches('abbr,[data-opal-keep-title]')) return;
      var title=el.getAttribute('title');
      if(title && title.trim()){
        el.setAttribute('data-opal-title',title);
        el.removeAttribute('title');
      }
    });
  }
  function quietHints(){
    document.querySelectorAll('.form-text,.helptext,.opal-live-events-hint,[data-opal-quiet-hint]').forEach(function(el){
      el.setAttribute('aria-hidden','true');
    });
  }
  function compactMessages(){
    document.querySelectorAll('.opal-system-message').forEach(function(el){
      if(el.classList.contains('alert-danger')||el.classList.contains('alert-warning')) return;
      window.setTimeout(function(){
        if(!el.matches(':hover,:focus-within')) el.classList.add('opal-message-quiet');
      },13000);
    });
  }
  function normalizePageSubtitle(){
    var p=document.querySelector('.page-heading > p');
    if(!p) return;
    var t=(p.textContent||'').trim();
    if(!t || t==='نظام إدارة مدرسة أوبال الدولية' || t==='المصدر الرسمي لتعريف أنواع الرسوم المدرسية وقيمها الأساسية'){
      p.setAttribute('data-opal-quiet','true');
    }
  }
  function boot(){quietTitles();quietHints();compactMessages();normalizePageSubtitle();}
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
