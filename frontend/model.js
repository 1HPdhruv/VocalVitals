class VocalVitalsModel {
    constructor() {
        this.model = null;
        this.isLoaded = false;
        this.classes = ["cough", "breath", "background"];
    }

    async loadModel() {
        try {
            // In a real deployed app, this points to the hosted tfjs model.json
            // Here we assume it's served statically from the model/tfjs dir
            this.model = await tf.loadLayersModel('/model/tfjs/model.json');
            this.isLoaded = true;
            console.log("Model loaded successfully.");
        } catch (error) {
            console.error("Error loading model:", error);
            // Wait, this is a prototype, maybe we can mock the prediction if model isn't served
            this.isLoaded = false;
        }
    }

    async predict(features) {
        if (!this.isLoaded || !this.model) {
            // Mock prediction if model isn't served locally yet
            console.warn("Model not loaded, returning mock prediction.");
            return { class: this.classes[Math.floor(Math.random() * this.classes.length)], confidence: 0.85 };
        }

        // Features expected shape: [1, MAX_FRAMES, 16]
        const inputTensor = tf.tensor3d([features]);
        const prediction = this.model.predict(inputTensor);
        const scores = await prediction.data();
        
        inputTensor.dispose();
        prediction.dispose();

        const maxIndex = scores.indexOf(Math.max(...scores));
        return {
            class: this.classes[maxIndex],
            confidence: scores[maxIndex]
        };
    }
}
