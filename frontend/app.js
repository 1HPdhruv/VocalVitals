document.addEventListener('DOMContentLoaded', async () => {
    const recordBtn = document.getElementById('record-btn');
    const stopBtn = document.getElementById('stop-btn');
    const statusText = document.getElementById('status-text');
    const predictionResult = document.getElementById('prediction-result');
    const baselineStatus = document.getElementById('baseline-status');

    let audioContext;
    let microphone;
    let analyzer;
    let processor;
    let isRecording = false;

    // Feature collection
    let currentSessionFeatures = [];

    const vocalModel = new VocalVitalsModel();
    statusText.innerText = "Loading model...";
    await vocalModel.loadModel();
    statusText.innerText = "Ready. Press Start Recording.";

    // Baseline Tracking (Phase 6)
    function checkBaseline(prediction) {
        let baseline = localStorage.getItem('vocalVitalsBaseline');
        if (!baseline) {
            // Store first cough as baseline
            if (prediction.class === 'cough' && prediction.confidence > 0.8) {
                localStorage.setItem('vocalVitalsBaseline', JSON.stringify({
                    date: new Date().toISOString(),
                    confidence: prediction.confidence
                }));
                baselineStatus.innerText = "Baseline established just now.";
                baselineStatus.style.color = "var(--success)";
            } else {
                baselineStatus.innerText = "Awaiting strong cough to set baseline.";
            }
        } else {
            baseline = JSON.parse(baseline);
            baselineStatus.innerText = `Baseline set on ${new Date(baseline.date).toLocaleDateString()}`;
            
            // Drift logic
            if (prediction.class === 'cough') {
                if (prediction.confidence < baseline.confidence * 0.7) {
                    predictionResult.innerHTML += ' <span style="color:var(--danger); font-size:0.8rem;">(Significant drift from baseline)</span>';
                }
            }
        }
    }

    recordBtn.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            microphone = audioContext.createMediaStreamSource(stream);
            
            // Setup Meyda
            analyzer = Meyda.createMeydaAnalyzer({
                audioContext: audioContext,
                source: microphone,
                bufferSize: 1024,
                featureExtractors: ['mfcc', 'rms', 'spectralCentroid', 'amplitudeSpectrum'],
                callback: features => {
                    if (!isRecording) return;
                    
                    // Construct 16-dim vector to match python: 13 MFCCs + RMS + Centroid + HF Ratio
                    // Meyda's MFCCs return 13 values
                    const mfcc = features.mfcc;
                    const rms = features.rms;
                    const centroid = features.spectralCentroid;
                    
                    // HF Ratio calculation (rough approximation for > 2000Hz)
                    // Sample rate 16000, Nyquist 8000. 512 bins. 2000Hz is at bin 128
                    const spec = features.amplitudeSpectrum;
                    const totalEnergy = spec.reduce((a, b) => a + b, 0);
                    let hfEnergy = 0;
                    for(let i = 128; i < spec.length; i++) {
                        hfEnergy += spec[i];
                    }
                    const hfRatio = totalEnergy > 0 ? (hfEnergy / totalEnergy) : 0;

                    const frameVector = [...mfcc, rms, centroid, hfRatio];
                    currentSessionFeatures.push(frameVector);
                }
            });

            isRecording = true;
            currentSessionFeatures = [];
            analyzer.start();
            
            statusText.innerText = "Recording... please cough or breathe.";
            recordBtn.disabled = true;
            stopBtn.disabled = false;

        } catch (err) {
            console.error(err);
            statusText.innerText = "Microphone access denied.";
        }
    });

    stopBtn.addEventListener('click', async () => {
        isRecording = false;
        analyzer.stop();
        if (audioContext) {
            audioContext.close();
        }
        
        recordBtn.disabled = false;
        stopBtn.disabled = true;
        statusText.innerText = "Processing audio...";

        // Pad or truncate to MAX_FRAMES (60)
        let features = currentSessionFeatures;
        const MAX_FRAMES = 60;
        
        if (features.length === 0) {
            statusText.innerText = "No audio recorded.";
            return;
        }

        if (features.length < MAX_FRAMES) {
            const padLen = MAX_FRAMES - features.length;
            const zeroFrame = new Array(16).fill(0);
            for(let i=0; i<padLen; i++) features.push(zeroFrame);
        } else {
            features = features.slice(0, MAX_FRAMES);
        }

        const pred = await vocalModel.predict(features);
        predictionResult.innerText = `${pred.class.toUpperCase()} (${(pred.confidence * 100).toFixed(1)}%)`;
        statusText.innerText = "Ready.";

        checkBaseline(pred);
    });

    // Check baseline on load
    checkBaseline({ class: 'none', confidence: 0 });
});
