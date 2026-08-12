import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from feature_extractor import extract_features

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CLASSES = ["cough", "breath", "background"]

# V3 synthetic assumptions (mean, std) for normalization/comparison
# Example hypothetical values that v3 might have used:
V3_ASSUMPTIONS = {
    "cough": {"rms": (0.6, 0.1), "centroid": (3000, 500), "mfcc0": (20, 5)},
    "breath": {"rms": (0.2, 0.05), "centroid": (1500, 300), "mfcc0": (10, 3)},
    "background": {"rms": (0.05, 0.02), "centroid": (2000, 800), "mfcc0": (5, 2)}
}

def analyze():
    print("Extracting features for distribution analysis...")
    features_dict = {cls: {"rms": [], "centroid": [], "mfcc0": []} for cls in CLASSES}
    
    for cls in CLASSES:
        cls_dir = os.path.join(DATA_DIR, cls)
        if not os.path.exists(cls_dir):
            continue
            
        for file in os.listdir(cls_dir):
            if file.endswith(".wav"):
                feats = extract_features(os.path.join(cls_dir, file))
                if feats is not None:
                    # feats shape: (frames, 16)
                    # 13 MFCCs (idx 0-12), RMS (idx 13), Centroid (idx 14), HF Ratio (idx 15)
                    features_dict[cls]["mfcc0"].extend(feats[:, 0].tolist())
                    features_dict[cls]["rms"].extend(feats[:, 13].tolist())
                    features_dict[cls]["centroid"].extend(feats[:, 14].tolist())
                    
    # Plotting
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "docs"), exist_ok=True)
    
    metrics = ["rms", "centroid", "mfcc0"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    for i, metric in enumerate(metrics):
        for cls in CLASSES:
            if len(features_dict[cls][metric]) > 0:
                sns.kdeplot(features_dict[cls][metric], ax=axes[i], label=f"Real {cls}", fill=True)
                
                # Plot v3 assumption as a dashed normal distribution
                mean, std = V3_ASSUMPTIONS[cls][metric]
                x = np.linspace(mean - 3*std, mean + 3*std, 100)
                y = (1/(std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean)/std)**2)
                # Scale roughly to match KDE amplitude
                axes[i].plot(x, y, linestyle="--", label=f"v3 Synth {cls}")
                
        axes[i].set_title(f"{metric.upper()} Distribution (Real vs v3 Synth)")
        axes[i].legend()
        
    plt.tight_layout()
    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "feature_distributions.png")
    plt.savefig(output_path)
    print(f"Saved distribution plot to {output_path}")

if __name__ == "__main__":
    analyze()
