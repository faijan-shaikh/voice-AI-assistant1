document.addEventListener('DOMContentLoaded', () => {
  // Global State
  let currentResultData = null; // VoiceNoteResult or BatchProcessingResult
  let activeFilter = 'all';

  // Recording State - Single Mode
  let mediaRecorderSingle = null;
  let audioChunksSingle = [];
  let recordingIntervalSingle = null;
  let recordingSecondsSingle = 0;
  let recordedBlobSingle = null;

  // Recording State - Assistant Mode
  let mediaRecorderAssistant = null;
  let audioChunksAssistant = [];
  let recordingIntervalAssistant = null;
  let recordingSecondsAssistant = 0;
  let recordedBlobAssistant = null;

  // Web Audio API Visualizer State
  let audioCtx = null;
  let analyserNode = null;
  let animFrameId = null;

  // Toast Notification System
  const toastContainer = document.getElementById('toastContainer');
  function showToast(message, type = 'info') {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    let icon = '<i class="fa-solid fa-circle-info"></i>';
    if (type === 'success') icon = '<i class="fa-solid fa-circle-check"></i>';
    if (type === 'error') icon = '<i class="fa-solid fa-triangle-exclamation"></i>';

    toast.innerHTML = `${icon} <span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // --- Theme Toggle Logic ---
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const storedTheme = localStorage.getItem('theme') || 'dark';

  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'light') {
      document.body.classList.add('light-theme');
      document.body.classList.remove('dark-theme');
      if (themeToggleBtn) themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
    } else {
      document.body.classList.add('dark-theme');
      document.body.classList.remove('light-theme');
      if (themeToggleBtn) themeToggleBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
    }
    localStorage.setItem('theme', theme);
  }

  setTheme(storedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      setTheme(newTheme);
      showToast(`Switched to ${newTheme === 'dark' ? 'Dark' : 'Light'} Mode`, 'info');
    });
  }

  // --- Workspace Reset Button ---
  const resetAppBtn = document.getElementById('resetAppBtn');
  if (resetAppBtn) {
    resetAppBtn.addEventListener('click', () => {
      currentResultData = null;
      resultsSection.classList.add('hidden');
      textMemoInput.value = '';
      selectedSingleFile = null;
      selectedBatchFiles = [];
      if (batchFileList) batchFileList.classList.add('hidden');
      if (singleFileInfo) singleFileInfo.classList.add('hidden');
      if (audioPreviewContainer) audioPreviewContainer.classList.add('hidden');
      showToast('Workspace reset clean', 'info');
    });
  }

  // --- Navigation Tabs ---
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabContents = document.querySelectorAll('.tab-content');

  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      navTabs.forEach(t => t.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      const target = tab.dataset.tab;
      const targetEl = document.getElementById(target);
      if (targetEl) targetEl.classList.add('active');
    });
  });

  // --- Real-time Web Audio API Canvas Visualizer ---
  function startCanvasVisualizer(stream, canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth || 500;
    canvas.height = canvas.offsetHeight || 90;

    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      analyserNode = audioCtx.createAnalyser();
      analyserNode.fftSize = 64;
      source.connect(analyserNode);

      const bufferLength = analyserNode.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function draw() {
        animFrameId = requestAnimationFrame(draw);
        analyserNode.getByteFrequencyData(dataArray);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barWidth = (canvas.width / bufferLength) * 1.8;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * canvas.height * 0.85;
          const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
          gradient.addColorStop(0, '#6366F1');
          gradient.addColorStop(0.5, '#A855F7');
          gradient.addColorStop(1, '#EC4899');

          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.roundRect(x, canvas.height - barHeight, barWidth - 3, barHeight, [4, 4, 0, 0]);
          ctx.fill();

          x += barWidth + 2;
        }
      }
      draw();
    } catch (e) {
      console.warn('AudioContext Visualizer non-critical error:', e);
    }
  }

  function stopCanvasVisualizer(canvasId) {
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (audioCtx) {
      audioCtx.close().catch(() => {});
      audioCtx = null;
    }
    const canvas = document.getElementById(canvasId);
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  // ==========================================
  // 1. CONVERSATIONAL VOICE AI ASSISTANT TAB
  // ==========================================
  const assistantChatHistory = document.getElementById('assistantChatHistory');
  const btnAssistantRecord = document.getElementById('btnAssistantRecord');
  const assistantTimerDisplay = document.getElementById('assistantTimerDisplay');
  const assistantRecorderStatus = document.getElementById('assistantRecorderStatus');
  const assistantTextInput = document.getElementById('assistantTextInput');
  const btnAssistantSend = document.getElementById('btnAssistantSend');

  // Quick Prompt Pills
  document.querySelectorAll('.prompt-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const text = pill.dataset.prompt;
      if (text && assistantTextInput) {
        assistantTextInput.value = text;
        sendAssistantTextQuery(text);
      }
    });
  });

  if (btnAssistantSend && assistantTextInput) {
    btnAssistantSend.addEventListener('click', () => {
      const text = assistantTextInput.value.trim();
      if (text) {
        sendAssistantTextQuery(text);
        assistantTextInput.value = '';
      }
    });

    assistantTextInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        btnAssistantSend.click();
      }
    });
  }

  if (btnAssistantRecord) {
    btnAssistantRecord.addEventListener('click', async () => {
      if (mediaRecorderAssistant && mediaRecorderAssistant.state === 'recording') {
        stopAssistantRecording();
      } else {
        startAssistantRecording();
      }
    });
  }

  async function startAssistantRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksAssistant = [];
      mediaRecorderAssistant = new MediaRecorder(stream);

      mediaRecorderAssistant.ondataavailable = e => {
        if (e.data.size > 0) audioChunksAssistant.push(e.data);
      };

      mediaRecorderAssistant.onstop = async () => {
        stopCanvasVisualizer('assistantVisualizerCanvas');
        recordedBlobAssistant = new Blob(audioChunksAssistant, { type: 'audio/webm' });
        
        // Post audio to voice pipeline
        const formData = new FormData();
        formData.append('audio', recordedBlobAssistant, 'assistant_voice.webm');
        await sendAssistantVoiceQuery(formData);
      };

      mediaRecorderAssistant.start();
      startCanvasVisualizer(stream, 'assistantVisualizerCanvas');

      btnAssistantRecord.classList.add('recording');
      btnAssistantRecord.innerHTML = '<i class="fa-solid fa-square"></i>';
      assistantRecorderStatus.textContent = 'Listening to your question... Speak now!';

      recordingSecondsAssistant = 0;
      updateAssistantTimer();
      recordingIntervalAssistant = setInterval(() => {
        recordingSecondsAssistant++;
        updateAssistantTimer();
      }, 1000);
    } catch (err) {
      alert('Microphone error: ' + err.message);
    }
  }

  function stopAssistantRecording() {
    if (mediaRecorderAssistant && mediaRecorderAssistant.state === 'recording') {
      mediaRecorderAssistant.stop();
      mediaRecorderAssistant.stream.getTracks().forEach(track => track.stop());
    }
    btnAssistantRecord.classList.remove('recording');
    btnAssistantRecord.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    assistantRecorderStatus.textContent = 'Processing your voice query with Gemini AI...';
    clearInterval(recordingIntervalAssistant);
  }

  function updateAssistantTimer() {
    const mins = String(Math.floor(recordingSecondsAssistant / 60)).padStart(2, '0');
    const secs = String(recordingSecondsAssistant % 60).padStart(2, '0');
    assistantTimerDisplay.textContent = `${mins}:${secs}`;
  }

  async function sendAssistantTextQuery(text) {
    appendChatBubble('user', text);
    showLoading('Gemini AI Reasoning...', 'Generating concise answer & spoken audio');

    try {
      const resp = await fetch('/api/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      if (!resp.ok) throw new Error('Assistant query failed');
      const data = await resp.json();
      appendChatBubble('assistant', data.answer, data.audio_url);
    } catch (e) {
      appendChatBubble('assistant', 'Sorry, I ran into an error processing your query: ' + e.message);
    } finally {
      hideLoading();
    }
  }

  async function sendAssistantVoiceQuery(formData) {
    showLoading('Transcribing & Reasoning...', 'Converting Speech -> LLM -> Text-to-Speech response');

    try {
      const resp = await fetch('/api/voice', {
        method: 'POST',
        body: formData
      });
      if (!resp.ok) throw new Error('Voice query failed');
      const data = await resp.json();
      appendChatBubble('user', `🎤 "${data.transcript}"`);
      appendChatBubble('assistant', data.answer, data.audio_url);
      assistantRecorderStatus.textContent = 'Click microphone to speak to Assistant';
    } catch (e) {
      appendChatBubble('assistant', 'Error processing voice note: ' + e.message);
      assistantRecorderStatus.textContent = 'Error occurred. Try again.';
    } finally {
      hideLoading();
    }
  }

  function appendChatBubble(role, text, audioUrl = null) {
    if (!assistantChatHistory) return;
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;

    const icon = role === 'user' ? 'fa-user' : 'fa-robot';
    const name = role === 'user' ? 'You' : 'Gemini AI Assistant';

    let audioHtml = '';
    if (audioUrl) {
      audioHtml = `
        <div class="chat-audio-player">
          <audio controls autoplay src="${audioUrl}" style="width:100%; border-radius:10px; margin-top:8px;"></audio>
        </div>
      `;
    }

    bubble.innerHTML = `
      <div class="chat-avatar"><i class="fa-solid ${icon}"></i></div>
      <div class="chat-content">
        <strong style="font-size:13px; color:var(--text-muted);">${name}</strong>
        <p>${text}</p>
        ${audioHtml}
      </div>
    `;

    assistantChatHistory.appendChild(bubble);
    assistantChatHistory.scrollTop = assistantChatHistory.scrollHeight;
  }


  // ==========================================
  // 2. SINGLE MODE (VOICE NOTE -> ACTION ITEMS)
  // ==========================================
  const btnToggleRecord = document.getElementById('btnToggleRecord');
  const btnToggleUpload = document.getElementById('btnToggleUpload');
  const recorderPanel = document.getElementById('recorderPanel');
  const uploadPanel = document.getElementById('uploadPanel');

  const btnRecordToggle = document.getElementById('btnRecordToggle');
  const timerDisplay = document.getElementById('timerDisplay');
  const recorderStatus = document.getElementById('recorderStatus');
  const waveBars = document.querySelector('.wave-bars');
  const audioPreviewContainer = document.getElementById('audioPreviewContainer');
  const audioPreview = document.getElementById('audioPreview');
  const btnProcessRecord = document.getElementById('btnProcessRecord');
  const btnDiscardRecord = document.getElementById('btnDiscardRecord');

  const dropZoneSingle = document.getElementById('dropZoneSingle');
  const singleFileInput = document.getElementById('singleFileInput');
  const singleFileInfo = document.getElementById('singleFileInfo');
  const singleFileName = document.getElementById('singleFileName');
  const btnProcessSingleFile = document.getElementById('btnProcessSingleFile');
  let selectedSingleFile = null;

  if (btnToggleRecord && btnToggleUpload) {
    btnToggleRecord.addEventListener('click', () => {
      btnToggleRecord.classList.add('active');
      btnToggleUpload.classList.remove('active');
      recorderPanel.classList.remove('hidden');
      uploadPanel.classList.add('hidden');
    });

    btnToggleUpload.addEventListener('click', () => {
      btnToggleUpload.classList.add('active');
      btnToggleRecord.classList.remove('active');
      uploadPanel.classList.remove('hidden');
      recorderPanel.classList.add('hidden');
    });
  }

  if (btnRecordToggle) {
    btnRecordToggle.addEventListener('click', async () => {
      if (mediaRecorderSingle && mediaRecorderSingle.state === 'recording') {
        stopSingleRecording();
      } else {
        startSingleRecording();
      }
    });
  }

  async function startSingleRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksSingle = [];
      mediaRecorderSingle = new MediaRecorder(stream);

      mediaRecorderSingle.ondataavailable = event => {
        if (event.data.size > 0) audioChunksSingle.push(event.data);
      };

      mediaRecorderSingle.onstop = () => {
        stopCanvasVisualizer('visualizerCanvas');
        recordedBlobSingle = new Blob(audioChunksSingle, { type: 'audio/webm' });
        const audioUrl = URL.createObjectURL(recordedBlobSingle);
        audioPreview.src = audioUrl;
        audioPreviewContainer.classList.remove('hidden');
        recorderStatus.textContent = 'Recording complete. Ready to process voice note.';
      };

      mediaRecorderSingle.start();
      startCanvasVisualizer(stream, 'visualizerCanvas');

      btnRecordToggle.classList.add('recording');
      btnRecordToggle.innerHTML = '<i class="fa-solid fa-square"></i>';
      if (waveBars) waveBars.classList.add('recording');
      recorderStatus.textContent = 'Listening to your voice note... Speak clearly';

      recordingSecondsSingle = 0;
      updateSingleTimerDisplay();
      recordingIntervalSingle = setInterval(() => {
        recordingSecondsSingle++;
        updateSingleTimerDisplay();
      }, 1000);
    } catch (err) {
      alert('Microphone access denied: ' + err.message);
    }
  }

  function stopSingleRecording() {
    if (mediaRecorderSingle && mediaRecorderSingle.state === 'recording') {
      mediaRecorderSingle.stop();
      mediaRecorderSingle.stream.getTracks().forEach(track => track.stop());
    }
    btnRecordToggle.classList.remove('recording');
    btnRecordToggle.innerHTML = '<i class="fa-solid fa-microphone"></i>';
    if (waveBars) waveBars.classList.remove('recording');
    clearInterval(recordingIntervalSingle);
  }

  function updateSingleTimerDisplay() {
    const mins = String(Math.floor(recordingSecondsSingle / 60)).padStart(2, '0');
    const secs = String(recordingSecondsSingle % 60).padStart(2, '0');
    timerDisplay.textContent = `${mins}:${secs}`;
  }

  if (btnDiscardRecord) {
    btnDiscardRecord.addEventListener('click', () => {
      recordedBlobSingle = null;
      audioPreview.src = '';
      audioPreviewContainer.classList.add('hidden');
      recordingSecondsSingle = 0;
      updateSingleTimerDisplay();
      recorderStatus.textContent = 'Click record & start speaking your voice memo';
    });
  }

  if (btnProcessRecord) {
    btnProcessRecord.addEventListener('click', async () => {
      if (!recordedBlobSingle) return;
      const formData = new FormData();
      formData.append('audio', recordedBlobSingle, 'voicenote.webm');
      await submitAudioApi('/api/action-items/audio', formData, 'Processing Recorded Audio...', 'Extracting structured tasks & summary');
    });
  }

  // Drag & Drop Single Upload
  if (singleFileInput) {
    singleFileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) handleSingleFile(e.target.files[0]);
    });
  }

  if (dropZoneSingle) {
    dropZoneSingle.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZoneSingle.classList.add('dragover');
    });

    dropZoneSingle.addEventListener('dragleave', () => dropZoneSingle.classList.remove('dragover'));

    dropZoneSingle.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZoneSingle.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) handleSingleFile(e.dataTransfer.files[0]);
    });
  }

  function handleSingleFile(file) {
    selectedSingleFile = file;
    singleFileName.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
    singleFileInfo.classList.remove('hidden');
  }

  if (btnProcessSingleFile) {
    btnProcessSingleFile.addEventListener('click', async () => {
      if (!selectedSingleFile) return;
      const formData = new FormData();
      formData.append('audio', selectedSingleFile);
      await submitAudioApi('/api/action-items/audio', formData, 'Analyzing Voice Memo...', 'Google Gemini Multimodal Analysis');
    });
  }


  // ==========================================
  // 3. BATCH PROCESSING MODE
  // ==========================================
  const dropZoneBatch = document.getElementById('dropZoneBatch');
  const batchFileInput = document.getElementById('batchFileInput');
  const batchFileList = document.getElementById('batchFileList');
  const batchCount = document.getElementById('batchCount');
  const batchItemsUl = document.getElementById('batchItemsUl');
  const btnProcessBatch = document.getElementById('btnProcessBatch');
  const btnClearBatch = document.getElementById('btnClearBatch');
  let selectedBatchFiles = [];

  if (batchFileInput) {
    batchFileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) addBatchFiles(Array.from(e.target.files));
    });
  }

  if (dropZoneBatch) {
    dropZoneBatch.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZoneBatch.classList.add('dragover');
    });
    dropZoneBatch.addEventListener('dragleave', () => dropZoneBatch.classList.remove('dragover'));
    dropZoneBatch.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZoneBatch.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) addBatchFiles(Array.from(e.dataTransfer.files));
    });
  }

  function addBatchFiles(files) {
    files.forEach(f => {
      if (!selectedBatchFiles.some(existing => existing.name === f.name)) {
        selectedBatchFiles.push(f);
      }
    });
    renderBatchFileList();
  }

  function renderBatchFileList() {
    if (selectedBatchFiles.length === 0) {
      batchFileList.classList.add('hidden');
      return;
    }
    batchCount.textContent = selectedBatchFiles.length;
    batchItemsUl.innerHTML = '';
    selectedBatchFiles.forEach((file, index) => {
      const li = document.createElement('li');
      li.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:10px 12px; border-bottom:1px solid var(--panel-border); font-size:13.5px;';
      li.innerHTML = `
        <span><i class="fa-solid fa-file-audio gradient-text"></i> ${file.name}</span>
        <button onclick="removeBatchFile(${index})" style="background:none; border:none; color:#EF4444; cursor:pointer; font-size:16px;"><i class="fa-solid fa-xmark"></i></button>
      `;
      batchItemsUl.appendChild(li);
    });
    batchFileList.classList.remove('hidden');
  }

  window.removeBatchFile = function(index) {
    selectedBatchFiles.splice(index, 1);
    renderBatchFileList();
  };

  if (btnClearBatch) {
    btnClearBatch.addEventListener('click', () => {
      selectedBatchFiles = [];
      renderBatchFileList();
    });
  }

  if (btnProcessBatch) {
    btnProcessBatch.addEventListener('click', async () => {
      if (selectedBatchFiles.length === 0) return;
      const formData = new FormData();
      selectedBatchFiles.forEach(file => formData.append('files', file));
      await submitAudioApi('/api/action-items/batch', formData, 'Batch Processing Recordings...', 'Generating Master Executive Summary');
    });
  }


  // ==========================================
  // 4. TEXT MEMO PROCESSING
  // ==========================================
  const textMemoInput = document.getElementById('textMemoInput');
  const btnProcessText = document.getElementById('btnProcessText');

  if (btnProcessText && textMemoInput) {
    btnProcessText.addEventListener('click', async () => {
      const text = textMemoInput.value.trim();
      if (!text) {
        alert('Please enter or paste your voice note text.');
        return;
      }
      showLoading('Analyzing Text Memo...', 'Extracting structured action items and summary');
      try {
        const resp = await fetch('/api/action-items/text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Analysis failed');
        }
        const data = await resp.json();
        currentResultData = data;
        renderResults(data, false);
        showToast('Text memo processed successfully!', 'success');
      } catch (e) {
        alert('Error: ' + e.message);
      } finally {
        hideLoading();
      }
    });
  }


  // ==========================================
  // 5. GENERIC SUBMIT & RESULTS RENDERER
  // ==========================================
  const loadingOverlay = document.getElementById('loadingOverlay');
  const loadingTitle = document.getElementById('loadingTitle');
  const loadingSubtitle = document.getElementById('loadingSubtitle');

  const resultsSection = document.getElementById('resultsSection');
  const resTitle = document.getElementById('resTitle');
  const resSentiment = document.getElementById('resSentiment');
  const resSummaryText = document.getElementById('resSummaryText');
  const keyTakeawaysContainer = document.getElementById('keyTakeawaysContainer');
  const keyTakeawaysUl = document.getElementById('keyTakeawaysUl');
  const resAudioContainer = document.getElementById('resAudioContainer');
  const resAudioPlayer = document.getElementById('resAudioPlayer');

  const taskCounterBadge = document.getElementById('taskCounterBadge');
  const progressPercent = document.getElementById('progressPercent');
  const progressFill = document.getElementById('progressFill');
  const taskListUl = document.getElementById('taskListUl');
  const filterTabs = document.querySelectorAll('.filter-tab');
  const taskSearchInput = document.getElementById('taskSearchInput');

  const batchBreakdownContainer = document.getElementById('batchBreakdownContainer');
  const batchNotesAccordion = document.getElementById('batchNotesAccordion');

  async function submitAudioApi(endpoint, formData, title = 'Processing Audio...', subtitle = 'Gemini AI Analysis') {
    showLoading(title, subtitle);
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        body: formData
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Processing failed');
      }
      const data = await resp.json();
      currentResultData = data;
      const isBatch = endpoint.includes('batch');
      renderResults(data, isBatch);
      showToast('Action Items & Executive Summary Generated!', 'success');
    } catch (e) {
      alert('Error processing audio: ' + e.message);
    } finally {
      hideLoading();
    }
  }

  function showLoading(title, subtitle) {
    if (loadingTitle) loadingTitle.textContent = title;
    if (loadingSubtitle) loadingSubtitle.textContent = subtitle;
    if (loadingOverlay) loadingOverlay.classList.remove('hidden');
  }

  function hideLoading() {
    if (loadingOverlay) loadingOverlay.classList.add('hidden');
  }

  function renderResults(data, isBatch = false) {
    if (!resultsSection) return;
    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });

    if (isBatch) {
      resTitle.textContent = 'Batch Executive Summary';
      resSentiment.textContent = `${data.total_recordings} Recordings`;
      resSummaryText.textContent = data.master_summary;
      if (keyTakeawaysContainer) keyTakeawaysContainer.classList.add('hidden');
      if (resAudioContainer) resAudioContainer.classList.add('hidden');

      renderActionItemsBoard(data.master_action_items || []);

      if (batchBreakdownContainer && batchNotesAccordion) {
        batchBreakdownContainer.classList.remove('hidden');
        batchNotesAccordion.innerHTML = '';
        (data.individual_notes || []).forEach((note, idx) => {
          const card = document.createElement('div');
          card.style.cssText = 'background:var(--input-bg); padding:16px; border-radius:14px; margin-top:12px; border:1px solid var(--panel-border);';
          card.innerHTML = `
            <h4 style="font-size:15.5px; color:var(--text-main);"><i class="fa-solid fa-microphone gradient-text"></i> Note #${idx + 1}: ${note.title}</h4>
            <p style="font-size:13.5px; color:var(--text-muted); margin-top:6px;">${note.summary}</p>
            <div style="font-size:12.5px; color:var(--primary); margin-top:10px; font-weight:600;">${note.action_items ? note.action_items.length : 0} Action Items Extracted</div>
          `;
          batchNotesAccordion.appendChild(card);
        });
      }
    } else {
      resTitle.textContent = data.title || 'Voice Note Summary';
      resSentiment.textContent = data.sentiment || 'Productive';
      resSummaryText.textContent = data.summary;

      if (data.audio_url && resAudioPlayer && resAudioContainer) {
        resAudioPlayer.src = data.audio_url;
        resAudioContainer.classList.remove('hidden');
      } else if (resAudioContainer) {
        resAudioContainer.classList.add('hidden');
      }

      if (data.key_takeaways && data.key_takeaways.length > 0 && keyTakeawaysUl && keyTakeawaysContainer) {
        keyTakeawaysUl.innerHTML = '';
        data.key_takeaways.forEach(pt => {
          const li = document.createElement('li');
          li.textContent = pt;
          keyTakeawaysUl.appendChild(li);
        });
        keyTakeawaysContainer.classList.remove('hidden');
      } else if (keyTakeawaysContainer) {
        keyTakeawaysContainer.classList.add('hidden');
      }

      if (batchBreakdownContainer) batchBreakdownContainer.classList.add('hidden');
      renderActionItemsBoard(data.action_items || []);
    }
  }

  // --- Task Board & Filter Logic ---
  let currentTasks = [];

  function renderActionItemsBoard(tasks) {
    currentTasks = tasks.map(t => ({ ...t, status: t.status || 'Pending' }));
    filterAndRenderTasks();
  }

  filterTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      filterTabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      filterAndRenderTasks();
    });
  });

  if (taskSearchInput) {
    taskSearchInput.addEventListener('input', () => filterAndRenderTasks());
  }

  function filterAndRenderTasks() {
    if (!taskListUl) return;
    const query = taskSearchInput ? taskSearchInput.value.toLowerCase().trim() : '';

    let filtered = currentTasks.filter(item => {
      if (activeFilter === 'High' || activeFilter === 'Medium' || activeFilter === 'Low') {
        if (item.priority !== activeFilter) return false;
      } else if (activeFilter === 'Pending') {
        if (item.status !== 'Pending') return false;
      } else if (activeFilter === 'Completed') {
        if (item.status !== 'Completed') return false;
      }

      if (query) {
        const text = `${item.task} ${item.category} ${item.assignee} ${item.deadline}`.toLowerCase();
        if (!text.includes(query)) return false;
      }

      return true;
    });

    if (taskCounterBadge) taskCounterBadge.textContent = `${currentTasks.length} Tasks`;
    const completedCount = currentTasks.filter(t => t.status === 'Completed').length;
    const pct = currentTasks.length > 0 ? Math.round((completedCount / currentTasks.length) * 100) : 0;
    if (progressPercent) progressPercent.textContent = `${pct}%`;
    if (progressFill) progressFill.style.width = `${pct}%`;

    taskListUl.innerHTML = '';
    if (filtered.length === 0) {
      taskListUl.innerHTML = '<div style="text-align:center; padding:24px; color:var(--text-subtle);">No action items found matching your filters.</div>';
      return;
    }

    filtered.forEach(item => {
      const isDone = item.status === 'Completed';
      const div = document.createElement('div');
      div.className = `task-item ${isDone ? 'completed' : ''}`;
      div.innerHTML = `
        <div class="task-left">
          <div class="task-checkbox" onclick="toggleTaskStatus('${item.id}')">
            <i class="fa-solid fa-check"></i>
          </div>
          <span class="task-text">${item.task}</span>
        </div>
        <div class="task-tags">
          <span class="prio-badge prio-${item.priority}">${item.priority}</span>
          <span class="tag-badge"><i class="fa-solid fa-tag"></i> ${item.category}</span>
          <span class="tag-badge" style="color:var(--text-muted);"><i class="fa-regular fa-clock"></i> ${item.deadline}</span>
        </div>
      `;
      taskListUl.appendChild(div);
    });
  }

  window.toggleTaskStatus = function(taskId) {
    const task = currentTasks.find(t => t.id === taskId);
    if (task) {
      task.status = task.status === 'Completed' ? 'Pending' : 'Completed';
      filterAndRenderTasks();
      showToast(`Task status set to ${task.status}`, 'info');
    }
  };


  // ==========================================
  // 6. EXPORT ACTIONS
  // ==========================================
  const btnExportPdf = document.getElementById('btnExportPdf');
  const btnCopyMarkdown = document.getElementById('btnCopyMarkdown');
  const btnExportJson = document.getElementById('btnExportJson');

  if (btnExportPdf) {
    btnExportPdf.addEventListener('click', async () => {
      if (!currentResultData) return;
      showLoading('Generating Executive PDF Report...', 'Formatting PDF with ReportLab tables');
      try {
        const exportPayload = JSON.parse(JSON.stringify(currentResultData));
        if (exportPayload.action_items) exportPayload.action_items = currentTasks;
        else if (exportPayload.master_action_items) exportPayload.master_action_items = currentTasks;

        const response = await fetch('/api/action-items/pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: exportPayload })
        });

        if (!response.ok) throw new Error('Failed to generate PDF');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Action_Items_Report_${Date.now()}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast('PDF Executive Report downloaded!', 'success');
      } catch (err) {
        alert('PDF Generation failed: ' + err.message);
      } finally {
        hideLoading();
      }
    });
  }

  if (btnCopyMarkdown) {
    btnCopyMarkdown.addEventListener('click', () => {
      if (!currentResultData) return;
      let md = `# ${currentResultData.title || currentResultData.master_summary_title || 'Voice Note Report'}\n\n`;
      md += `## Executive Summary\n${currentResultData.summary || currentResultData.master_summary}\n\n`;
      md += `## Action Items\n`;

      currentTasks.forEach(t => {
        const chk = t.status === 'Completed' ? '[x]' : '[ ]';
        md += `- ${chk} **${t.task}** (Priority: ${t.priority} | Category: ${t.category} | Assignee: ${t.assignee} | Due: ${t.deadline})\n`;
      });

      navigator.clipboard.writeText(md).then(() => {
        showToast('Copied Markdown report to clipboard!', 'success');
      });
    });
  }

  if (btnExportJson) {
    btnExportJson.addEventListener('click', () => {
      if (!currentResultData) return;
      const str = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentResultData, null, 2));
      const a = document.createElement('a');
      a.href = str;
      a.download = `voice_note_data_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast('Exported raw JSON data!', 'success');
    });
  }
});
