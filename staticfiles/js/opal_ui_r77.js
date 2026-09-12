/* OPAL Update 131.7 R77 — runtime enforcement for the quiet, visible interface. */
(function(){
  'use strict';
  const QUIET='.form-text,.helptext,.opal-live-events-hint,.opal-mobile-scroll-hint,[data-opal-quiet-hint],[data-opal-r75-quiet]';
  function preserveTitle(el){return el.matches('abbr,[data-opal-keep-title]');}
  function quietTitle(el){if(!el||!el.hasAttribute||!el.hasAttribute('title')||preserveTitle(el))return;const t=(el.getAttribute('title')||'').trim();if(t)el.setAttribute('data-opal-title',t);el.removeAttribute('title');}
  function quietHints(root){if(!root||!root.querySelectorAll)return;root.querySelectorAll(QUIET).forEach(el=>{if(el.matches('.invalid-feedback,.text-danger,[role="alert"]'))return;el.hidden=true;el.setAttribute('aria-hidden','true');});}
  function removeFloating(root){if(!root||!root.querySelectorAll)return;root.querySelectorAll('.tooltip,.popover').forEach(el=>{if(!el.matches('[data-opal-keep-floating]'))el.remove();});}
  function normalize(root){if(root.nodeType===1)quietTitle(root);if(root.querySelectorAll)root.querySelectorAll('[title]').forEach(quietTitle);quietHints(root);removeFloating(root);}
  function boot(){document.documentElement.classList.add('opal-r77-visible');normalize(document);const observer=new MutationObserver(records=>{for(const r of records){for(const n of r.addedNodes){if(n.nodeType===1)normalize(n);}if(r.type==='attributes'&&r.attributeName==='title')quietTitle(r.target);}});observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['title']});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
