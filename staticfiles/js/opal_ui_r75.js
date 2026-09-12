/* OPAL Update 131.7 R75 — Interface Runtime Governance */
(function(){
  'use strict';
  var QUIET_HINT_SELECTORS = [
    '.form-text','.helptext','.opal-live-events-hint','.opal-mobile-scroll-hint',
    '[data-opal-quiet-hint]','[data-opal-r75-quiet]'
  ].join(',');
  var ACTION_SELECTOR = '.d-flex.gap-2,.d-flex.gap-3,.d-flex.justify-content-between';

  function isMeaningfulTitle(el){
    if(!el || !el.hasAttribute('title')) return false;
    var title=(el.getAttribute('title')||'').trim();
    if(!title) return false;
    if(el.matches('abbr[title]')) return true;
    return false;
  }

  function quietTitle(el){
    if(!el || !el.hasAttribute('title') || isMeaningfulTitle(el)) return;
    var title=(el.getAttribute('title')||'').trim();
    if(title){
      el.setAttribute('data-opal-title',title);
      el.removeAttribute('title');
    }
  }

  function normalizeTitles(root){
    if(!root) return;
    if(root.nodeType===1) quietTitle(root);
    if(!root.querySelectorAll) return;
    root.querySelectorAll('[title]').forEach(quietTitle);
  }

  function quietHints(root){
    if(!root || !root.querySelectorAll) return;
    root.querySelectorAll(QUIET_HINT_SELECTORS).forEach(function(el){
      if(el.matches('.invalid-feedback,.text-danger,[role="alert"]')) return;
      el.setAttribute('data-opal-r75-quiet','true');
      el.setAttribute('aria-hidden','true');
    });
  }

  function classifyActionRows(root){
    if(!root || !root.querySelectorAll) return;
    root.querySelectorAll(ACTION_SELECTOR).forEach(function(row){
      if(row.closest('.modal,.dropdown-menu,.navbar,.opal-topbar-shell')) return;
      var buttons=row.querySelectorAll(':scope > .btn, :scope > button, :scope > a.btn');
      if(buttons.length>=2 && buttons.length<=6) row.classList.add('opal-r75-action-row');
    });
  }

  function normalizeTables(root){
    if(!root || !root.querySelectorAll) return;
    root.querySelectorAll('table.table').forEach(function(table){
      if(table.parentElement && table.parentElement.classList.contains('table-responsive')) return;
      table.classList.add('opal-r75-table');
    });
  }

  function dismissBootstrapFloating(){
    if(window.bootstrap){
      document.querySelectorAll('[data-bs-toggle="tooltip"],[data-bs-toggle="popover"]').forEach(function(el){
        try{
          var t=bootstrap.Tooltip.getInstance(el); if(t) t.hide();
          var p=bootstrap.Popover.getInstance(el); if(p) p.hide();
        }catch(e){}
      });
    }
  }

  function normalize(root){
    normalizeTitles(root);
    quietHints(root);
    classifyActionRows(root);
    normalizeTables(root);
    dismissBootstrapFloating();
  }

  function boot(){
    document.documentElement.classList.add('opal-r75-governed');
    normalize(document);
    var observer=new MutationObserver(function(records){
      records.forEach(function(record){
        record.addedNodes.forEach(function(node){
          if(node.nodeType===1) normalize(node);
        });
        if(record.type==='attributes' && record.target && record.attributeName==='title') quietTitle(record.target);
      });
    });
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['title']});
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
