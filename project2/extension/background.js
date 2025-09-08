const BUFFER_KEY = 'fb_buffer';
const SEND_INTERVAL_MS = 30 * 1000;
const SERVER_URL = 'http://localhost:8000/api/feedback';

function bufferFeedback(item) {
  chrome.storage.local.get(BUFFER_KEY, (res) => {
    const buf = res[BUFFER_KEY] || [];
    buf.push(item);
    chrome.storage.local.set({[BUFFER_KEY]: buf});
  });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResp) => {
  if(msg.type === 'user_feedback') {
    chrome.storage.local.get(['anon_id'], (res) => {
      let anon = res.anon_id;
      if(!anon) {
        anon = crypto.getRandomValues(new Uint32Array(4)).join('-');
        chrome.storage.local.set({anon_id: anon});
      }
      const item = {
        anon_id: anon,
        post_id: msg.postId,
        snippet: msg.snippet,
        label: msg.label,
        reason: msg.reason || null,
        url: sender.tab ? sender.tab.url : null,
        ts: new Date().toISOString()
      };
      bufferFeedback(item);
    });
  }
});

setInterval(async () => {
  chrome.storage.local.get(BUFFER_KEY, async (res) => {
    const buf = res[BUFFER_KEY] || [];
    if(buf.length === 0) return;
    const batch = buf.splice(0, 50);
    chrome.storage.local.set({[BUFFER_KEY]: buf});
    try {
      await fetch(SERVER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({items: batch, source: 'extension_v1'})
      });
    } catch(err) {
      console.error('send error', err);
      chrome.storage.local.get(BUFFER_KEY, (r) => {
        const cur = r[BUFFER_KEY] || [];
        chrome.storage.local.set({[BUFFER_KEY]: batch.concat(cur)});
      });
    }
  });
}, SEND_INTERVAL_MS);
