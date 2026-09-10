/* OPAL Update 131.7 R76 — final UI/runtime governance */
(function(){
  "use strict";
  var KEEP_TITLE = /^(abbr)$/i;
  function clean(root){
    if(!root || !root.querySelectorAll) return;
    var nodes=[];
    if(root.nodeType===1) nodes.push(root);
    root.querySelectorAll("[title]").forEach(function(n){nodes.push(n);});
    nodes.forEach(function(el){
      if(KEEP_TITLE.test(el.tagName)) return;
      if(!el.hasAttribute("aria-label") && el.matches("button,a,input,select,textarea")){
        var txt=(el.getAttribute("title")||"").trim();
        if(txt) el.setAttribute("aria-label",txt);
      }
      el.removeAttribute("title");
    });
    root.querySelectorAll(".tooltip,.popover").forEach(function(el){el.remove();});
  }
  function boot(){
    document.documentElement.classList.add("opal-r76-governed");
    clean(document);
    if(!window.MutationObserver) return;
    var observer=new MutationObserver(function(records){
      records.forEach(function(r){
        if(r.type==="childList") r.addedNodes.forEach(function(n){if(n.nodeType===1) clean(n);});
        if(r.type==="attributes" && r.target) clean(r.target);
      });
    });
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["title"]});
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",boot,{once:true}); else boot();
})();
