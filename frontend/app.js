// ─── Tab / Auth helpers ────────────────────────────────────────────────────

function showTab(tab) {
    document.getElementById('login-form').style.display = tab === 'login' ? '' : 'none';
    document.getElementById('register-form').style.display = tab === 'register' ? '' : 'none';
    document.getElementById('tab-login').classList.toggle('active', tab === 'login');
    document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    try {
        await Api.login(email, password);
        await initApp();
    } catch (e) {
        document.getElementById('auth-error').textContent = e.message;
    }
}

async function handleRegister() {
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    try {
        await Api.register(email, password);
        await Api.login(email, password);
        await initApp();
    } catch (e) {
        document.getElementById('auth-error').textContent = e.message;
    }
}

function handleLogout() {
    Api.logout();
    document.getElementById('auth-panel').style.display = '';
    document.getElementById('app-panel').style.display = 'none';
}

// ─── Main app ───────────────────────────────────────────────────────────────

const vocalModel = new VocalVitalsModel();

async function initApp() {
    const user = await Api.me();
    if (!user) return;

    document.getElementById('auth-panel').style.display = 'none';
    document.getElementById('app-panel').style.display = '';
    document.getElementById('user-email-label').textContent = user.email;

    // Load model
    document.getElementById('status-text').textContent = 'Loading model…';
    await vocalModel.loadModel();
    document.getElementById('status-text').textContent = 'Ready. Press Start Recording.';

    // Show model version
    const mv = await Api.getModelVersion();
    if (mv) document.getElementById('model-version-badge').textContent = mv.version;

    // Load baseline
    await refreshBaseline();

    // Load history
    await refreshHistory();
}

async function refreshBaseline() {
    const baseline = await Api.getBaseline();
    const el = document.getElementById('baseline-status');
    if (!baseline) {
        el.textContent = 'Not established — record a high-confidence cough first.';
        el.style.color = 'var(--text-secondary)';
    } else {
        el.textContent = `Established ${new Date(baseline.established_at).toLocaleDateString()} · avg confidence ${(baseline.avg_confidence * 100).toFixed(0)}%`;
        el.style.color = 'var(--success)';
    }
}

async function refreshHistory() {
    const data = await Api.getSessions(1, 10);
    const list = document.getElementById('history-list');
    list.innerHTML = '';
    if (!data || data.total === 0) {
        list.innerHTML = '<li class="history-empty">No sessions yet.</li>';
        return;
    }
    for (const s of data.items) {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.innerHTML = `
            <span class="hist-label ${s.prediction}">${s.prediction.toUpperCase()}</span>
            <span class="hist-conf">${(s.confidence * 100).toFixed(1)}%</span>
            ${s.drift_detected ? '<span class="hist-drift">⚠ drift</span>' : ''}
            <span class="hist-date">${new Date(s.created_at).toLocaleString()}</span>
        `;
        list.appendChild(li);
    }
}

// ─── Recording ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    // Check if already logged in
    const user = await Api.me();
    if (user) {
        await initApp();
    }

    const recordBtn = document.getElementById('record-btn');
    const stopBtn   = document.getElementById('stop-btn');
    const statusText = document.getElementById('status-text');
    const predictionResult = document.getElementById('prediction-result');

    let audioContext, microphone, analyzer;
    let isRecording = false;
    let currentSessionFeatures = [];
    let recordingStart = null;

    recordBtn.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            microphone = audioContext.createMediaStreamSource(stream);
            recordingStart = Date.now();

            analyzer = Meyda.createMeydaAnalyzer({
                audioContext,
                source: microphone,
                bufferSize: 1024,
                featureExtractors: ['mfcc', 'rms', 'spectralCentroid', 'amplitudeSpectrum'],
                callback: features => {
                    if (!isRecording) return;
                    const spec = features.amplitudeSpectrum;
                    const total = spec.reduce((a, b) => a + b, 0);
                    let hf = 0;
                    for (let i = 128; i < spec.length; i++) hf += spec[i];
                    const hfRatio = total > 0 ? hf / total : 0;
                    currentSessionFeatures.push([...features.mfcc, features.rms, features.spectralCentroid, hfRatio]);
                },
            });

            isRecording = true;
            currentSessionFeatures = [];
            analyzer.start();
            statusText.textContent = 'Recording… speak, cough, or breathe.';
            recordBtn.disabled = true;
            stopBtn.disabled = false;
        } catch (err) {
            statusText.textContent = 'Microphone access denied.';
        }
    });

    stopBtn.addEventListener('click', async () => {
        isRecording = false;
        analyzer.stop();
        audioContext?.close();
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        statusText.textContent = 'Processing…';

        const durationMs = Date.now() - recordingStart;
        let features = currentSessionFeatures;
        const MAX_FRAMES = 60;

        if (!features.length) { statusText.textContent = 'No audio captured.'; return; }
        if (features.length < MAX_FRAMES) {
            const pad = new Array(16).fill(0);
            while (features.length < MAX_FRAMES) features.push(pad);
        } else {
            features = features.slice(0, MAX_FRAMES);
        }

        const pred = await vocalModel.predict(features);
        predictionResult.textContent = `${pred.class.toUpperCase()} · ${(pred.confidence * 100).toFixed(1)}%`;
        statusText.textContent = 'Ready.';

        // Persist to backend if logged in
        try {
            const saved = await Api.saveSession(pred.class, pred.confidence, durationMs, features);
            if (saved.drift_detected) {
                predictionResult.innerHTML += ' <span style="color:var(--danger); font-size:0.85rem;">⚠ drift from baseline</span>';
            }
            await refreshBaseline();
            await refreshHistory();
        } catch (e) {
            console.warn('Could not save session (not logged in?):', e.message);
        }
    });
});
