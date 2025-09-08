(() => {
  let injected = new Set();
  function getPosts() {
    const selectors = ['article', '#content', '.Post'];
    let nodes = [];
    selectors.forEach(s => {
      document.querySelectorAll(s).forEach(n => nodes.push(n));
    });
    return nodes;
  }
  function makePromptNode(textSnippet, postId) {
    const container = document.createElement('div');
    container.style.position = 'absolute';
    container.style.right = '8px';
    container.style.bottom = '8px';
    container.style.zIndex = 999999;
    container.style.background = 'rgba(255,255,255,0.95)';
    container.style.border = '1px solid #ccc';
    container.style.padding = '6px';
    container.style.borderRadius = '8px';
    container.style.fontSize = '12px';
    container.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
    const html = `
      <div style="display:flex;gap:6px;">
        <button class="fb-btn" data-label="agree">Agree</button>
        <button class="fb-btn" data-label="disagree">Disagree</button>
        <button class="fb-btn" data-label="spam">Spam</button>
        <button class="fb-btn" data-label="hate">Hate</button>
      </div>
      <div style="margin-top:4px;">
        <a class="fb-more" href="#" style="font-size:11px">More</a>
      </div>
    `;
    container.innerHTML = html;
    container.querySelectorAll('.fb-btn').forEach(b => {
      b.addEventListener('click', (e) => {
        const label = e.currentTarget.dataset.label;
        chrome.runtime.sendMessage({type:'user_feedback', postId: postId, label: label, snippet: textSnippet});
        container.innerHTML = '<div style="font-size:12px;color:green">Thanks — recorded</div>';
        setTimeout(()=>container.remove(), 1200);
      });
    });
    container.querySelector('.fb-more').addEventListener('click', (e) => {
      e.preventDefault();
      const reason = prompt('Optional reason / comment (visible to moderators):');
      chrome.runtime.sendMessage({type:'user_feedback', postId: postId, label: 'other', snippet: textSnippet, reason: reason});
      container.innerHTML = '<div style="font-size:12px;color:green">Thanks — recorded</div>';
      setTimeout(()=>container.remove(), 1200);
    });
    return container;
  }
  setInterval(() => {
    chrome.storage.local.get(['consent','freq','lastPrompt'], (res) => {
      if(!res.consent) return;
      const freq = res.freq || 10;
      const last = res.lastPrompt || 0;
      const now = Date.now();
      const cooldown = Math.max(60000, Math.floor(86400000 / freq));
      if(now - last < cooldown) return;
      const posts = getPosts();
      for(const p of posts) {
        try {
          if(injected.has(p)) continue;
          let snippet = p.innerText ? p.innerText.slice(0,300) : '';
          let postId = p.dataset.postId || (snippet.slice(0,60).trim().replace(/\s+/g,'_'));
          const node = makePromptNode(snippet, postId);
          p.style.position = p.style.position || 'relative';
          p.appendChild(node);
          injected.add(p);
          chrome.storage.local.set({lastPrompt: now});
          break;
        } catch(e) {
          console.error(e);
        }
      }
    });
  }, 5000);
})();
