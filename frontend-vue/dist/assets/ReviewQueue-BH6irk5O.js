import{$ as e,B as t,Dt as n,Et as r,G as i,J as a,K as o,Q as s,R as c,V as ee,W as l,X as u,Y as d,Z as te,at as f,ct as p,ft as ne,h as re,kt as m,lt as ie,mt as ae,ot as oe,p as se,pt as ce,q as h,r as le,rt as ue,v as g,y as de,yt as _}from"./index-DsGNz7TJ.js";import{a as fe,c as pe,d as me,f as he,i as ge,l as _e,m as ve,n as ye,o as be,p as xe,r as Se,s as Ce,u as we}from"./codex-icons-DuTEl6KI.js";import{t as Te}from"./contestLog-BxXA8Hlw.js";var Ee={key:0,class:`rq-center-state`},De={key:1,class:`rq-center-state`},Oe={class:`rq-panel-header`},ke={class:`rq-panel-header-top`},Ae={class:`rq-header-actions`},je=[`aria-label`],Me={"aria-hidden":`true`},Ne={key:0,class:`rq-owner-switcher`},Pe={class:`rq-owner-mode-buttons`},Fe=[`value`],Ie={class:`rq-stats-strip`},Le={class:`rq-stat`},Re={class:`rq-stat-val`},ze={class:`rq-stat rq-stat-pending`},Be={class:`rq-stat-val`},Ve={class:`rq-stat rq-stat-ok`},He={class:`rq-stat-val`},Ue={class:`rq-stat rq-stat-rej`},We={class:`rq-stat-val`},Ge={key:0,class:`rq-bulk-banner`},Ke={class:`rq-bulk-count`},qe={class:`rq-bulk-actions`},Je={key:0,class:`rq-bulk-comment-panel`},Ye={class:`rq-bulk-comment-heading`},Xe={class:`rq-bulk-comment-hint`},Ze={class:`rq-panel-scroll`},Qe={class:`rq-group`},$e={key:0,class:`rq-group-content is-open`},et={class:`rq-group-inner`},tt={class:`rq-list`},nt=[`onClick`],rt=[`checked`,`onChange`],it={class:`rq-item-content`},at={class:`rq-item-title`},ot={class:`rq-item-meta`},st={key:0,class:`rq-list-empty`},ct={key:1,class:`rq-load-more-wrap`},lt={key:2,class:`rq-load-more-wrap`},ut={key:0,class:`rq-group`},dt={class:`rq-group-header-left`},ft={class:`rq-group-count`},pt={key:0,class:`rq-group-content is-open`},mt={class:`rq-group-inner`},ht={class:`rq-list`},gt={class:`rq-item-content`},_t={class:`rq-item-title`},vt={class:`rq-item-meta`},yt={key:0,class:`rq-load-more-wrap`},bt={class:`rq-group`},xt={class:`rq-group-header-left`},St={class:`rq-group-count`},Ct={key:0,class:`rq-group-content is-open`},wt={class:`rq-group-inner`},Tt={class:`rq-judged-search-wrap`},Et={class:`rq-list`},Dt=[`onClick`],Ot={class:`rq-item-content`},kt={class:`rq-item-title`},At={class:`rq-item-meta`},jt={key:0,class:`rq-list-empty`},Mt={key:1,class:`rq-load-more-wrap`},Nt={key:0,class:`rq-center-state rq-center-full rq-panel`},Pt={class:`rq-card-done`},Ft={class:`rq-done-icon`},It={class:`rq-panel rq-preview-panel`},Lt={class:`rq-article-header`},Rt={class:`rq-article-meta-area`},zt=[`href`,`title`],Bt={class:`rq-tags`},Vt={class:`rq-tag`},Ht={key:0,class:`rq-tag rq-tag-date`},Ut={key:1,class:`rq-tag rq-tag-locked`},Wt=[`href`],Gt={class:`rq-preview-container`},Kt={key:0,class:`rq-center-state`},qt=[`srcdoc`],Jt={class:`rq-panel rq-decision-panel`},Yt={class:`rq-decision-body`},Xt={key:0,class:`rq-error-msg`},Zt={class:`rq-decision-form`},Qt={class:`rq-actions-wrapper`},$t={class:`rq-primary-actions`},en=[`disabled`],tn=[`disabled`],nn={class:`rq-secondary-actions`},rn=[`disabled`],an=[`disabled`],on={class:`rq-mobile-nav`},sn={key:0,class:`rq-nav-badge`},cn=[`disabled`],ln={key:3,class:`rq-undo-toast`,role:`status`},un={class:`rq-undo-text`},dn={class:`rq-undo-title`},fn=[`disabled`],pn={class:`rq-help-header`},mn=`https://bn.wiktionary.org/wiki/`,hn=`
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
`,gn=`
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
`,_n=`
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
`,vn=12e3,v=se({__name:`ReviewQueue`,props:[`contest`,`assignedQueue`],setup(se){let v=se,y=re(),yn=ue(`user`),b=_([]),x=_(null),S=_(``),C=_(``),w=_(!0),T=_(!1),E=_(!1),D=_(``),O=_(`list`),k=_(!1);_(!1);let bn=_(!0),xn=_(!1),Sn=_(``),A=_(!1),j=_(localStorage.getItem(`review_queue_theme`)||`light`),M=_(`judge`),N=_(yn?.value?.wiki_username||v.contest?.juries?.[0]||``),Cn=()=>{j.value=j.value===`dark`?`light`:`dark`,localStorage.setItem(`review_queue_theme`,j.value)},wn=e=>!v.assignedQueue||!P.value.is_owner||M.value===`owner`?e:e.filter(e=>e.assigned_to===N.value),P=_({is_jury:!1,is_owner:!1}),Tn=o(()=>P.value.is_jury||P.value.is_owner),F=_([]),En=_({pending:100,other:100,judged:100}),I=_(null),L=_(!1),R=_(null),Dn=new Set,z=null,On=!1,B=null,V=_(``),H=0,kn=async e=>{let t=++H;E.value=!0,V.value=``;try{let n=(await(await fetch(`https://bn.wiktionary.org/w/api.php?action=parse&page=${encodeURIComponent(e)}&format=json&prop=text&origin=*`)).json()).parse?.text?.[`*`]??`<p style="color:#94a3b8">Preview not available.</p>`;if(t!==H)return;V.value=`<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="utf-8">
<base href="https://bn.wiktionary.org/wiki/">
<style>${j.value===`light`?_n:hn}</style>
</head>
<body class="mw-body mw-parser-output">
${n}
<script>${gn}<\/script>
</body>
</html>`}catch(e){console.error(e);let n=j.value===`light`?`color:#20364d;background:#f5f8fb`:`color:oklch(0.96 0.02 264);background:oklch(0.1 0.01 264)`;t===H&&(V.value=`<!DOCTYPE html><html><body style="${n};padding:24px">Error loading preview.</body></html>`)}finally{t===H&&(E.value=!1)}};ne(j,()=>{x.value?.title&&kn(x.value.title)});let U=async(e=!0,t=!1)=>{e&&(w.value=!0),z?.abort(),z=new AbortController;let{signal:n}=z;try{if(!On){let e=await fetch(`/api/contests/${y.params.code}/my-role`,{signal:n});e.ok&&(P.value=await e.json()),On=!0}if(!Tn.value){w.value=!1;return}if(v.assignedQueue){let e=P.value.is_owner&&M.value===`judge`&&N.value?`&view_as=${encodeURIComponent(N.value)}`:``,r=t&&I.value!==null?I.value:null,i=t?[...b.value]:[],a=!0;for(;a;){let t=r===null?``:`&after_id=${r}`,o=`/api/jury-panel/contests/${y.params.code}/articles/page?page_size=250${t}${e}`,s=await fetch(o,{signal:n});if(!s.ok)throw Error(`Queue fetch failed (${s.status})`);let c=await s.json(),ee=wn(c.items||[]),l=new Set(i.map(e=>e.article_id));i=[...i,...ee.filter(e=>!l.has(e.article_id))],b.value=i,I.value=c.next_after_id??r,L.value=!!c.has_more,R.value=c.status_counts?{total:c.total,...c.status_counts}:R.value,r=c.next_after_id??null,a=!!c.has_more&&!!c.items?.length&&r!==null}}else{let t=!0;await Te(y.params.code,{signal:n,onPage:n=>{b.value=wn(n),t&&(t=!1,e&&(w.value=!1))}})}}catch(e){if(e.name===`AbortError`)return;console.error(`Failed to fetch articles`,e)}finally{n.aborted||(w.value=!1)}};ne([M,N],()=>{v.assignedQueue&&P.value.is_owner&&U(!1)});let W=o(()=>yn.value?.wiki_username),G=o(()=>W.value?b.value.filter(e=>e.status===`pending`&&!(P.value.is_jury&&!P.value.is_owner&&e.submitted_by===W.value)&&!e.reviews.some(e=>e.reviewer===W.value)):[]),K=o(()=>G.value.filter(e=>!e.locked_by||e.locked_by===W.value)),An=o(()=>({total:R.value?.total??b.value.length,accepted:R.value?.accepted??b.value.filter(e=>e.status===`accepted`).length,rejected:R.value?.rejected??b.value.filter(e=>e.status===`rejected`).length,pending:R.value?.pending??b.value.filter(e=>e.status===`pending`).length})),jn=o(()=>v.assignedQueue&&L.value),q=e=>{!e||Dn.has(e)||fetch(`/api/articles/${e}/lock`,{method:`DELETE`}).catch(()=>{})},Mn=o(()=>W.value?b.value.filter(e=>e.reviews.some(e=>e.reviewer===W.value)):[]),Nn=o(()=>{let e=Sn.value.trim().toLocaleLowerCase();return e?Mn.value.filter(t=>t.title.toLocaleLowerCase().includes(e)):Mn.value}),J=o(()=>!W.value||!P.value.is_owner?[]:b.value.filter(e=>e.status!==`pending`&&e.reviews.length>0&&!e.reviews.some(e=>e.reviewer===W.value))),Pn=(e,t)=>t.slice(0,En.value[e]||100),Fn=(e,t)=>Pn(e,t).length<t.length,In=(e,t)=>{En.value={...En.value,[e]:Math.min((En.value[e]||100)+100,t.length)}},Ln=()=>{L.value&&!w.value&&U(!1,!0)},Rn=async(e=1)=>{if(!(!v.assignedQueue||!L.value||I.value===null))return B||(B=(async()=>{try{for(let t=0;t<e&&L.value;t+=1){let e=P.value.is_owner&&M.value===`judge`&&N.value?`&view_as=${encodeURIComponent(N.value)}`:``,t=await fetch(`/api/jury-panel/contests/${y.params.code}/articles/page?page_size=1&after_id=${I.value}${e}`);if(!t.ok)throw Error(`Queue refill failed (${t.status})`);let n=await t.json(),r=wn(n.items||[]);I.value=n.next_after_id??I.value,L.value=!!n.has_more&&r.length>0,n.status_counts&&(R.value={total:n.total,...n.status_counts});let i=new Set(b.value.map(e=>e.article_id));if(b.value=[...b.value,...r.filter(e=>!i.has(e.article_id))],!n.items?.length)break}}catch(e){console.warn(`Background queue refill failed`,e)}finally{B=null}})(),B)},Y=e=>{let t=e.reviews.filter(e=>e.reviewer===W.value);return t.length?t[t.length-1].decision:null},zn=e=>{let t=e.reviews.filter(e=>e.reviewer===W.value);return t.length&&t[t.length-1].comment||``},X=e=>{let t=e?.reviews?.some(e=>e.reviewer===W.value);!e||e.status!==`pending`&&!t||(D.value=``,x.value?.article_id&&x.value.article_id!==e?.article_id&&q(x.value.article_id),x.value=e,S.value=zn(e),kn(e.title),fetch(`/api/articles/${e.article_id}/lock`,{method:`POST`}).catch(()=>{}),O.value=`review`)},Bn,Vn=null,Hn=async()=>{try{let e=await fetch(`/api/contests/${y.params.code}/stats`);if(!e.ok)return;let t=await e.json();t.signature!==Vn&&(Vn=t.signature,await U(!1))}catch(e){console.error(`Failed to check review queue for updates`,e)}};oe(async()=>{await U(),Bn=setInterval(()=>{v.assignedQueue||Hn()},5e3),K.value.length>0&&!x.value&&(X(K.value[0]),window.innerWidth<=768&&(O.value=`list`))});let Un=()=>{if(!x.value)return;let e=x.value.article_id,t=K.value;if(t.length<=1)return;let n=(t.findIndex(t=>t.article_id===e)+1)%t.length;q(e),X(t[n])};ne(O,e=>{e===`list`&&q(x.value?.article_id)}),f(()=>{z?.abort(),clearInterval(Bn),q(x.value?.article_id)});let Wn=async e=>{if(!x.value||T.value)return;T.value=!0,D.value=``;let t=x.value.article_id,n=x.value,r=S.value,i=K.value.findIndex(e=>e.article_id===t);try{let a=await fetch(`/api/articles/${t}/review`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({decision:e,comment:r})});if(!a.ok){let e=await a.json().catch(()=>({}));throw Error(e.detail||`Review failed (${a.status})`)}(e===`accepted`||e===`rejected`)&&Dn.add(t),Kn(n,e,r),S.value=``;let o={reviewer:W.value,decision:e,comment:r,reviewed_at:new Date().toISOString()};b.value=b.value.map(n=>n.article_id===t?{...n,status:e,reviews:[...n.reviews||[],o]}:n);let s=K.value,c=s.length?s[Math.min(Math.max(i,0),s.length-1)]:null;c?X(c):(x.value=null,O.value=`list`),v.assignedQueue?Rn():U(!1).catch(e=>console.warn(`Background queue refresh failed`,e))}catch(e){console.error(`Error submitting review`,e),D.value=e.message||`Review failed`}finally{T.value=!1}},Z=_(null),Q=_(!1),Gn,Kn=(e,t,n)=>{clearTimeout(Gn),Z.value={articleId:e.article_id,title:e.title,decision:t,comment:n},Gn=setTimeout(()=>{Z.value=null},vn)},qn=()=>{clearTimeout(Gn),Z.value=null},Jn=async()=>{let e=Z.value;if(!(!e||Q.value)){Q.value=!0,D.value=``;try{let t=await fetch(`/api/articles/${e.articleId}/review/undo`,{method:`POST`});if(!t.ok){let e=await t.json().catch(()=>({}));throw Error(e.detail||`Undo failed (${t.status})`)}let n=await t.json();Dn.delete(e.articleId),b.value=b.value.map(t=>t.article_id===e.articleId?{...t,status:n.restored_status,reviews:(t.reviews||[]).filter(e=>e.reviewer!==W.value)}:t),qn();let r=b.value.find(t=>t.article_id===e.articleId);r&&(X(r),S.value=e.comment||``),U(!1).catch(e=>console.warn(`Background queue refresh failed`,e))}catch(e){D.value=e.message||`Undo failed`}finally{Q.value=!1}}},$=_(!1),Yn=e=>{if(!e)return!1;let t=e.tagName;return t===`INPUT`||t===`TEXTAREA`||t===`SELECT`||e.isContentEditable},Xn=e=>{if(!(e.ctrlKey||e.metaKey||e.altKey)){if(e.key===`Escape`){$.value?($.value=!1,e.preventDefault()):Yn(e.target)&&e.target.blur();return}if(!Yn(e.target)){if(e.key===`?`){$.value=!$.value,e.preventDefault();return}if(!$.value&&!(!x.value||T.value))switch(e.key.toLowerCase()){case`a`:e.preventDefault(),Wn(`accepted`);break;case`r`:e.preventDefault(),Wn(`rejected`);break;case`s`:e.preventDefault(),Un();break;case`c`:e.preventDefault(),Zn.value?.focus();break;case`u`:e.preventDefault(),Jn();break;default:break}}}},Zn=_(null);oe(()=>window.addEventListener(`keydown`,Xn)),f(()=>{window.removeEventListener(`keydown`,Xn),clearTimeout(Gn)});let Qn=async e=>{if(!(!e||T.value)&&confirm(`Remove "${e.title}" from this contest?`)){T.value=!0;try{if(!(await fetch(`/api/articles/${e.article_id}`,{method:`DELETE`})).ok)throw Error(`Remove failed`);q(e.article_id),x.value?.article_id===e.article_id&&(x.value=null,O.value=`list`),await U(!1)}catch(e){console.error(`Error removing article`,e)}finally{T.value=!1}}},$n=()=>Qn(x.value),er=(e,t)=>{t.stopPropagation();let n=F.value.indexOf(e);n>-1?F.value.splice(n,1):F.value.push(e),F.value.length<2&&(C.value=``)},tr=async e=>{if(T.value||!F.value.length)return;T.value=!0;let t=[],n=[...F.value],r=n.includes(x.value?.article_id),i=C.value.trim()||`Bulk reviewed`;try{let a=await fetch(`/api/articles/bulk-review`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({article_ids:n,decision:e,comment:i})}),o=await a.json().catch(()=>({}));if(!a.ok)throw Error(o.detail||`Bulk review failed`);for(let t of o.succeeded||[])(e===`accepted`||e===`rejected`)&&Dn.add(t);t.push(...(o.failed||[]).map(e=>e.article_id)),F.value=[],C.value=``;let s=r&&!t.includes(x.value?.article_id);s&&(x.value=null,H++,V.value=``,E.value=!1),await U(!1),(s||!x.value||!K.value.find(e=>e.article_id===x.value.article_id))&&(K.value.length>0?X(K.value[0]):(x.value=null,O.value=`list`))}catch(e){console.error(`Bulk review failed`,e)}finally{t.length&&console.warn(`Bulk review: ${t.length} article(s) failed to update:`,t),T.value=!1}},nr=async()=>{if(!(T.value||!F.value.length)&&confirm(`Remove ${F.value.length} article(s) from the contest?`)){T.value=!0;try{let e=[...F.value],t=await fetch(`/api/articles/bulk-delete`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({article_ids:e})}),n=await t.json().catch(()=>({}));if(!t.ok)throw Error(n.detail||`Bulk remove failed`);F.value=[],C.value=``,x.value=null,await U(!1),O.value=`list`}catch(e){console.error(`Bulk remove failed`,e)}finally{T.value=!1}}},rr=e=>`${mn}${encodeURIComponent(e)}`;return o(()=>{if(!v.contest?.add_talk_template)return``;let e=v.contest.talk_template_name||``;e=e.trim(),e&&!e.startsWith(`{{`)&&(e=`{{${e}}}`);let t=``;return v.contest.include_talk_header&&(t+=`{{আলাপ পাতা}}

`),e&&(t+=e),t}),_(!1),(o,f)=>(p(),u(`div`,{class:n([`rq-app`,`rq-theme-${j.value}`])},[!w.value&&!Tn.value?(p(),u(`div`,Ee,[...f[27]||=[h(`div`,{class:`rq-card-unauth`},[h(`div`,{class:`rq-icon-large`},`⛔`),h(`h2`,null,`Access Denied`),h(`p`,null,`This area is restricted to Contest Jury members and Owners.`)],-1)]])):w.value?(p(),u(`div`,De,[...f[28]||=[h(`div`,{class:`rq-spinner`},null,-1),h(`p`,{class:`rq-loading-text`},`Loading review queue…`,-1)]])):(p(),u(`div`,{key:2,class:n([`rq-layout`,{"is-mobile-review":O.value===`review`}])},[h(`aside`,{class:n([`rq-panel rq-queue-panel`,{"mobile-hidden":O.value!==`list`,"is-collapsed":k.value}])},[h(`header`,Oe,[h(`div`,ke,[f[29]||=h(`div`,{class:`rq-brand-eyebrow`},[h(`span`,{class:`rq-eyebrow-text`},`Jury Workspace`),h(`span`,{class:`rq-badge-live`},`Live`)],-1),h(`div`,Ae,[h(`button`,{class:`rq-theme-btn`,type:`button`,onClick:Cn,"aria-label":j.value===`dark`?`Switch to light mode`:`Switch to dark mode`},[h(`span`,Me,m(j.value===`dark`?`☀`:`◐`),1),s(` `+m(j.value===`dark`?`Light`:`Dark`),1)],8,je),h(`button`,{class:`rq-icon-btn rq-desktop-only`,onClick:f[0]||=e=>k.value=!0,title:`Collapse Sidebar`},[e(r(g),{icon:r(_e)},null,8,[`icon`])])])]),f[35]||=h(`h2`,{class:`rq-panel-title`},`Review Queue`,-1),v.assignedQueue&&P.value.is_owner?(p(),u(`div`,Ne,[f[30]||=h(`span`,{class:`rq-owner-switcher-label`},`View as`,-1),h(`div`,Pe,[h(`button`,{type:`button`,class:n({"is-active":M.value===`judge`}),onClick:f[1]||=e=>M.value=`judge`},`Judge`,2),h(`button`,{type:`button`,class:n({"is-active":M.value===`owner`}),onClick:f[2]||=e=>M.value=`owner`},`Owner`,2)]),M.value===`judge`?ae((p(),u(`select`,{key:0,"onUpdate:modelValue":f[3]||=e=>N.value=e,class:`rq-owner-judge-select`,"aria-label":`Choose jury member`},[(p(!0),u(i,null,ie(v.contest?.juries||[],e=>(p(),u(`option`,{key:e,value:e},m(e),9,Fe))),128))],512)),[[t,N.value]]):d(``,!0)])):d(``,!0),h(`div`,Ie,[h(`div`,Le,[h(`span`,Re,m(An.value.total),1),f[31]||=h(`span`,{class:`rq-stat-lbl`},`Total`,-1)]),h(`div`,ze,[h(`span`,Be,m(An.value.pending),1),f[32]||=h(`span`,{class:`rq-stat-lbl`},`Pending`,-1)]),h(`div`,Ve,[h(`span`,He,m(An.value.accepted),1),f[33]||=h(`span`,{class:`rq-stat-lbl`},`OK`,-1)]),h(`div`,Ue,[h(`span`,We,m(An.value.rejected),1),f[34]||=h(`span`,{class:`rq-stat-lbl`},`Rej`,-1)])])]),e(c,{name:`rq-fade`},{default:ce(()=>[F.value.length>0?(p(),u(`div`,Ge,[h(`span`,Ke,m(F.value.length)+` selected`,1),h(`div`,qe,[h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-accept`,onClick:f[4]||=l(e=>tr(`accepted`),[`prevent`]),title:`Accept`},[e(r(g),{icon:r(ge)},null,8,[`icon`])]),h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-reject`,onClick:f[5]||=l(e=>tr(`rejected`),[`prevent`]),title:`Reject`},[e(r(g),{icon:r(he)},null,8,[`icon`])]),h(`button`,{type:`button`,class:`rq-bbtn rq-bbtn-remove`,onClick:l(nr,[`prevent`]),title:`Remove`},[e(r(g),{icon:r(be)},null,8,[`icon`])])])])):d(``,!0)]),_:1}),F.value.length>1?(p(),u(`div`,Je,[h(`div`,Ye,[f[36]||=h(`span`,null,`Bulk review comment`,-1),h(`span`,Xe,`Added to all `+m(F.value.length)+` selected articles`,1)]),ae(h(`textarea`,{"onUpdate:modelValue":f[6]||=e=>C.value=e,class:`rq-input rq-bulk-comment-input`,rows:`2`,placeholder:`Add comment`},null,512),[[ee,C.value]])])):d(``,!0),h(`div`,Ze,[h(`div`,Qe,[h(`button`,{class:`rq-group-header`,onClick:f[7]||=e=>bn.value=!bn.value},[f[37]||=h(`div`,{class:`rq-group-header-left`},[h(`span`,{class:`rq-dot rq-dot-pending`}),h(`span`,{class:`rq-group-title`},`Pending Review`)],-1),e(r(g),{icon:r(Ce),class:n([`rq-group-chevron`,{"is-open":bn.value}])},null,8,[`icon`,`class`])]),bn.value?(p(),u(`div`,$e,[h(`div`,et,[h(`ul`,tt,[(p(!0),u(i,null,ie(Pn(`pending`,G.value),e=>(p(),u(`li`,{key:e.article_id,class:n([`rq-list-item rq-item-pending`,{"is-active":x.value?.article_id===e.article_id,"is-locked":e.locked_by&&e.locked_by!==W.value}]),onClick:t=>X(e)},[h(`label`,{class:`rq-cb-wrapper`,onClick:f[8]||=l(()=>{},[`stop`])},[h(`input`,{type:`checkbox`,checked:F.value.includes(e.article_id),onChange:t=>er(e.article_id,t),class:`rq-cb`},null,40,rt)]),h(`div`,it,[h(`span`,at,m(e.title),1),h(`span`,ot,m(e.submitted_by),1)]),e.locked_by&&e.locked_by!==W.value?(p(),a(r(g),{key:0,icon:r(Se),class:`rq-icon-lock`,title:`Being reviewed by someone`},null,8,[`icon`])):d(``,!0)],10,nt))),128)),G.value.length?d(``,!0):(p(),u(`li`,st,[e(r(g),{icon:r(pe),class:`rq-empty-icon`},null,8,[`icon`]),f[38]||=h(`span`,null,`All caught up!`,-1)])),Fn(`pending`,G.value)?(p(),u(`li`,ct,[h(`button`,{type:`button`,class:`rq-load-more`,onClick:f[9]||=e=>In(`pending`,G.value)},`Show 100 more`)])):d(``,!0),!Fn(`pending`,G.value)&&jn.value?(p(),u(`li`,lt,[h(`button`,{type:`button`,class:`rq-load-more`,onClick:Ln},`Load next 250 articles from server`)])):d(``,!0)])])])):d(``,!0)]),J.value.length?(p(),u(`div`,ut,[h(`button`,{class:`rq-group-header`,onClick:f[10]||=e=>A.value=!A.value},[h(`div`,dt,[f[39]||=h(`span`,{class:`rq-dot rq-dot-other`},null,-1),f[40]||=h(`span`,{class:`rq-group-title`},`Other Judges`,-1),h(`span`,ft,m(J.value.length),1)]),e(r(g),{icon:r(Ce),class:n([`rq-group-chevron`,{"is-open":A.value}])},null,8,[`icon`,`class`])]),A.value?(p(),u(`div`,pt,[h(`div`,mt,[h(`ul`,ht,[(p(!0),u(i,null,ie(Pn(`other`,J.value),e=>(p(),u(`li`,{key:`other-${e.article_id}`,class:`rq-list-item rq-item-readonly`},[h(`div`,gt,[h(`span`,_t,m(e.title),1),h(`span`,vt,m(e.reviews.map(e=>e.reviewer).join(`, `)),1)])]))),128)),Fn(`other`,J.value)?(p(),u(`li`,yt,[h(`button`,{class:`rq-load-more`,onClick:f[11]||=e=>In(`other`,J.value)},`Load 100 more`)])):d(``,!0)])])])):d(``,!0)])):d(``,!0),h(`div`,bt,[h(`button`,{class:`rq-group-header`,onClick:f[12]||=e=>xn.value=!xn.value},[h(`div`,xt,[f[41]||=h(`span`,{class:`rq-dot rq-dot-judged`},null,-1),f[42]||=h(`span`,{class:`rq-group-title`},`My Judged`,-1),h(`span`,St,m(Mn.value.length),1)]),e(r(g),{icon:r(Ce),class:n([`rq-group-chevron`,{"is-open":xn.value}])},null,8,[`icon`,`class`])]),xn.value?(p(),u(`div`,Ct,[h(`div`,wt,[h(`div`,Tt,[e(r(de),{modelValue:Sn.value,"onUpdate:modelValue":f[13]||=e=>Sn.value=e,class:`rq-judged-search`,placeholder:`Search judged articles`,"aria-label":`Search judged articles`,"start-icon":r(ye),clearable:``},null,8,[`modelValue`,`start-icon`])]),h(`ul`,Et,[(p(!0),u(i,null,ie(Pn(`judged`,Nn.value),e=>(p(),u(`li`,{key:e.article_id,class:n([`rq-list-item`,[`rq-item-`+Y(e),{"is-active":x.value?.article_id===e.article_id}]]),onClick:t=>X(e)},[h(`div`,Ot,[h(`span`,kt,m(e.title),1),h(`span`,At,m(e.submitted_by),1)])],10,Dt))),128)),Nn.value.length?d(``,!0):(p(),u(`li`,jt,[h(`span`,null,m(Sn.value?`No matching judged articles`:`Nothing judged yet`),1)])),Fn(`judged`,Nn.value)?(p(),u(`li`,Mt,[h(`button`,{class:`rq-load-more`,onClick:f[14]||=e=>In(`judged`,Mn.value)},`Load 100 more`)])):d(``,!0)])])])):d(``,!0)])])],2),h(`div`,{class:n([`rq-review-area`,{"mobile-hidden":O.value!==`review`}])},[x.value?(p(),u(i,{key:1},[h(`main`,It,[h(`header`,Lt,[k.value?(p(),u(`button`,{key:0,class:`rq-hamburger-btn rq-desktop-only`,onClick:f[16]||=e=>k.value=!1,title:`Open Sidebar`},[e(r(g),{icon:r(we)},null,8,[`icon`])])):d(``,!0),h(`button`,{class:`rq-back-btn rq-mobile-only`,onClick:f[17]||=e=>O.value=`list`},[e(r(g),{icon:r(ve)},null,8,[`icon`])]),h(`div`,Rt,[h(`a`,{href:rr(x.value.title),target:`_blank`,class:`rq-article-title-link`,title:x.value.title},m(x.value.title),9,zt),h(`div`,Bt,[h(`span`,Vt,`by `+m(x.value.submitted_by),1),x.value.wiki_creation_date?(p(),u(`span`,Ht,m(r(le)(x.value.wiki_creation_date)),1)):d(``,!0),x.value.locked_by&&x.value.locked_by!==W.value?(p(),u(`span`,Ut,[e(r(g),{icon:r(Se)},null,8,[`icon`]),s(` `+m(x.value.locked_by)+` reviewing `,1)])):d(``,!0),Y(x.value)?(p(),u(`span`,{key:2,class:n([`rq-tag rq-tag-verdict`,`rq-tag-`+Y(x.value)])},m(Y(x.value)===`accepted`?`✓ Accepted`:Y(x.value)===`rejected`?`✕ Rejected`:`→ Skipped`),3)):d(``,!0)])]),h(`a`,{href:rr(x.value.title),target:`_blank`,class:`rq-btn-secondary rq-wiki-link-btn`,title:`Open on Wiktionary`},[e(r(g),{icon:r(me)},null,8,[`icon`]),f[46]||=s(),f[47]||=h(`span`,{class:`rq-desktop-only`},`Wiki`,-1)],8,Wt)]),h(`div`,Gt,[E.value?(p(),u(`div`,Kt,[...f[48]||=[h(`div`,{class:`rq-spinner rq-spinner-sm`},null,-1),h(`span`,{class:`rq-loading-text`},`Loading Wikipedia preview…`,-1)]])):(p(),u(`iframe`,{key:1,class:`rq-wiki-iframe`,sandbox:`allow-scripts`,srcdoc:V.value,referrerpolicy:`no-referrer`},null,8,qt))])]),h(`footer`,Jt,[h(`div`,Yt,[D.value?(p(),u(`div`,Xt,m(D.value),1)):d(``,!0),h(`div`,Zt,[ae(h(`textarea`,{ref_key:`commentBox`,ref:Zn,class:`rq-input rq-textarea`,"onUpdate:modelValue":f[18]||=e=>S.value=e,placeholder:`Leave a note for the submitter (optional)… (C)`,rows:`2`},null,512),[[ee,S.value]]),h(`div`,Qt,[h(`div`,$t,[h(`button`,{type:`button`,class:`rq-btn rq-btn-accept`,disabled:T.value,onClick:f[19]||=l(e=>Wn(`accepted`),[`prevent`]),title:`Accept (A)`},[e(r(g),{icon:r(ge)},null,8,[`icon`]),f[49]||=s(),f[50]||=h(`span`,null,`Accept`,-1),f[51]||=s(),f[52]||=h(`kbd`,{class:`rq-kbd rq-desktop-only`},`A`,-1)],8,en),h(`button`,{type:`button`,class:`rq-btn rq-btn-reject`,disabled:T.value,onClick:f[20]||=l(e=>Wn(`rejected`),[`prevent`]),title:`Reject (R)`},[e(r(g),{icon:r(he)},null,8,[`icon`]),f[53]||=s(),f[54]||=h(`span`,null,`Reject`,-1),f[55]||=s(),f[56]||=h(`kbd`,{class:`rq-kbd rq-desktop-only`},`R`,-1)],8,tn)]),h(`div`,nn,[h(`button`,{class:`rq-btn-ghost rq-btn-skip`,disabled:T.value,onClick:Un,title:`Skip (S)`},[e(r(g),{icon:r(fe)},null,8,[`icon`]),f[57]||=s(),f[58]||=h(`span`,{class:`rq-desktop-only`},`Skip`,-1)],8,rn),h(`button`,{class:`rq-btn-ghost rq-btn-remove`,disabled:T.value,onClick:$n,title:`Delete article`},[e(r(g),{icon:r(be)},null,8,[`icon`]),f[59]||=s(),f[60]||=h(`span`,{class:`rq-desktop-only`},`Delete`,-1)],8,an),h(`button`,{type:`button`,class:`rq-btn-ghost rq-btn-help rq-desktop-only`,title:`Keyboard shortcuts (?)`,"aria-label":`Keyboard shortcuts`,onClick:f[21]||=e=>$.value=!0},`?`)])])])])])],64)):(p(),u(`div`,Nt,[h(`div`,Pt,[h(`div`,Ft,[e(r(g),{icon:r(pe)},null,8,[`icon`])]),f[44]||=h(`h3`,null,`Queue is Clear`,-1),f[45]||=h(`p`,null,`You have reviewed all available articles in your queue.`,-1),h(`button`,{class:`rq-btn-secondary`,onClick:f[15]||=e=>k.value=!1,style:{"margin-top":`16px`}},[e(r(g),{icon:r(we)},null,8,[`icon`]),f[43]||=s(` Open Sidebar `,-1)])])]))],2)],2)),h(`nav`,on,[h(`button`,{class:n([`rq-nav-btn`,{"is-active":O.value===`list`}]),onClick:f[22]||=e=>O.value=`list`},[e(r(g),{icon:r(we),class:`rq-nav-icon`},null,8,[`icon`]),f[61]||=h(`span`,{class:`rq-nav-label`},`Queue`,-1),G.value.length?(p(),u(`span`,sn,m(G.value.length),1)):d(``,!0)],2),h(`button`,{class:n([`rq-nav-btn`,{"is-active":O.value===`review`}]),onClick:f[23]||=e=>O.value=`review`,disabled:!x.value},[e(r(g),{icon:r(xe),class:`rq-nav-icon`},null,8,[`icon`]),f[62]||=h(`span`,{class:`rq-nav-label`},`Review`,-1)],10,cn)]),Z.value?(p(),u(`div`,ln,[h(`span`,un,[h(`strong`,{class:n([`rq-undo-decision`,`rq-undo-${Z.value.decision}`])},m(Z.value.decision),3),h(`span`,dn,m(Z.value.title),1)]),h(`button`,{type:`button`,class:`rq-undo-btn`,disabled:Q.value,onClick:Jn},[s(m(Q.value?`Undoing…`:`Undo`)+` `,1),f[63]||=h(`kbd`,{class:`rq-kbd`},`U`,-1)],8,fn),h(`button`,{type:`button`,class:`rq-undo-dismiss`,"aria-label":`Dismiss`,onClick:qn},`×`)])):d(``,!0),$.value?(p(),u(`div`,{key:4,class:`rq-help-backdrop`,onClick:f[26]||=e=>$.value=!1},[h(`div`,{class:`rq-help-panel`,role:`dialog`,"aria-label":`Keyboard shortcuts`,onClick:f[25]||=l(()=>{},[`stop`])},[h(`div`,pn,[f[64]||=h(`h3`,null,`Keyboard shortcuts`,-1),h(`button`,{type:`button`,class:`rq-help-close`,"aria-label":`Close`,onClick:f[24]||=e=>$.value=!1},`×`)]),f[65]||=te(`<dl class="rq-help-list" data-v-39a02d49><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>A</kbd></dt><dd data-v-39a02d49>Accept the current article</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>R</kbd></dt><dd data-v-39a02d49>Reject the current article</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>S</kbd></dt><dd data-v-39a02d49>Skip to the next article without deciding</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>C</kbd></dt><dd data-v-39a02d49>Focus the comment box</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>U</kbd></dt><dd data-v-39a02d49>Undo the last decision</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>Esc</kbd></dt><dd data-v-39a02d49>Leave the comment box / close this panel</dd></div><div class="rq-help-row" data-v-39a02d49><dt data-v-39a02d49><kbd class="rq-kbd" data-v-39a02d49>?</kbd></dt><dd data-v-39a02d49>Show or hide this panel</dd></div></dl><p class="rq-help-note" data-v-39a02d49>Shortcuts are ignored while you&#39;re typing in a text field.</p>`,2)])])):d(``,!0)],2))}},[[`__scopeId`,`data-v-39a02d49`]]);export{v as default};