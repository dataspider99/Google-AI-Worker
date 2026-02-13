(function () {
  const apiKeyEl = document.getElementById('api-key-value');
  const toggleKeyBtn = document.getElementById('toggle-key');
  const createKeyBtn = document.getElementById('create-key');
  const runResultEl = document.getElementById('run-result');
  const modalEl = document.getElementById('response-modal');
  const modalLoadingEl = document.getElementById('modal-loading');
  const modalContentEl = document.getElementById('modal-content');
  const modalLoadingTextEl = document.getElementById('modal-loading-text');
  const modalCloseBtn = document.getElementById('modal-close');
  const modalBackdrop = document.getElementById('modal-backdrop');
  const oshaaniKeyInput = document.getElementById('oshaani-key-input');
  const saveOshaaniKeyBtn = document.getElementById('save-oshaani-key');
  const testOshaaniKeyBtn = document.getElementById('test-oshaani-key');
  const clearOshaaniKeyBtn = document.getElementById('clear-oshaani-key');
  const oshaaniKeyStatus = document.getElementById('oshaani-key-status');

  let apiKeyStored = null;

  function openModal() {
    if (modalEl) {
      modalEl.classList.add('is-open');
      modalEl.setAttribute('aria-hidden', 'false');
    }
  }

  function closeModal() {
    if (modalEl) {
      modalEl.classList.remove('is-open');
      modalEl.setAttribute('aria-hidden', 'true');
    }
  }

  function showModalLoading(message) {
    if (modalLoadingTextEl) modalLoadingTextEl.textContent = message || 'Running…';
    if (modalLoadingEl) modalLoadingEl.style.display = 'flex';
    if (modalContentEl) { modalContentEl.style.display = 'none'; modalContentEl.innerHTML = ''; }
    if (modalContentEl) modalContentEl.classList.remove('error');
    openModal();
  }

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
  if (modalBackdrop) modalBackdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modalEl && modalEl.classList.contains('is-open')) closeModal();
  });

  if (toggleKeyBtn && apiKeyEl) {
    toggleKeyBtn.addEventListener('click', function () {
      if (apiKeyEl.classList.contains('revealed')) {
        apiKeyEl.textContent = '••••••••••••';
        apiKeyEl.classList.remove('revealed');
        toggleKeyBtn.textContent = 'Show key';
      } else if (apiKeyStored) {
        apiKeyEl.textContent = apiKeyStored;
        apiKeyEl.classList.add('revealed');
        toggleKeyBtn.textContent = 'Hide key';
      }
    });
  }

  if (createKeyBtn) {
    createKeyBtn.addEventListener('click', async function () {
      createKeyBtn.disabled = true;
      createKeyBtn.textContent = 'Generating…';
      showModalLoading('Generating API key…');
      try {
        const r = await fetch('/api-key', { method: 'POST', credentials: 'include' });
        const data = await r.json();
        if (data.api_key) {
          apiKeyStored = data.api_key;
          apiKeyEl.textContent = data.api_key;
          apiKeyEl.classList.add('revealed');
          toggleKeyBtn.textContent = 'Hide key';
          showResult('New API key created. Copy it now; it won’t be shown again.', false);
        } else {
          showResult(data, true);
        }
      } catch (e) {
        showResult({ detail: e.message || 'Network or unexpected error.' }, true);
      }
      createKeyBtn.disabled = false;
      createKeyBtn.textContent = 'Generate new key';
    });
  }

  document.querySelectorAll('[data-workflow]').forEach(function (btn) {
    btn.addEventListener('click', async function () {
      const workflow = this.getAttribute('data-workflow');
      if (workflow === 'chat-auto-reply') {
        await runChatAutoReplyWithSpacePicker();
        return;
      }
      if (workflow === 'chat-auto-reply-batch') {
        await runChatAutoReplyBatch(5);
        return;
      }
      const cards = document.querySelector('.cards');
      if (cards) cards.classList.add('loading');
      showModalLoading('Running…');
      try {
        let url = '/workflows/run-all';
        let method = 'POST';
        if (workflow === 'smart-inbox') url = '/workflows/smart-inbox';
        else if (workflow === 'first-email-draft') url = '/workflows/first-email-draft';
        else if (workflow === 'document-intelligence') url = '/workflows/document-intelligence';
        else if (workflow === 'chat-spaces') { url = '/workflows/chat-spaces'; method = 'GET'; }
        const r = await fetch(url, { method: method, credentials: 'include' });
        const data = await r.json();
        if (r.ok) {
          showResult(data, false, workflow);
        } else {
          showResult(data, true);
        }
      } catch (e) {
        showResult({ detail: e.message || 'Network or unexpected error.' }, true);
      }
      if (cards) cards.classList.remove('loading');
    });
  });

  async function runChatAutoReplyWithSpacePicker() {
    const pickerEl = document.getElementById('chat-auto-reply-picker');
    const selectEl = document.getElementById('chat-auto-reply-space');
    const cards = document.querySelector('.cards');
    if (cards) cards.classList.add('loading');
    showModalLoading('Loading spaces…');
    try {
      const r = await fetch('/workflows/chat-spaces', { credentials: 'include' });
      const data = await r.json();
      if (!r.ok) {
        showResult(data, true);
        if (cards) cards.classList.remove('loading');
        return;
      }
      var spaces = (data.spaces || []).filter(function (s) { return s.type === 'DIRECT_MESSAGE'; });
      if (spaces.length === 0) {
        showResult(data, true);
        if (pickerEl) pickerEl.style.display = 'none';
        if (cards) cards.classList.remove('loading');
        return;
      }
      if (spaces.length === 1) {
        await runChatAutoReplyForSpace(spaces[0].name);
        if (cards) cards.classList.remove('loading');
        return;
      }
      closeModal();
      if (selectEl && pickerEl) {
        selectEl.innerHTML = '';
        spaces.forEach(function (s) {
          var opt = document.createElement('option');
          opt.value = s.name;
          opt.textContent = s.displayName || s.name;
          selectEl.appendChild(opt);
        });
        pickerEl.style.display = 'flex';
      }
    } catch (e) {
      showResult({ detail: e.message || 'Network or unexpected error.' }, true);
    }
    if (cards) cards.classList.remove('loading');
  }

  async function runChatAutoReplyForSpace(spaceName) {
    const cards = document.querySelector('.cards');
    if (cards) cards.classList.add('loading');
    showModalLoading('Running chat auto-reply…');
    try {
      const r = await fetch('/workflows/chat-auto-reply?space_name=' + encodeURIComponent(spaceName), { method: 'POST', credentials: 'include' });
      const data = await r.json();
      if (r.ok) {
        showResult(data, false, 'chat-auto-reply');
      } else {
        showResult(data, true);
      }
    } catch (e) {
      showResult({ detail: e.message || 'Network or unexpected error.' }, true);
    }
    if (cards) cards.classList.remove('loading');
  }

  var runSelectedBtn = document.getElementById('chat-auto-reply-run-selected');
  if (runSelectedBtn) {
    runSelectedBtn.addEventListener('click', function () {
      var selectEl = document.getElementById('chat-auto-reply-space');
      var spaceName = selectEl && selectEl.value;
      if (spaceName) runChatAutoReplyForSpace(spaceName);
    });
  }

  async function runChatAutoReplyBatch(limit) {
    const cards = document.querySelector('.cards');
    if (cards) cards.classList.add('loading');
    showModalLoading('Running chat auto-reply for top ' + limit + ' spaces…');
    try {
      const r = await fetch('/workflows/chat-auto-reply-batch?limit=' + limit, { method: 'POST', credentials: 'include' });
      const data = await r.json();
      if (r.ok) {
        showResult(data, false, 'chat-auto-reply-batch');
      } else {
        showResult(data, true);
      }
    } catch (e) {
      showResult({ detail: e.message || 'Network or unexpected error.' }, true);
    }
    if (cards) cards.classList.remove('loading');
  }

  function formatResponse(data) {
    if (data === null || data === undefined) return '';
    if (typeof data !== 'object') return String(data);
    var frag = document.createDocumentFragment();
    var escape = function (s) {
      var div = document.createElement('div');
      div.textContent = s;
      return div.innerHTML;
    };
    var addSection = function (title, content) {
      var section = document.createElement('div');
      section.className = 'result-section';
      var h = document.createElement('h4');
      h.className = 'result-heading';
      h.textContent = title;
      section.appendChild(h);
      if (typeof content === 'string') {
        var p = document.createElement('div');
        p.className = 'result-text';
        p.innerHTML = escape(content).replace(/\n/g, '<br>');
        section.appendChild(p);
      } else {
        section.appendChild(content);
      }
      frag.appendChild(section);
    };
    var addKeyValue = function (key, value) {
      var row = document.createElement('div');
      row.className = 'result-row';
      row.innerHTML = '<span class="result-key">' + escape(String(key)) + '</span><span class="result-value">' + escape(String(value)) + '</span>';
      return row;
    };
    if (data.response !== undefined && data.response !== '') {
      addSection('Response', String(data.response));
    }
    if (data.tasks_created && Array.isArray(data.tasks_created) && data.tasks_created.length > 0) {
      var tasksSection = document.createElement('div');
      tasksSection.className = 'result-section';
      tasksSection.innerHTML = '<h4 class="result-heading">Google Tasks created</h4>';
      var tasksList = document.createElement('ul');
      tasksList.className = 'result-tasks-list';
      data.tasks_created.forEach(function (t) {
        var li = document.createElement('li');
        li.textContent = (t.title || 'Task') + (t.notes ? ' — ' + t.notes : '');
        tasksList.appendChild(li);
      });
      tasksSection.appendChild(tasksList);
      frag.appendChild(tasksSection);
    }
    if (data.events_created && Array.isArray(data.events_created) && data.events_created.length > 0) {
      var eventsSection = document.createElement('div');
      eventsSection.className = 'result-section';
      eventsSection.innerHTML = '<h4 class="result-heading">Calendar events created</h4>';
      var eventsList = document.createElement('ul');
      eventsList.className = 'result-tasks-list';
      data.events_created.forEach(function (ev) {
        var li = document.createElement('li');
        var start = (ev.start && (ev.start.dateTime || ev.start.date)) || '';
        var end = (ev.end && (ev.end.dateTime || ev.end.date)) || '';
        li.textContent = (ev.summary || 'Event') + (start ? ' — ' + start + (end ? ' to ' + end : '') : '');
        if (ev.htmlLink) {
          var a = document.createElement('a');
          a.href = ev.htmlLink;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.textContent = ' Open in Calendar';
          a.className = 'result-calendar-link';
          li.appendChild(a);
        }
        eventsList.appendChild(li);
      });
      eventsSection.appendChild(eventsList);
      frag.appendChild(eventsSection);
    }
    if (data.status) {
      var statusSection = document.createElement('div');
      statusSection.className = 'result-section';
      statusSection.appendChild(addKeyValue('Status', data.status));
      if (data.message) statusSection.appendChild(addKeyValue('Message', data.message));
      frag.appendChild(statusSection);
    }
    if (data.workflows && typeof data.workflows === 'object') {
      var wfDiv = document.createElement('div');
      wfDiv.className = 'result-workflows';
      Object.keys(data.workflows).forEach(function (name) {
        var w = data.workflows[name];
        var card = document.createElement('div');
        card.className = 'result-workflow-card';
        card.innerHTML = '<span class="result-workflow-name">' + escape(name.replace(/_/g, ' ')) + '</span>' +
          '<span class="result-workflow-status">' + escape(w.status || '') + '</span>' +
          (w.response_preview ? '<p class="result-workflow-preview">' + escape(String(w.response_preview).slice(0, 200)) + (String(w.response_preview).length > 200 ? '…' : '') + '</p>' : '');
        wfDiv.appendChild(card);
      });
      var wrap = document.createElement('div');
      wrap.className = 'result-section';
      wrap.innerHTML = '<h4 class="result-heading">Workflows</h4>';
      wrap.appendChild(wfDiv);
      frag.appendChild(wrap);
    }
    if (data.spaces && Array.isArray(data.spaces) && typeof data.total === 'number') {
      var batchDiv = document.createElement('div');
      batchDiv.className = 'result-workflows';
      data.spaces.forEach(function (item) {
        var card = document.createElement('div');
        card.className = 'result-workflow-card';
        var name = item.space || 'Space';
        var status = item.error ? 'Error: ' + item.error : (item.replies && item.replies.length ? item.replies.length + ' reply(ies)' : 'No new replies');
        card.innerHTML = '<span class="result-workflow-name">' + escape(name) + '</span><span class="result-workflow-status">' + escape(status) + '</span>';
        if (item.replies && item.replies.length) {
          var preview = JSON.stringify(item.replies).slice(0, 180);
          if (JSON.stringify(item.replies).length > 180) preview += '…';
          card.innerHTML += '<p class="result-workflow-preview">' + escape(preview) + '</p>';
        }
        batchDiv.appendChild(card);
      });
      var batchWrap = document.createElement('div');
      batchWrap.className = 'result-section';
      batchWrap.innerHTML = '<h4 class="result-heading">Chat auto-reply (top ' + data.total + ')</h4>';
      batchWrap.appendChild(batchDiv);
      frag.appendChild(batchWrap);
    }
    var skip = { response: 1, status: 1, message: 1, workflows: 1, total: 1, spaces: 1, tasks_created: 1, events_created: 1 };
    var others = [];
    Object.keys(data).forEach(function (k) {
      if (skip[k]) return;
      var v = data[k];
      if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
        if (Object.keys(v).length <= 3 && [].every.call(Object.keys(v), function (key) { return typeof v[key] !== 'object'; })) {
          others.push({ k: k, v: JSON.stringify(v) });
        } else {
          others.push({ k: k, v: JSON.stringify(v, null, 2) });
        }
      } else {
        others.push({ k: k, v: typeof v === 'string' ? v : JSON.stringify(v) });
      }
    });
    if (others.length) {
      var section = document.createElement('div');
      section.className = 'result-section';
      section.innerHTML = '<h4 class="result-heading">Details</h4>';
      others.forEach(function (o) {
        section.appendChild(addKeyValue(o.k, o.v));
      });
      frag.appendChild(section);
    }
    if (frag.childNodes.length === 0) {
      var pre = document.createElement('pre');
      pre.className = 'result-raw';
      pre.textContent = JSON.stringify(data, null, 2);
      frag.appendChild(pre);
    }
    return frag;
  }

  /** Build a clear error message from API response (detail can be string or list of validation errors). */
  function formatErrorMessage(data) {
    if (data == null) return 'An error occurred.';
    var detail = data.detail;
    if (detail == null) return data.message || JSON.stringify(data);
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      var lines = detail.map(function (d) {
        var loc = d.loc ? d.loc.join(' ') : '';
        var msg = d.msg || d.message || JSON.stringify(d);
        return loc ? loc + ': ' + msg : msg;
      });
      return lines.join('\n');
    }
    return JSON.stringify(detail);
  }

  /** Links to open Gmail, Chat, Drive, Tasks based on workflow. */
  var GSUITE_LINKS = {
    'smart-inbox': [
      { label: 'View in Gmail', url: 'https://mail.google.com/mail/' },
      { label: 'View in Tasks', url: 'https://tasks.google.com/' },
      { label: 'View in Calendar', url: 'https://calendar.google.com/calendar/' }
    ],
    'first-email-draft': [
      { label: 'View in Gmail', url: 'https://mail.google.com/mail/' }
    ],
    'document-intelligence': [
      { label: 'View in Drive', url: 'https://drive.google.com/drive/' }
    ],
    'chat-auto-reply': [
      { label: 'View in Chat', url: 'https://chat.google.com/' }
    ],
    'chat-auto-reply-batch': [
      { label: 'View in Chat', url: 'https://chat.google.com/' }
    ],
    'chat-spaces': [
      { label: 'View in Chat', url: 'https://chat.google.com/' }
    ],
    'run-all': [
      { label: 'Gmail', url: 'https://mail.google.com/mail/' },
      { label: 'Chat', url: 'https://chat.google.com/' },
      { label: 'Drive', url: 'https://drive.google.com/drive/' },
      { label: 'Tasks', url: 'https://tasks.google.com/' }
    ]
  };

  function appendGsuiteButtons(container, workflow) {
    var links = workflow && GSUITE_LINKS[workflow];
    if (!links || links.length === 0) return;
    var wrap = document.createElement('div');
    wrap.className = 'result-gsuite-links';
    var heading = document.createElement('div');
    heading.className = 'result-gsuite-heading';
    heading.textContent = 'Open in Google Workspace';
    wrap.appendChild(heading);
    var btnRow = document.createElement('div');
    btnRow.className = 'result-gsuite-btns';
    links.forEach(function (item) {
      var a = document.createElement('a');
      a.href = item.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.className = 'btn btn-secondary result-gsuite-btn';
      a.textContent = item.label;
      btnRow.appendChild(a);
    });
    wrap.appendChild(btnRow);
    container.appendChild(wrap);
  }

  function showResult(textOrData, isError, workflow) {
    var target = modalContentEl || runResultEl;
    if (!target) return;
    if (modalLoadingEl) modalLoadingEl.style.display = 'none';
    if (modalContentEl) modalContentEl.style.display = 'block';
    target.classList.toggle('error', isError);
    target.innerHTML = '';
    if (isError) {
      var wrap = document.createElement('div');
      wrap.className = 'result-error-wrap';
      var heading = document.createElement('div');
      heading.className = 'result-error-heading';
      heading.textContent = 'Error';
      wrap.appendChild(heading);
      var msg = document.createElement('div');
      msg.className = 'result-error-detail';
      var text = typeof textOrData === 'string' ? textOrData : (textOrData && typeof textOrData === 'object' ? formatErrorMessage(textOrData) : String(textOrData));
      msg.textContent = text;
      msg.style.whiteSpace = 'pre-wrap';
      msg.style.wordBreak = 'break-word';
      wrap.appendChild(msg);
      target.appendChild(wrap);
      openModal();
      return;
    }
    if (typeof textOrData === 'string') {
      var p = document.createElement('div');
      p.className = 'result-text';
      p.textContent = textOrData;
      target.appendChild(p);
      openModal();
      return;
    }
    if (typeof textOrData === 'object' && textOrData !== null) {
      target.appendChild(formatResponse(textOrData));
      appendGsuiteButtons(target, workflow);
      var copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'btn btn-secondary result-copy';
      copyBtn.textContent = 'Copy raw JSON';
      copyBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(JSON.stringify(textOrData, null, 2));
        copyBtn.textContent = 'Copied';
        setTimeout(function () { copyBtn.textContent = 'Copy raw JSON'; }, 1500);
      });
      target.appendChild(copyBtn);
    } else {
      var p = document.createElement('div');
      p.className = 'result-text';
      p.textContent = String(textOrData);
      target.appendChild(p);
    }
    openModal();
  }

  // Oshaani API key: load status, save, clear
  async function loadOshaaniKeyStatus() {
    if (!oshaaniKeyStatus) return;
    try {
      const r = await fetch('/me/oshaani-key', { credentials: 'include' });
      const data = await r.json();
      oshaaniKeyStatus.textContent = data.hint || '';
      oshaaniKeyStatus.classList.toggle('status-key-set', !!data.set);
    } catch (e) {
      oshaaniKeyStatus.textContent = '';
      oshaaniKeyStatus.classList.remove('status-key-set');
    }
  }
  if (saveOshaaniKeyBtn && oshaaniKeyInput) {
    saveOshaaniKeyBtn.addEventListener('click', async function () {
      saveOshaaniKeyBtn.disabled = true;
      saveOshaaniKeyBtn.textContent = 'Saving…';
      showModalLoading('Saving Oshaani key…');
      try {
        const r = await fetch('/me/oshaani-key', {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oshaani_api_key: oshaaniKeyInput.value || '' }),
        });
        const data = await r.json();
        if (r.ok) {
          await loadOshaaniKeyStatus();
          oshaaniKeyInput.value = '';
          showResult(data.message || 'Saved.', false);
        } else {
          showResult(data, true);
        }
      } catch (e) {
        showResult({ detail: e.message || 'Network or unexpected error.' }, true);
      }
      saveOshaaniKeyBtn.disabled = false;
      saveOshaaniKeyBtn.textContent = 'Save';
    });
  }
  if (testOshaaniKeyBtn) {
    testOshaaniKeyBtn.addEventListener('click', async function () {
      testOshaaniKeyBtn.disabled = true;
      var keyToTest = oshaaniKeyInput && oshaaniKeyInput.value ? oshaaniKeyInput.value.trim() : '';
      showModalLoading(keyToTest ? 'Testing key…' : 'Testing saved key…');
      try {
        const r = await fetch('/me/oshaani-key/test', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oshaani_api_key: keyToTest }),
        });
        const data = await r.json().catch(function () { return { detail: 'Invalid response from server.' }; });
        if (r.ok && data.valid) {
          showResult(data.message || 'Key is valid.', false);
        } else {
          showResult(data, true);
        }
      } catch (e) {
        showResult({ detail: e.message || 'Network or unexpected error.' }, true);
      }
      testOshaaniKeyBtn.disabled = false;
    });
  }
  if (clearOshaaniKeyBtn) {
    clearOshaaniKeyBtn.addEventListener('click', async function () {
      clearOshaaniKeyBtn.disabled = true;
      showModalLoading('Clearing Oshaani key…');
      try {
        await fetch('/me/oshaani-key', {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oshaani_api_key: '' }),
        });
        await loadOshaaniKeyStatus();
        if (oshaaniKeyInput) oshaaniKeyInput.value = '';
        showResult('Cleared. Using default key.', false);
      } catch (e) {
        showResult({ detail: e.message || 'Network or unexpected error.' }, true);
      }
      clearOshaaniKeyBtn.disabled = false;
    });
  }
  loadOshaaniKeyStatus();

  function updateChatAutoReplyBadge(on) {
    var badge = document.getElementById('chat-auto-reply-badge');
    if (!badge) return;
    badge.textContent = 'Chat auto-reply ' + (on ? 'On' : 'Off');
    badge.classList.toggle('on', !!on);
    badge.classList.toggle('off', !on);
  }

  // Workflow toggles: load state, then save on change
  async function loadWorkflowToggles() {
    try {
      const r = await fetch('/me/workflow-toggles', { credentials: 'include' });
      const toggles = await r.json();
      document.querySelectorAll('.workflow-toggle').forEach(function (cb) {
        var id = cb.getAttribute('data-workflow-id');
        cb.checked = toggles[id] !== false;
        var card = cb.closest('.card');
        if (card) card.classList.toggle('workflow-off', !cb.checked);
      });
      updateChatAutoReplyBadge(toggles.chat_auto_reply !== false);
    } catch (e) {
      // leave defaults (all checked)
    }
  }

  document.querySelectorAll('.workflow-toggle').forEach(function (cb) {
    cb.addEventListener('change', async function () {
      var id = cb.getAttribute('data-workflow-id');
      if (!id) return;
      var payload = {};
      payload[id] = cb.checked;
      try {
        const r = await fetch('/me/workflow-toggles', {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (r.ok) {
          var card = cb.closest('.card');
          if (card) card.classList.toggle('workflow-off', !cb.checked);
          if (id === 'chat_auto_reply') updateChatAutoReplyBadge(cb.checked);
        } else {
          cb.checked = !cb.checked;
          var card = cb.closest('.card');
          if (card) card.classList.toggle('workflow-off', !cb.checked);
          if (id === 'chat_auto_reply') updateChatAutoReplyBadge(cb.checked);
        }
      } catch (e) {
        cb.checked = !cb.checked;
        var card = cb.closest('.card');
        if (card) card.classList.toggle('workflow-off', !cb.checked);
        if (id === 'chat_auto_reply') updateChatAutoReplyBadge(cb.checked);
      }
    });
  });

  loadWorkflowToggles();

  // Automation (Run all on schedule) on/off toggle – on Run all card only
  var automationToggle = document.getElementById('automation-toggle');
  var automationBadge = document.getElementById('automation-badge');

  // Load saved automation state on page load so checkbox matches persisted value
  (function loadAutomationState() {
    if (!automationToggle) return;
    fetch('/me/automation', { credentials: 'include', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        var enabled = data.enabled === true || data.enabled === 'true';
        automationToggle.checked = enabled;
      })
      .catch(function () {});
  })();

  function syncAutomationUI(enabled) {
    if (automationBadge) {
      automationBadge.textContent = 'Automation ' + (enabled ? 'On' : 'Off');
      automationBadge.classList.toggle('on', !!enabled);
      automationBadge.classList.toggle('off', !enabled);
    }
    if (automationToggle && automationToggle.checked !== enabled) {
      automationToggle.checked = !!enabled;
    }
  }

  function handleAutomationChange(enabled) {
    fetch('/me/automation', {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: enabled }),
    })
      .then(function (r) {
        if (r.ok) return r.json();
        throw new Error('Failed to update');
      })
      .then(function (data) {
        syncAutomationUI(data.enabled);
      })
      .catch(function () {
        // Don't revert UI – leave toggle as user set it; show error so they know save failed
        var msg = document.getElementById('automation-error-msg');
        if (msg) {
          msg.textContent = 'Could not save. Try again or check Drive access.';
          msg.style.display = 'block';
          setTimeout(function () { msg.style.display = 'none'; }, 5000);
        }
      });
  }

  if (automationToggle) {
    automationToggle.addEventListener('change', function () {
      var enabled = automationToggle.checked;
      var msg = document.getElementById('automation-error-msg');
      if (msg) msg.style.display = 'none';
      handleAutomationChange(enabled);
    });
  }
})();
