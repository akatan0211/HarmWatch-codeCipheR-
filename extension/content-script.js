// content-script.js

// --- helpers ---
function extractHashtags(text) {
  if (!text) return [];
  const set = new Set();
  const re = /#([^\s#.,!?;:()"'«»]+)/g;
  let m;
  while ((m = re.exec(text))) set.add('#' + m[1]);
  return Array.from(set);
}
function textFromNode(node) {
  if (!node) return '';
  return node.innerText || node.textContent || '';
}
function parseTimestampFromElement(el) {
  if (!el) return null;
  const attrs = ['datetime', 'data-time', 'data-timestamp', 'title'];
  for (const a of attrs) {
    const v = el.getAttribute && el.getAttribute(a);
    if (v) return v;
  }
  const txt = textFromNode(el).trim();
  return txt || null;
}
function buildNormalized(obj) {
  return {
    platform: obj.platform || 'unknown',
    post_id: obj.post_id || null,
    user_id: obj.user_id || null,
    timestamp: obj.timestamp || new Date().toISOString(),
    post_text: obj.post_text || '',
    hashtags: obj.hashtags || extractHashtags(obj.post_text || ''),
    likes: Number(obj.likes || 0),
    comments: Number(obj.comments || 0),
    shares: Number(obj.shares || 0),
    source_url: obj.source_url || window.location.href,
    category: obj.category || null,
    sentiment: obj.sentiment || null
  };
}

// --- simple platform extractors (best-effort) ---
function extractTwitter() {
  const article = document.querySelector('article[role="article"], article[data-testid="tweet"]');
  if (!article) return null;
  const content = article.querySelector('div[lang]') || article;
  const post_text = textFromNode(content);
  let user_id = null;
  const user = article.querySelector('a[href*="/"]');
  if (user) {
    const m = user.href.match(/twitter\.com\/([^\/?#]+)/);
    user_id = m ? m[1] : null;
  }
  let post_id = null;
  const timeLink = article.querySelector('a[href*="/status/"]') || article.querySelector('a time');
  if (timeLink) {
    const href = timeLink.closest('a')?.href || timeLink.href || '';
    const m = href.match(/status\/(\d+)/);
    if (m) post_id = m[1];
  }
  const timestamp = parseTimestampFromElement(article.querySelector('time'));
  return buildNormalized({ platform: 'twitter', post_id, user_id, timestamp, post_text });
}

function extractGeneric() {
  const metaDesc = document.querySelector('meta[property="og:description"]')?.content || document.querySelector('meta[name="description"]')?.content;
  const metaAuthor = document.querySelector('meta[name="author"]')?.content || null;
  let paragraphs = Array.from(document.querySelectorAll('p, article, div'));
  paragraphs = paragraphs.map(n => ({n, len: (n.innerText||'').length})).sort((a,b)=>b.len-a.len);
  const post_text = paragraphs.length ? (paragraphs[0].n.innerText || metaDesc || '') : (metaDesc || '');
  const hashtags = extractHashtags(post_text);
  return buildNormalized({ platform: 'generic', post_text, hashtags, user_id: metaAuthor });
}

// --- central extraction routine ---
async function extractAndSend() {
  const platformExtractors = [extractTwitter, extractGeneric];
  let result = null;
  for (const fn of platformExtractors) {
    try {
      const r = fn();
      if (r && r.post_text && r.post_text.trim().length > 0) { result = r; break; }
    } catch (e) { /* continue */ }
  }
  if (!result) result = extractGeneric();
  // normalize timestamp to ISO if possible
  if (result.timestamp && !/^\d{4}-\d{2}-\d{2}T/.test(result.timestamp)) {
    try { result.timestamp = new Date(result.timestamp).toISOString(); } catch {}
  }
  // send to background to buffer (don't POST directly here)
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'EXTRACTED_POST', payload: result }, (resp) => {
      if (chrome.runtime.lastError) {
        console.warn('Could not send extracted post to background:', chrome.runtime.lastError);
        resolve({ status: 'local_only', error: chrome.runtime.lastError.message, payload: result });
      } else {
        resolve(resp || { status: 'buffered_locally', payload: result });
      }
    });
  });
}

// expose for manual testing in console
window.extractAndSend = extractAndSend;

// listen for trigger from popup/background
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!(msg && msg.action === 'EXTRACT_AND_SEND')) return;
  let responded = false;
  const safeRespond = (p) => { if (responded) return; responded = true; try { sendResponse(p); } catch(e){ } };
  const timer = setTimeout(()=> safeRespond({ status: 'timeout' }), 8000);
  (async () => {
    try {
      const r = await extractAndSend();
      safeRespond({ status: 'ok', result: r });
    } catch (err) {
      safeRespond({ status: 'error', error: err && err.message });
    } finally {
      clearTimeout(timer);
    }
  })();
  return true;
});
