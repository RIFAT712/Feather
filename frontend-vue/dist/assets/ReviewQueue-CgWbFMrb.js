import{$ as e,B as t,Dt as n,Et as r,G as i,J as a,K as o,Q as s,R as ee,V as te,W as c,X as l,Y as u,Z as ne,at as d,ct as f,ft as re,h as ie,kt as p,lt as m,mt as ae,ot as oe,p as se,pt as ce,q as h,r as le,rt as ue,v as g,yt as _}from"./index-CmEgUF9u.js";import{a as de,c as fe,d as pe,f as me,i as he,l as ge,n as _e,o as ve,p as ye,r as be,s as xe,u as Se}from"./codex-icons-BkUTHPM2.js";import{t as Ce}from"./contestLog-BxXA8Hlw.js";var we={key:0,class:`rq-center-state`},Te={key:1,class:`rq-center-state`},Ee={class:`rq-panel-header`},De={class:`rq-panel-header-top`},Oe={class:`rq-header-actions`},ke=[`aria-label`],Ae={"aria-hidden":`true`},je={key:0,class:`rq-owner-switcher`},Me={class:`rq-owner-mode-buttons`},Ne=[`value`],Pe={class:`rq-stats-strip`},Fe={class:`rq-stat`},Ie={class:`rq-stat-val`},Le={class:`rq-stat rq-stat-pending`},Re={class:`rq-stat-val`},ze={class:`rq-stat rq-stat-ok`},Be={class:`rq-stat-val`},Ve={class:`rq-stat rq-stat-rej`},He={class:`rq-stat-val`},Ue={key:0,class:`rq-bulk-banner`},We={class:`rq-bulk-count`},Ge={class:`rq-bulk-actions`},Ke={key:0,class:`rq-bulk-comment-panel`},qe={class:`rq-bulk-comment-heading`},Je={class:`rq-bulk-comment-hint`},Ye={class:`rq-panel-scroll`},Xe={class:`rq-group`},Ze={key:0,class:`rq-group-content is-open`},Qe={class:`rq-group-inner`},$e={class:`rq-list`},et=[`onClick`],tt=[`checked`,`onChange`],nt={class:`rq-item-content`},rt={class:`rq-item-title`},it={class:`rq-item-meta`},at={key:0,class:`rq-list-empty`},ot={key:1,class:`rq-load-more-wrap`},st={key:2,class:`rq-load-more-wrap`},ct={key:0,class:`rq-group`},lt={class:`rq-group-header-left`},ut={class:`rq-group-count`},dt={key:0,class:`rq-group-content is-open`},ft={class:`rq-group-inner`},pt={class:`rq-list`},mt={class:`rq-item-content`},ht={class:`rq-item-title`},gt={class:`rq-item-meta`},_t={key:0,class:`rq-load-more-wrap`},vt={class:`rq-group`},yt={class:`rq-group-header-left`},bt={class:`rq-group-count`},xt={key:0,class:`rq-group-content is-open`},St={class:`rq-group-inner`},Ct={class:`rq-list`},wt=[`onClick`],Tt={class:`rq-item-content`},Et={class:`rq-item-title`},Dt={class:`rq-item-meta`},Ot={key:0,class:`rq-list-empty`},kt={key:1,class:`rq-load-more-wrap`},At={key:0,class:`rq-center-state rq-center-full rq-panel`},jt={class:`rq-card-done`},Mt={class:`rq-done-icon`},Nt={class:`rq-panel rq-preview-panel`},Pt={class:`rq-article-header`},Ft={class:`rq-article-meta-area`},It=[`href`,`title`],Lt={class:`rq-tags`},Rt={class:`rq-tag`},zt={key:0,class:`rq-tag rq-tag-date`},Bt={key:1,class:`rq-tag rq-tag-locked`},Vt=[`href`],Ht={class:`rq-preview-container`},Ut={key:0,class:`rq-center-state`},Wt=[`srcdoc`],Gt={class:`rq-panel rq-decision-panel`},Kt={class:`rq-decision-body`},qt={key:0,class:`rq-error-msg`},Jt={class:`rq-decision-form`},Yt={class:`rq-actions-wrapper`},Xt={class:`rq-primary-actions`},Zt=[`disabled`],Qt=[`disabled`],$t={class:`rq-secondary-actions`},en=[`disabled`],tn=[`disabled`],nn={class:`rq-mobile-nav`},rn={key:0,class:`rq-nav-badge`},an=[`disabled`],on={key:3,class:`rq-undo-toast`,role:`status`},sn={class:`rq-undo-text`},cn={class:`rq-undo-title`},ln=[`disabled`],un={class:`rq-help-header`},dn=`https://bn.wiktionary.org/wiki/`,fn=`
  :root { color-scheme: dark; }
  html, body {
    background: oklch(0.1 0.01 264) !important;
    color: oklch(0.96 0.02 264) !important;
    font-family: 'Linux Libertine', Georgia, Times, serif;
    font-size: 15px;
    line-height: 1.6;
    margin: 0;
    padding: 20px 24px 64px;
    max-width: 860px;
  }
  /* Wikipedia-style link colors */
  a { color: #3366cc !important; }
  a:visited { color: #795cb2 !important; }
  a.new, a.new:visited { color: #d33 !important; }  /* red-links (missing pages) */
  a:hover { text-decoration: underline; }

  /* TOC, reflist, catlinks links inherit wiki-blue */
  .toc a, .toc a:visited { color: #3366cc !important; }
  .reflist a, .references a { color: #3366cc !important; }
  .catlinks a { color: #3366cc !important; }

  /* --- strip ALL inline light-background colors from every element --- */
  * { background-color: unset !important; }

  /* tables */
  table { border-collapse: collapse; background: oklch(0.15 0.01 264) !important; color: oklch(0.96 0.02 264) !important; }
  th, td { border: 1px solid oklch(0.4 0.02 264) !important; padding: 6px 10px; color: oklch(0.96 0.02 264) !important; }
  th { background: oklch(0.2 0.01 264) !important; }
  tr:nth-child(even) td { background: oklch(0.18 0.01 264) !important; }

  /* wikitable */
  .wikitable { background: oklch(0.15 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; }
  .wikitable > * > tr > th { background: oklch(0.2 0.01 264) !important; color: oklch(0.96 0.02 264) !important; }
  .wikitable > * > tr > td { background: transparent !important; }

  /* NavFrame */
  .NavFrame {
    border: 1px solid oklch(0.4 0.02 264) !important;
    border-radius: 6px;
    background: oklch(0.2 0.01 264) !important;
    margin: 12px 0;
    overflow: hidden;
  }
  .NavHead {
    background: oklch(0.25 0.02 264) !important;
    color: oklch(0.96 0.02 264) !important;
    padding: 6px 10px !important;
    cursor: pointer !important;
    font-weight: 600;
    user-select: none;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid oklch(0.4 0.02 264);
  }
  .NavHead:hover { background: oklch(0.3 0.02 264) !important; }
  .NavToggle { color: oklch(0.96 0.02 264) !important; font-size: 0.85em; }
  .NavContent { background: oklch(0.15 0.01 264) !important; }
  .NavContent td, .NavContent th { border-color: oklch(0.3 0.02 264) !important; }

  /* vsToggle */
  .vsToggleElement[style*='background'] { background: oklch(0.25 0.02 264) !important; color: oklch(0.96 0.02 264) !important; }
  th[class~='vsToggleElement'] { background: oklch(0.25 0.02 264) !important; color: oklch(0.96 0.02 264) !important; cursor: pointer !important; }

  /* mw-collapsible */
  .mw-collapsible-toggle { cursor: pointer; color: oklch(0.76 0.02 264) !important; }
  .mw-collapsed .mw-collapsible-content { display: none !important; }

  /* headings */
  h1, h2, h3, h4, h5 {
    color: oklch(0.96 0.02 264) !important;
    border-bottom: 1px solid oklch(0.4 0.02 264) !important;
    padding-bottom: 4px;
  }
  h2 { font-size: 1.4em; margin-top: 1.4em; }
  h3 { font-size: 1.15em; margin-top: 1em; }
  h4 { font-size: 1em; border-bottom: none !important; }

  /* TOC */
  #toc, .toc { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; border-radius: 6px; padding: 12px 18px; }
  .toctitle { color: oklch(0.96 0.02 264) !important; }

  /* hide edit links */
  .mw-editsection, .mw-editsection-bracket { display: none !important; }

  /* infobox */
  .infobox { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; }
  .infobox th { background: oklch(0.25 0.02 264) !important; }

  /* references */
  .reflist, ol.references { color: #94a3b8 !important; font-size: 0.85em; }

  /* categories */
  .catlinks { background: oklch(0.2 0.01 264) !important; border: 1px solid oklch(0.4 0.02 264) !important; color: oklch(0.76 0.02 264) !important; margin-top: 24px; padding: 8px 14px; border-radius: 6px; }

  /* hatnote/notices */
  .hatnote, .dablink { background: #1d3550 !important; border-left: 3px solid #4f9cf7 !important; padding: 6px 12px; color: #9eb6cc !important; }

  /* ib-header / inflection tables with inline styles */
  [style*='background:#'], [style*='background: #'], [style*='background:rgb'], [style*='background: rgb'] {
    background: rgba(80,80,120,0.25) !important;
    color: oklch(0.96 0.02 264) !important;
  }
  /* keep text-align / font-weight from inline styles but neutralise colour */
  [style*='color:rgb'], [style*='color: rgb'] { color: oklch(0.96 0.02 264) !important; }
`,pn=`
  (function() {
    function initNavFrames() {
      document.querySelectorAll('.NavFrame').forEach(function(frame) {
        var head = frame.querySelector('.NavHead');
        var content = frame.querySelector('.NavContent');
        if (!head || !content) return;
        content.style.display = 'none';
        var toggle = head.querySelector('.NavToggle a');
        if (!toggle) {
          var wrapper = document.createElement('span');
          wrapper.className = 'NavToggle';
          wrapper.style.cssText = 'float:right; font-weight:normal; font-size:smaller; padding-left: 8px;';
          toggle = document.createElement('a');
          toggle.href = '#';
          wrapper.appendChild(toggle);
          head.appendChild(wrapper);
        }
        toggle.textContent = '▶';
        head.style.cursor = 'pointer';
        head.addEventListener('click', function(e) {
          e.preventDefault();
          var hidden = content.style.display === 'none';
          content.style.display = hidden ? '' : 'none';
          toggle.textContent = hidden ? '▼' : '▶';
        });
      });
    }

    function initVsToggles() {
      document.querySelectorAll('.vsToggleElement').forEach(function(el) {
        var table = el.closest('table');
        if (!table) return;
        var anchor = el.querySelector('.NavToggle a');
        if (!anchor) {
          var wrapper = document.createElement('span');
          wrapper.className = 'NavToggle';
          wrapper.style.cssText = 'float:right; font-weight:normal; font-size:smaller; padding-left: 8px;';
          anchor = document.createElement('a');
          anchor.href = '#';
          wrapper.appendChild(anchor);
          el.appendChild(wrapper);
        }
        var shows = table.querySelectorAll('.vsShow');
        var hides = table.querySelectorAll('.vsHide');
        shows.forEach(function(r){ r.style.display = 'none'; });
        hides.forEach(function(r){ r.style.display = ''; });
        anchor.textContent = '▶';
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e) {
          e.preventDefault();
          var isExpanded = anchor.textContent.includes('▼');
          if (isExpanded) {
            shows.forEach(function(r){ r.style.display = 'none'; });
            hides.forEach(function(r){ r.style.display = ''; });
            anchor.textContent = '▶';
          } else {
            shows.forEach(function(r){ r.style.display = ''; });
            hides.forEach(function(r){ r.style.display = 'none'; });
            anchor.textContent = '▼';
          }
        });
      });
    }

    function initMwCollapsibles() {
      document.querySelectorAll('.mw-collapsible, table.collapsed, table.mw-collapsed').forEach(function(el) {
        var isTable = el.tagName === 'TABLE';
        var head = isTable ? el.querySelector('tr') : el.firstElementChild;
        if (!head) return;
        var toggler = el.querySelector('.mw-collapsible-toggle');
        if (!toggler) {
          toggler = document.createElement('span');
          toggler.className = 'mw-collapsible-toggle';
          toggler.style.cssText = 'float:right; cursor:pointer; user-select:none; font-size:smaller; padding-left:8px;';
          var th = head.querySelector('th') || head.querySelector('td') || head;
          if(th) th.appendChild(toggler);
        }
        toggler.textContent = '▶';
        if (isTable) {
          var rows = el.querySelectorAll('tr');
          rows.forEach(function(row, idx) { if (idx > 0) row.style.display = 'none'; });
        } else {
          var content = el.querySelector('.mw-collapsible-content');
          if (content) { content.style.display = 'none'; }
          else { Array.from(el.children).forEach(function(child, idx) { if (idx > 0) child.style.display = 'none'; }); }
        }
        head.style.cursor = 'pointer';
        head.addEventListener('click', function(e) {
          e.preventDefault();
          var isCollapsed = toggler.textContent.includes('▶');
          toggler.textContent = isCollapsed ? '▼' : '▶';
          if (isTable) {
            var rows = el.querySelectorAll('tr');
            rows.forEach(function(row, idx) { if (idx > 0) row.style.display = isCollapsed ? '' : 'none'; });
          } else {
            var content = el.querySelector('.mw-collapsible-content');
            if (content) { content.style.display = isCollapsed ? '' : 'none'; }
            else { Array.from(el.children).forEach(function(child, idx) { if (idx > 0) child.style.display = isCollapsed ? '' : 'none'; }); }
          }
        });
      });
    }

    document.addEventListener('DOMContentLoaded', function() {
      initNavFrames(); initVsToggles(); initMwCollapsibles();
    });
    if (document.readyState !== 'loading') {
      initNavFrames(); initVsToggles(); initMwCollapsibles();
    }
  })();
`,mn=`
  :root { color-scheme: light; }
  html, body {
    background: #f5f8fb !important;
    color: #20364d !important;
    font-family: 'Linux Libertine', Georgia, Times, serif;
    font-size: 15px;
    line-height: 1.6;
    margin: 0;
    padding: 20px 24px 64px;
    max-width: 860px;
  }
  a { color: #1769aa !important; }
  a:visited { color: #7253a8 !important; }
  a.new, a.new:visited { color: #b42332 !important; }
  a:hover { text-decoration: underline; }
  * { background-color: unset !important; }
  table, .wikitable { border-collapse: collapse; background: #ffffff !important; color: #20364d !important; }
  th, td { border: 1px solid #c7d6e3 !important; padding: 6px 10px; color: #20364d !important; }
  th { background: #e7f0f7 !important; }
  tr:nth-child(even) td { background: #f4f8fb !important; }
  .NavFrame { border: 1px solid #c7d6e3 !important; border-radius: 6px; background: #ffffff !important; margin: 12px 0; overflow: hidden; }
  .NavHead { background: #e7f0f7 !important; color: #20364d !important; padding: 6px 10px !important; cursor: pointer !important; font-weight: 600; }
  .NavContent { background: #ffffff !important; }
  .vsToggleElement[style*='background'], th[class~='vsToggleElement'] { background: #e7f0f7 !important; color: #20364d !important; }
  .mw-collapsible-toggle { cursor: pointer; color: #47637c !important; }
  h1, h2, h3, h4, h5 { color: #20364d !important; border-bottom: 1px solid #c7d6e3 !important; padding-bottom: 4px; }
  #toc, .toc, .infobox { background: #ffffff !important; border: 1px solid #c7d6e3 !important; border-radius: 6px; }
  .mw-editsection, .mw-editsection-bracket { display: none !important; }
`,hn=12e3,v=se({__name:`ReviewQueue`,props:[`contest`,`assignedQueue`],setup(se){let v=se,y=ie(),gn=ue(`user`),b=_([]),x=_(null),S=_(``),C=_(``),w=_(!0),T=_(!1),E=_(!1),D=_(``),O=_(`list`),k=_(!1);_(!1);let _n=_(!0),vn=_(!1),A=_(!1),j=_(localStorage.getItem(`review_queue_theme`)||`light`),M=_(`judge`),N=_(gn?.value?.wiki_username||v.contest?.juries?.[0]||``),yn=()=>{j.value=j.value===`dark`?`light`:`dark`,localStorage.setItem(`review_queue_theme`,j.value)},bn=e=>!v.assignedQueue||!P.value.is_owner||M.value===`owner`?e:e.filter(e=>e.assigned_to===N.value),P=_({is_jury:!1,is_owner:!1}),xn=o(()=>P.value.is_jury||P.value.is_owner),F=_([]),I=_({pending:100,other:100,judged:100}),Sn=_(null),Cn=_(!1),L=_(null),wn=new Set,Tn=null,En=!1,R=_(``),z=0,Dn=async e=>{let t=++z;E.value=!0,R.value=``;try{let n=(await(await fetch(`https://bn.wiktionary.org/w/api.php?action=parse&page=${encodeURIComponent(e)}&format=json&prop=text&origin=*`)).json()).parse?.text?.[`*`]??`<p style="color:#94a3b8">Preview not available.</p>`;if(t!==z)return;R.value=`<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="utf-8">
<base href="https://bn.wiktionary.org/wiki/">
<style>${j.value===`light`?mn:fn}</style>
</head>
<body class="mw-body mw-parser-output">
${n}
<script>${pn}<\/script>
</body>
</html>`}catch(e){console.error(e);let n=j.value===`light`?`color:#20364d;background:#f5f8fb`:`color:oklch(0.96 0.02 264);background:oklch(0.1 0.01 264)`;t===z&&(R.value=`<!DOCTYPE html><html><body style="${n};padding:24px">Error loading preview.</body></html>`)}finally{t===z&&(E.value=!1)}};re(j,()=>{x.value?.title&&Dn(x.value.title)});let B=async(e=!0,t=!1)=>{e&&(w.value=!0),Tn?.abort(),Tn=new AbortController;let{signal:n}=Tn;try{if(!En){let e=await fetch(`/api/contests/${y.params.code}/my-role`,{signal:n});e.ok&&(P.value=await e.json()),En=!0}if(!xn.value){w.value=!1;return}if(v.assignedQueue){let e=P.value.is_owner&&M.value===`judge`&&N.value?`&view_as=${encodeURIComponent(N.value)}`:``,r=t&&Sn.value!==null?`&after_id=${Sn.value}`:``,i=`/api/jury-panel/contests/${y.params.code}/articles/page?page_size=250${r}${e}`,a=await fetch(i,{signal:n});if(a.ok){let e=await a.json(),n=bn(e.items||[]);Sn.value=e.next_after_id??null,Cn.value=!!e.has_more,L.value=e.status_counts?{total:e.total,...e.status_counts}:null,b.value=t?[...b.value,...n]:n}}else{let t=!0;await Ce(y.params.code,{signal:n,onPage:n=>{b.value=bn(n),t&&(t=!1,e&&(w.value=!1))}})}}catch(e){if(e.name===`AbortError`)return;console.error(`Failed to fetch articles`,e)}finally{n.aborted||(w.value=!1)}};re([M,N],()=>{v.assignedQueue&&P.value.is_owner&&B(!1)});let V=o(()=>gn.value?.wiki_username),H=o(()=>V.value?b.value.filter(e=>e.status===`pending`&&!(P.value.is_jury&&!P.value.is_owner&&e.submitted_by===V.value)&&!e.reviews.some(e=>e.reviewer===V.value)):[]),U=o(()=>H.value.filter(e=>!e.locked_by||e.locked_by===V.value)),W=o(()=>({total:L.value?.total??b.value.length,accepted:L.value?.accepted??b.value.filter(e=>e.status===`accepted`).length,rejected:L.value?.rejected??b.value.filter(e=>e.status===`rejected`).length,pending:L.value?.pending??b.value.filter(e=>e.status===`pending`).length})),On=o(()=>v.assignedQueue&&Cn.value),G=e=>{!e||wn.has(e)||fetch(`/api/articles/${e}/lock`,{method:`DELETE`}).catch(()=>{})},K=o(()=>V.value?b.value.filter(e=>e.reviews.some(e=>e.reviewer===V.value)):[]),q=o(()=>!V.value||!P.value.is_owner?[]:b.value.filter(e=>e.status!==`pending`&&e.reviews.length>0&&!e.reviews.some(e=>e.reviewer===V.value))),J=(e,t)=>t.slice(0,I.value[e]||100),kn=(e,t)=>J(e,t).length<t.length,An=(e,t)=>{I.value={...I.value,[e]:Math.min((I.value[e]||100)+100,t.length)}},jn=()=>{Cn.value&&!w.value&&B(!1,!0)},Y=e=>{let t=e.reviews.filter(e=>e.reviewer===V.value);return t.length?t[t.length-1].decision:null},Mn=e=>{let t=e.reviews.filter(e=>e.reviewer===V.value);return t.length&&t[t.length-1].comment||``},X=e=>{let t=e?.reviews?.some(e=>e.reviewer===V.value);!e||e.status!==`pending`&&!t||(D.value=``,x.value?.article_id&&x.value.article_id!==e?.article_id&&G(x.value.article_id),x.value=e,S.value=Mn(e),Dn(e.title),fetch(`/api/articles/${e.article_id}/lock`,{method:`POST`}).catch(()=>{}),O.value=`review`)},Nn,Pn=null,Fn=async()=>{try{let e=await fetch(`/api/contests/${y.params.code}/stats`);if(!e.ok)return;let t=await e.json();t.signature!==Pn&&(Pn=t.signature,await B(!1))}catch(e){console.error(`Failed to check review queue for updates`,e)}};oe(async()=>{await B(),Nn=setInterval(()=>{v.assignedQueue?B(!1).catch(e=>console.error(`Failed to refresh review queue`,e)):Fn()},5e3),U.value.length>0&&!x.value&&(X(U.value[0]),window.innerWidth<=768&&(O.value=`list`))});let In=()=>{if(!x.value)return;let e=x.value.article_id,t=U.value;if(t.length<=1)return;let n=(t.findIndex(t=>t.article_id===e)+1)%t.length;G(e),X(t[n])};re(O,e=>{e===`list`&&G(x.value?.article_id)}),d(()=>{Tn?.abort(),clearInterval(Nn),G(x.value?.article_id)});let Ln=async e=>{if(!x.value||T.value)return;T.value=!0,D.value=``;let t=x.value.article_id,n=x.value,r=S.value,i=U.value.findIndex(e=>e.article_id===t);try{let a=await fetch(`/api/articles/${t}/review`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({decision:e,comment:r})});if(!a.ok){let e=await a.json().catch(()=>({}));throw Error(e.detail||`Review failed (${a.status})`)}(e===`accepted`||e===`rejected`)&&wn.add(t),zn(n,e,r),S.value=``;let o={reviewer:V.value,decision:e,comment:r,reviewed_at:new Date().toISOString()};b.value=b.value.map(n=>n.article_id===t?{...n,status:e,reviews:[...n.reviews||[],o]}:n);let s=U.value,ee=s.length?s[Math.min(Math.max(i,0),s.length-1)]:null;ee?X(ee):(x.value=null,O.value=`list`),B(!1).catch(e=>console.warn(`Background queue refresh failed`,e))}catch(e){console.error(`Error submitting review`,e),D.value=e.message||`Review failed`}finally{T.value=!1}},Z=_(null),Q=_(!1),Rn,zn=(e,t,n)=>{clearTimeout(Rn),Z.value={articleId:e.article_id,title:e.title,decision:t,comment:n},Rn=setTimeout(()=>{Z.value=null},hn)},Bn=()=>{clearTimeout(Rn),Z.value=null},Vn=async()=>{let e=Z.value;if(!(!e||Q.value)){Q.value=!0,D.value=``;try{let t=await fetch(`/api/articles/${e.articleId}/review/undo`,{method:`POST`});if(!t.ok){let e=await t.json().catch(()=>({}));throw Error(e.detail||`Undo failed (${t.status})`)}let n=await t.json();wn.delete(e.articleId),b.value=b.value.map(t=>t.article_id===e.articleId?{...t,status:n.restored_status,reviews:(t.reviews||[]).filter(e=>e.reviewer!==V.value)}:t),Bn();let r=b.value.find(t=>t.article_id===e.articleId);r&&(X(r),S.value=e.comment||``),B(!1).catch(e=>console.warn(`Background queue refresh failed`,e))}catch(e){D.value=e.message||`Undo failed`}finally{Q.value=!1}}},$=_(!1),Hn=e=>{if(!e)return!1;let t=e.tagName;return t===`INPUT`||t===`TEXTAREA`||t===`SELECT`||e.isContentEditable},Un=e=>{if(!(e.ctrlKey||e.metaKey||e.altKey)){if(e.key===`Escape`){$.value?($.value=!1,e.preventDefault()):Hn(e.target)&&e.target.blur();return}if(!Hn(e.target)){if(e.key===`?`){$.value=!$.value,e.preventDefault();return}if(!$.value&&!(!x.value||T.value))switch(e.key.toLowerCase()){case`a`:e.preventDefault(),Ln(`accepted`);break;case`r`:e.preventDefault(),Ln(`rejected`);break;case`s`:e.preventDefault(),In();break;case`c`:e.preventDefault(),Wn.value?.focus();break;case`u`:e.preventDefault(),Vn();break;default:break}}}},Wn=_(null);oe(()=>window.addEventListener(`keydown`,Un)),d(()=>{window.removeEventListener(`keydown`,Un),clearTimeout(Rn)});let Gn=async e=>{if(!(!e||T.value)&&confirm(`Remove "${e.title}" from this contest?`)){T.value=!0;try{if(!(await fetch(`/api/articles/${e.article_id}`,{method:`DELETE`})).ok)throw Error(`Remove failed`);G(e.article_id),x.value?.article_id===e.article_id&&(x.value=null,O.value=`list`),await B(!1)}catch(e){console.error(`Error removing article`,e)}finally{T.value=!1}}},Kn=()=>Gn(x.value),qn=(e,t)=>{t.stopPropagation();let n=F.value.indexOf(e);n>-1?F.value.splice(n,1):F.value.push(e),F.value.length<2&&(C.value=``)},Jn=async e=>{if(T.value||!F.value.length)return;T.value=!0;let t=[],n=[...F.value],r=n.includes(x.value?.article_id),i=C.value.trim()||`Bulk reviewed`;try{let a=await fetch(`/api/articles/bulk-review`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({article_ids:n,decision:e,comment:i})}),o=await a.json().catch(()=>({}));if(!a.ok)throw Error(o.detail||`Bulk review failed`);for(let t of o.succeeded||[])(e===`accepted`||e===`rejected`)&&wn.add(t);t.push(...(o.failed||[]).map(e=>e.article_id)),F.value=[],C.value=``;let s=r&&!t.includes(x.value?.article_id);s&&(x.value=null,z++,R.value=``,E.value=!1),await B(!1),(s||!x.value||!U.value.find(e=>e.article_id===x.value.article_id))&&(U.value.length>0?X(U.value[0]):(x.value=null,O.value=`list`))}catch(e){console.error(`Bulk review failed`,e)}finally{t.length&&console.warn(`Bulk review: ${t.length} article(s) failed to update:`,t),T.value=!1}},Yn=async()=>{if(!(T.value||!F.value.length)&&confirm(`Remove ${F.value.length} article(s) from the contest?`)){T.value=!0;try{let e=[...F.value],t=await fetch(`/api/articles/bulk-delete`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({article_ids:e})}),n=await t.json().catch(()=>({}));if(!t.ok)throw Error(n.detail||`Bulk remove failed`);F.value=[],C.value=``,x.value=null,await B(!1),O.value=`list`}catch(e){console.error(`Bulk remove failed`,e)}finally{T.value=!1}}},Xn=e=>`${dn}${encodeURIComponent(e)}`;return o(()=>{if(!v.contest?.add_talk_template)return``;let e=v.contest.talk_template_name||``;e=e.trim(),e&&!e.startsWith(`{{`)&&(e=`{{${e}}}`);let t=``;return v.contest.include_talk_header&&(t+=`{{আলাপ পাতা}}

`),e&&(t+=e),t}),_(!1),(o,d)=>(f(),l(`div`,{class:n([`rq-app`,`rq-theme-${j.value}`])},[!w.value&&!xn.value?(f(),l(`div`,we,[...d[26]||=[h(`div`,{class:`rq-card-unauth`},[h(`div`,{class:`rq-icon-large`},`⛔`),h(`h2`,null,`Access Denied`),h(`p`,null,`This area is restricted to Contest Jury members and Owners.`)],-1)]])):w.value?(f(),l(`div`,Te,[...d[27]||=[h(`div`,{class:`rq-spinner`},null,-1),h(`p`,{class:`rq-loading-text`},`Loading review queue…`,-1)]])):(f(),l(`div`,{key:2,class:n([`rq-layout`,{"is-mobile-review":O.value===`review`}])},[h(`aside`,{class:n([`rq-panel rq-queue-panel`,{"mobile-hidden":O.value!==`list`,"is-collapsed":k.value}])},[h(`header`,Ee,[h(`div`,De,[d[28]||=h(`div`,{class:`rq-brand-eyebrow`},[h(`span`,{class:`rq-eyebrow-text`},`Jury Workspace`),h(`span`,{class:`rq-badge-live`},`Live`)],-1),h(`div`,Oe,[h(`button`,{class:`rq-theme-btn`,type:`button`,onClick:yn,"aria-label":j.value===`dark`?`Switch to light mode`:`Switch to dark mode`},[h(`span`,Ae,p(j.value===`dark`?`☀`:`◐`),1),s(` `+p(j.value===`dark`?`Light`:`Dark`),1)],8,ke),h(`button`,{class:`rq-icon-btn rq-desktop-only`,onClick:d[0]||=e=>k.value=!0,title:`Collapse Sidebar`},[e(r(g),{icon:r(fe)},null,8,[`icon`])])])]),d[34]||=h(`h2`,{class:`rq-panel-title`},`Review Queue`,-1),v.assignedQueue&&P.value.is_owner?(f(),l(`div`,je,[d[29]||=h(`span`,{class:`rq-owner-switcher-label`},`View as`,-1),h(`div`,Me,[h(`button`,{type:`button`,class:n({"is-active":M.value===`judge`}),onClick:d[1]||=e=>M.value=`judge`},`Judge`,2),h(`button`,{type:`button`,class:n({"is-active":M.value===`owner`}),onClick:d[2]||=e=>M.value=`owner`},`Owner`,2)]),M.value===`judge`?ae((f(),l(`select`,{key:0,"onUpdate:modelValue":d[3]||=e=>N.value=e,class:`rq-owner-judge-select`,"aria-label":`Choose jury member`},[(f(!0),l(i,null,m(v.contest?.juries||[],e=>(f(),l(`option`,{key:e,value:e},p(e),9,Ne))),128))],512)),[[t,N.value]]):u(``,!0)])):u(``,!0),h(`div`,Pe,[h(`div`,Fe,[h(`span`,Ie,p(W.value.total),1),d[30]||=h(`span`,{class:`rq-stat-lbl`},`Total`,-1)]),h(`div`,Le,[h(`span`,Re,p(W.value.pending),1),d[31]||=h(`span`,{class:`rq-stat-lbl`},`Pending`,-1)]),h(`div`,ze,[h(`span`,Be,p(W.value.accepted),1),d[32]||=h(`span`,{class:`rq-stat-lbl`},`OK`,-1)]),h(`div`,Ve,[h(`span`,He,p(W.value.rejected),1),d[33]||=h(`span`,{class:`rq-stat-lbl`},`Rej`,-1)])])]),e(ee,{name:`rq-fade`},{default:ce(()=>[F.value.length>0?(f(),l(`div`,Ue,[h(`span`,We,p(F.value.length)+` selected`,1),h(`div`,Ge,[h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-accept`,onClick:d[4]||=c(e=>Jn(`accepted`),[`prevent`]),title:`Accept`},[e(r(g),{icon:r(be)},null,8,[`icon`])]),h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-reject`,onClick:d[5]||=c(e=>Jn(`rejected`),[`prevent`]),title:`Reject`},[e(r(g),{icon:r(pe)},null,8,[`icon`])]),h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-remove`,onClick:c(Yn,[`prevent`]),title:`Remove`},[e(r(g),{icon:r(de)},null,8,[`icon`])])])])):u(``,!0)]),_:1}),F.value.length>1?(f(),l(`div`,Ke,[h(`div`,qe,[d[35]||=h(`span`,null,`Bulk review comment`,-1),h(`span`,Je,`Added to all `+p(F.value.length)+` selected articles`,1)]),ae(h(`textarea`,{"onUpdate:modelValue":d[6]||=e=>C.value=e,class:`rq-input rq-bulk-comment-input`,rows:`2`,placeholder:`Add comment`},null,512),[[te,C.value]])])):u(``,!0),h(`div`,Ye,[h(`div`,Xe,[h(`button`,{class:`rq-group-header`,onClick:d[7]||=e=>_n.value=!_n.value},[d[36]||=h(`div`,{class:`rq-group-header-left`},[h(`span`,{class:`rq-dot rq-dot-pending`}),h(`span`,{class:`rq-group-title`},`Pending Review`)],-1),e(r(g),{icon:r(ve),class:n([`rq-group-chevron`,{"is-open":_n.value}])},null,8,[`icon`,`class`])]),_n.value?(f(),l(`div`,Ze,[h(`div`,Qe,[h(`ul`,$e,[(f(!0),l(i,null,m(J(`pending`,H.value),e=>(f(),l(`li`,{key:e.article_id,class:n([`rq-list-item rq-item-pending`,{"is-active":x.value?.article_id===e.article_id,"is-locked":e.locked_by&&e.locked_by!==V.value}]),onClick:t=>X(e)},[h(`label`,{class:`rq-cb-wrapper`,onClick:d[8]||=c(()=>{},[`stop`])},[h(`input`,{type:`checkbox`,checked:F.value.includes(e.article_id),onChange:t=>qn(e.article_id,t),class:`rq-cb`},null,40,tt)]),h(`div`,nt,[h(`span`,rt,p(e.title),1),h(`span`,it,p(e.submitted_by),1)]),e.locked_by&&e.locked_by!==V.value?(f(),a(r(g),{key:0,icon:r(_e),class:`rq-icon-lock`,title:`Being reviewed by someone`},null,8,[`icon`])):u(``,!0)],10,et))),128)),H.value.length?u(``,!0):(f(),l(`li`,at,[e(r(g),{icon:r(xe),class:`rq-empty-icon`},null,8,[`icon`]),d[37]||=h(`span`,null,`All caught up!`,-1)])),kn(`pending`,H.value)?(f(),l(`li`,ot,[h(`button`,{type:`button`,class:`rq-load-more`,onClick:d[9]||=e=>An(`pending`,H.value)},`Show 100 more`)])):u(``,!0),!kn(`pending`,H.value)&&On.value?(f(),l(`li`,st,[h(`button`,{type:`button`,class:`rq-load-more`,onClick:jn},`Load next 250 articles from server`)])):u(``,!0)])])])):u(``,!0)]),q.value.length?(f(),l(`div`,ct,[h(`button`,{class:`rq-group-header`,onClick:d[10]||=e=>A.value=!A.value},[h(`div`,lt,[d[38]||=h(`span`,{class:`rq-dot rq-dot-other`},null,-1),d[39]||=h(`span`,{class:`rq-group-title`},`Other Judges`,-1),h(`span`,ut,p(q.value.length),1)]),e(r(g),{icon:r(ve),class:n([`rq-group-chevron`,{"is-open":A.value}])},null,8,[`icon`,`class`])]),A.value?(f(),l(`div`,dt,[h(`div`,ft,[h(`ul`,pt,[(f(!0),l(i,null,m(J(`other`,q.value),e=>(f(),l(`li`,{key:`other-${e.article_id}`,class:`rq-list-item rq-item-readonly`},[h(`div`,mt,[h(`span`,ht,p(e.title),1),h(`span`,gt,p(e.reviews.map(e=>e.reviewer).join(`, `)),1)])]))),128)),kn(`other`,q.value)?(f(),l(`li`,_t,[h(`button`,{class:`rq-load-more`,onClick:d[11]||=e=>An(`other`,q.value)},`Load 100 more`)])):u(``,!0)])])])):u(``,!0)])):u(``,!0),h(`div`,vt,[h(`button`,{class:`rq-group-header`,onClick:d[12]||=e=>vn.value=!vn.value},[h(`div`,yt,[d[40]||=h(`span`,{class:`rq-dot rq-dot-judged`},null,-1),d[41]||=h(`span`,{class:`rq-group-title`},`My Judged`,-1),h(`span`,bt,p(K.value.length),1)]),e(r(g),{icon:r(ve),class:n([`rq-group-chevron`,{"is-open":vn.value}])},null,8,[`icon`,`class`])]),vn.value?(f(),l(`div`,xt,[h(`div`,St,[h(`ul`,Ct,[(f(!0),l(i,null,m(J(`judged`,K.value),e=>(f(),l(`li`,{key:e.article_id,class:n([`rq-list-item`,[`rq-item-`+Y(e),{"is-active":x.value?.article_id===e.article_id}]]),onClick:t=>X(e)},[h(`div`,Tt,[h(`span`,Et,p(e.title),1),h(`span`,Dt,p(e.submitted_by),1)])],10,wt))),128)),K.value.length?u(``,!0):(f(),l(`li`,Ot,[...d[42]||=[h(`span`,null,`Nothing judged yet`,-1)]])),kn(`judged`,K.value)?(f(),l(`li`,kt,[h(`button`,{class:`rq-load-more`,onClick:d[13]||=e=>An(`judged`,K.value)},`Load 100 more`)])):u(``,!0)])])])):u(``,!0)])])],2),h(`div`,{class:n([`rq-review-area`,{"mobile-hidden":O.value!==`review`}])},[x.value?(f(),l(i,{key:1},[h(`main`,Nt,[h(`header`,Pt,[k.value?(f(),l(`button`,{key:0,class:`rq-hamburger-btn rq-desktop-only`,onClick:d[15]||=e=>k.value=!1,title:`Open Sidebar`},[e(r(g),{icon:r(ge)},null,8,[`icon`])])):u(``,!0),h(`button`,{class:`rq-back-btn rq-mobile-only`,onClick:d[16]||=e=>O.value=`list`},[e(r(g),{icon:r(ye)},null,8,[`icon`])]),h(`div`,Ft,[h(`a`,{href:Xn(x.value.title),target:`_blank`,class:`rq-article-title-link`,title:x.value.title},p(x.value.title),9,It),h(`div`,Lt,[h(`span`,Rt,`by `+p(x.value.submitted_by),1),x.value.wiki_creation_date?(f(),l(`span`,zt,p(r(le)(x.value.wiki_creation_date)),1)):u(``,!0),x.value.locked_by&&x.value.locked_by!==V.value?(f(),l(`span`,Bt,[e(r(g),{icon:r(_e)},null,8,[`icon`]),s(` `+p(x.value.locked_by)+` reviewing `,1)])):u(``,!0),Y(x.value)?(f(),l(`span`,{key:2,class:n([`rq-tag rq-tag-verdict`,`rq-tag-`+Y(x.value)])},p(Y(x.value)===`accepted`?`✓ Accepted`:Y(x.value)===`rejected`?`✕ Rejected`:`→ Skipped`),3)):u(``,!0)])]),h(`a`,{href:Xn(x.value.title),target:`_blank`,class:`rq-btn-secondary rq-wiki-link-btn`,title:`Open on Wiktionary`},[e(r(g),{icon:r(Se)},null,8,[`icon`]),d[46]||=s(),d[47]||=h(`span`,{class:`rq-desktop-only`},`Wiki`,-1)],8,Vt)]),h(`div`,Ht,[E.value?(f(),l(`div`,Ut,[...d[48]||=[h(`div`,{class:`rq-spinner rq-spinner-sm`},null,-1),h(`span`,{class:`rq-loading-text`},`Loading Wikipedia preview…`,-1)]])):(f(),l(`iframe`,{key:1,class:`rq-wiki-iframe`,sandbox:`allow-scripts`,srcdoc:R.value,referrerpolicy:`no-referrer`},null,8,Wt))])]),h(`footer`,Gt,[h(`div`,Kt,[D.value?(f(),l(`div`,qt,p(D.value),1)):u(``,!0),h(`div`,Jt,[ae(h(`textarea`,{ref_key:`commentBox`,ref:Wn,class:`rq-input rq-textarea`,"onUpdate:modelValue":d[17]||=e=>S.value=e,placeholder:`Leave a note for the submitter (optional)… (C)`,rows:`2`},null,512),[[te,S.value]]),h(`div`,Yt,[h(`div`,Xt,[h(`button`,{type:`button`,class:`rq-btn rq-btn-accept`,disabled:T.value,onClick:d[18]||=c(e=>Ln(`accepted`),[`prevent`]),title:`Accept (A)`},[e(r(g),{icon:r(be)},null,8,[`icon`]),d[49]||=s(),d[50]||=h(`span`,null,`Accept`,-1),d[51]||=s(),d[52]||=h(`kbd`,{class:`rq-kbd rq-desktop-only`},`A`,-1)],8,Zt),h(`button`,{type:`button`,class:`rq-btn rq-btn-reject`,disabled:T.value,onClick:d[19]||=c(e=>Ln(`rejected`),[`prevent`]),title:`Reject (R)`},[e(r(g),{icon:r(pe)},null,8,[`icon`]),d[53]||=s(),d[54]||=h(`span`,null,`Reject`,-1),d[55]||=s(),d[56]||=h(`kbd`,{class:`rq-kbd rq-desktop-only`},`R`,-1)],8,Qt)]),h(`div`,$t,[h(`button`,{class:`rq-btn-ghost rq-btn-skip`,disabled:T.value,onClick:In,title:`Skip (S)`},[e(r(g),{icon:r(he)},null,8,[`icon`]),d[57]||=s(),d[58]||=h(`span`,{class:`rq-desktop-only`},`Skip`,-1)],8,en),h(`button`,{class:`rq-btn-ghost rq-btn-remove`,disabled:T.value,onClick:Kn,title:`Delete article`},[e(r(g),{icon:r(de)},null,8,[`icon`]),d[59]||=s(),d[60]||=h(`span`,{class:`rq-desktop-only`},`Delete`,-1)],8,tn),h(`button`,{type:`button`,class:`rq-btn-ghost rq-btn-help rq-desktop-only`,title:`Keyboard shortcuts (?)`,"aria-label":`Keyboard shortcuts`,onClick:d[20]||=e=>$.value=!0},`?`)])])])])])],64)):(f(),l(`div`,At,[h(`div`,jt,[h(`div`,Mt,[e(r(g),{icon:r(xe)},null,8,[`icon`])]),d[44]||=h(`h3`,null,`Queue is Clear`,-1),d[45]||=h(`p`,null,`You have reviewed all available articles in your queue.`,-1),h(`button`,{class:`rq-btn-secondary`,onClick:d[14]||=e=>k.value=!1,style:{"margin-top":`16px`}},[e(r(g),{icon:r(ge)},null,8,[`icon`]),d[43]||=s(` Open Sidebar `,-1)])])]))],2)],2)),h(`nav`,nn,[h(`button`,{class:n([`rq-nav-btn`,{"is-active":O.value===`list`}]),onClick:d[21]||=e=>O.value=`list`},[e(r(g),{icon:r(ge),class:`rq-nav-icon`},null,8,[`icon`]),d[61]||=h(`span`,{class:`rq-nav-label`},`Queue`,-1),H.value.length?(f(),l(`span`,rn,p(H.value.length),1)):u(``,!0)],2),h(`button`,{class:n([`rq-nav-btn`,{"is-active":O.value===`review`}]),onClick:d[22]||=e=>O.value=`review`,disabled:!x.value},[e(r(g),{icon:r(me),class:`rq-nav-icon`},null,8,[`icon`]),d[62]||=h(`span`,{class:`rq-nav-label`},`Review`,-1)],10,an)]),Z.value?(f(),l(`div`,on,[h(`span`,sn,[h(`strong`,{class:n([`rq-undo-decision`,`rq-undo-${Z.value.decision}`])},p(Z.value.decision),3),h(`span`,cn,p(Z.value.title),1)]),h(`button`,{type:`button`,class:`rq-undo-btn`,disabled:Q.value,onClick:Vn},[s(p(Q.value?`Undoing…`:`Undo`)+` `,1),d[63]||=h(`kbd`,{class:`rq-kbd`},`U`,-1)],8,ln),h(`button`,{type:`button`,class:`rq-undo-dismiss`,"aria-label":`Dismiss`,onClick:Bn},`×`)])):u(``,!0),$.value?(f(),l(`div`,{key:4,class:`rq-help-backdrop`,onClick:d[25]||=e=>$.value=!1},[h(`div`,{class:`rq-help-panel`,role:`dialog`,"aria-label":`Keyboard shortcuts`,onClick:d[24]||=c(()=>{},[`stop`])},[h(`div`,un,[d[64]||=h(`h3`,null,`Keyboard shortcuts`,-1),h(`button`,{type:`button`,class:`rq-help-close`,"aria-label":`Close`,onClick:d[23]||=e=>$.value=!1},`×`)]),d[65]||=ne(`<dl class="rq-help-list" data-v-6f5031f8><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>A</kbd></dt><dd data-v-6f5031f8>Accept the current article</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>R</kbd></dt><dd data-v-6f5031f8>Reject the current article</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>S</kbd></dt><dd data-v-6f5031f8>Skip to the next article without deciding</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>C</kbd></dt><dd data-v-6f5031f8>Focus the comment box</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>U</kbd></dt><dd data-v-6f5031f8>Undo the last decision</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>Esc</kbd></dt><dd data-v-6f5031f8>Leave the comment box / close this panel</dd></div><div class="rq-help-row" data-v-6f5031f8><dt data-v-6f5031f8><kbd class="rq-kbd" data-v-6f5031f8>?</kbd></dt><dd data-v-6f5031f8>Show or hide this panel</dd></div></dl><p class="rq-help-note" data-v-6f5031f8>Shortcuts are ignored while you&#39;re typing in a text field.</p>`,2)])])):u(``,!0)],2))}},[[`__scopeId`,`data-v-6f5031f8`]]);export{v as default};