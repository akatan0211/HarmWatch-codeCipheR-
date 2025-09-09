// popup.js
document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.getElementById('save');
  const consentEl = document.getElementById('consent');
  const freqEl = document.getElementById('freq');
  const status = document.getElementById('status');

  // load saved values
  chrome.storage.local.get(['consent','freq'], (res) => {
    if (res.consent !== undefined) consentEl.checked = !!res.consent;
    if (res.freq !== undefined) freqEl.value = String(res.freq);
  });

  saveBtn.addEventListener('click', async () => {
    const consent = consentEl.checked;
    const freq = parseInt(freqEl.value || '0', 10);
    await chrome.storage.local.set({ consent: consent, freq: freq, lastPrompt: 0 });
    status.textContent = 'Saved preferences.';
    setTimeout(() => status.textContent = '', 1500);
  });
});
