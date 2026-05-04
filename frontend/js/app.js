'use strict';

(function () {
  const dropZone    = document.getElementById('drop-zone');
  const fileInput   = document.getElementById('file-input');
  const dropLabel   = document.getElementById('drop-label');

  const errorPanel  = document.getElementById('error-panel');
  const errorList   = document.getElementById('error-list');
  const errorCount  = document.getElementById('error-count-label');

  const genericPanel = document.getElementById('generic-error-panel');
  const genericMsg   = document.getElementById('generic-error-msg');

  const previewPanel   = document.getElementById('preview-panel');
  const previewName    = document.getElementById('preview-workout-name');
  const previewSport   = document.getElementById('preview-sport');
  const previewSteps   = document.getElementById('preview-steps');

  const garminEmail    = document.getElementById('garmin-email');
  const garminPassword = document.getElementById('garmin-password');
  const pushBtn        = document.getElementById('push-btn');
  const pushBtnText    = pushBtn.querySelector('.btn-text');
  const pushBtnSpinner = pushBtn.querySelector('.btn-spinner');
  const pushSuccessPanel = document.getElementById('push-success-panel');
  const pushInfo         = document.getElementById('push-info');

  const pasteArea = document.getElementById('paste-area');

  let _pasteText        = null;  // set when user pastes; cleared when a file is chosen
  let _previewController = null;

  function getActiveFile() {
    if (_pasteText !== null) {
      const ext = _pasteText.trimStart().startsWith('<') ? 'xml' : 'json';
      return new File([_pasteText], `workout.${ext}`, {
        type: ext === 'json' ? 'application/json' : 'application/xml',
      });
    }
    return fileInput.files[0] || null;
  }

  // ── Paste input ────────────────────────────────────────────────────────────

  pasteArea.addEventListener('input', () => {
    const text = pasteArea.value;
    pasteArea.classList.toggle('has-content', text.trim().length > 0);
    if (!text.trim()) {
      _pasteText = null;
      updatePushBtn();
      clearPanels();
      return;
    }
    _pasteText = text;
    updatePushBtn();
    clearPanels();
    loadPreview();
  });

  // ── File selection ─────────────────────────────────────────────────────────

  fileInput.addEventListener('change', () => {
    const f = fileInput.files[0];
    if (f) {
      _pasteText = null;
      pasteArea.value = '';
      pasteArea.classList.remove('has-content');
      onFileChosen(f.name);
    }
  });

  function onFileChosen(name) {
    dropLabel.innerHTML = `Selected: <strong>${escapeHtml(name)}</strong>`;
    updatePushBtn();
    clearPanels();
    loadPreview();
  }

  function updatePushBtn() {
    const f        = getActiveFile();
    const isJson   = f && f.name.toLowerCase().endsWith('.json');
    const hasCreds = garminEmail.value.trim() && garminPassword.value.trim();
    pushBtn.disabled = !(isJson && hasCreds);
  }

  // ── Drag and drop ──────────────────────────────────────────────────────────

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (!f) return;
    // Feed the file into the hidden input for FormData
    const dt = new DataTransfer();
    dt.items.add(f);
    fileInput.files = dt.files;
    onFileChosen(f.name);
  });

  // Allow keyboard activation of drop zone
  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') fileInput.click();
  });
  dropZone.addEventListener('click', (e) => {
    // Only trigger if the click was on the drop zone itself, not the label/button inside it
    if (e.target === dropZone || e.target.classList.contains('drop-icon') ||
        e.target.classList.contains('drop-label') || e.target.classList.contains('drop-sub')) {
      fileInput.click();
    }
  });

  // ── Credential inputs enable push button ──────────────────────────────────

  garminEmail.addEventListener('input', updatePushBtn);
  garminPassword.addEventListener('input', updatePushBtn);

  // ── Push to Garmin ─────────────────────────────────────────────────────────

  pushBtn.addEventListener('click', async () => {
    const f = getActiveFile();
    if (!f) return;

    let workout;
    try {
      workout = JSON.parse(await f.text());
    } catch (_) {
      showGenericError('Could not parse the file as JSON.');
      return;
    }

    setPushLoading(true);
    clearPanels();

    try {
      const response = await fetch('/api/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email:   garminEmail.value.trim(),
          password: garminPassword.value,
          workout,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        pushInfo.textContent = `"${data.workout_name}" is now in your Garmin Connect account.`;
        showPanel(pushSuccessPanel);
      } else {
        let msg = `Error ${response.status}`;
        try {
          const d = await response.json();
          msg = d.detail?.message || d.message || msg;
        } catch (_) {}
        showGenericError(msg);
      }
    } catch (err) {
      showGenericError(`Network error: ${err.message}`);
    } finally {
      setPushLoading(false);
    }
  });

  function setPushLoading(on) {
    pushBtn.disabled    = on;
    pushBtnText.hidden  = on;
    pushBtnSpinner.hidden = !on;
  }

  // ── UI helpers ─────────────────────────────────────────────────────────────

  function clearPanels() {
    hidePanel(previewPanel);
    hidePanel(errorPanel);
    hidePanel(pushSuccessPanel);
    hidePanel(genericPanel);
    errorList.innerHTML = '';
    previewSteps.innerHTML = '';
  }

  async function loadPreview() {
    const f = getActiveFile();
    if (!f) return;

    if (_previewController) _previewController.abort();
    _previewController = new AbortController();
    const { signal } = _previewController;

    const formData = new FormData();
    formData.append('file', f);

    try {
      const response = await fetch('/api/preview', { method: 'POST', body: formData, signal });
      if (response.ok) {
        const data = await response.json();
        renderPreview(data);
      } else if (response.status === 422) {
        const data = await response.json();
        renderErrors(data.detail?.errors || data.errors || []);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        // Network errors are silent
      }
    }
  }

  function renderPreview(data) {
    previewName.textContent = data.name || 'Workout Preview';
    previewSport.textContent = data.sport || '';

    previewSteps.innerHTML = (data.steps || []).map((step) => `
      <tr data-intensity="${escapeHtml(step.intensity || '')}">
        <td class="preview-step-name">${escapeHtml(step.name)}</td>
        <td class="preview-duration">${escapeHtml(step.duration)}</td>
        <td class="preview-target">${escapeHtml(step.target)}</td>
      </tr>
    `).join('');

    showPanel(previewPanel);
  }

  function showPanel(el)  { el.hidden = false; }
  function hidePanel(el)  { el.hidden = true; }

  function renderErrors(errors) {
    if (!errors.length) {
      showGenericError('The server returned a validation error but no details were provided.');
      return;
    }
    errorCount.textContent = `${errors.length} validation error${errors.length !== 1 ? 's' : ''}`;
    errorList.innerHTML = errors.map((e) => `
      <li class="error-item">
        <code class="error-path">${escapeHtml(formatPath(e.path || '$'))}</code>
        <span class="error-msg">${escapeHtml(e.message || 'Unknown error')}</span>
      </li>
    `).join('');
    showPanel(errorPanel);
  }

  function showGenericError(msg) {
    genericMsg.textContent = msg;
    showPanel(genericPanel);
  }

  // Convert JSON Pointer / dotted path to bracket notation: $.steps[0] → [steps][0]
  function formatPath(path) {
    if (path === '$') return '$';
    return path
      .replace(/^\$/, '')
      .replace(/\[(\d+)\]/g, '[$1]')
      .replace(/\.([^.[]+)/g, '[$1]')
      .replace(/^\./, '');
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── AI prompt copy button ──────────────────────────────────────────────────

  const aiPromptCopy = document.getElementById('ai-prompt-copy');
  const aiPromptText = document.getElementById('ai-prompt-text');
  if (aiPromptCopy && aiPromptText) {
    aiPromptCopy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(aiPromptText.textContent.trim());
        aiPromptCopy.textContent = 'Copied!';
        aiPromptCopy.classList.add('copied');
        setTimeout(() => {
          aiPromptCopy.textContent = 'Copy prompt';
          aiPromptCopy.classList.remove('copied');
        }, 2000);
      } catch (_) {
        aiPromptCopy.textContent = 'Copy failed';
        setTimeout(() => { aiPromptCopy.textContent = 'Copy prompt'; }, 2000);
      }
    });
  }
})();
