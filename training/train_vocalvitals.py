import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from feature_extractor import extract_features
import tensorflowjs as tfjs

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "model")
CLASSES = ["cough", "breath", "background"]
MAX_FRAMES = 60 # ~2 seconds with hop_length 512 at 16kHz
NUM_FEATURES = 16

def load_dataset():
    X = []
    y = []
    for label_idx, cls in enumerate(CLASSES):
        cls_dir = os.path.join(DATA_DIR, cls)
        if not os.path.exists(cls_dir):
            continue
            
        for file in os.listdir(cls_dir):
            if file.endswith(".wav"):
                file_path = os.path.join(cls_dir, file)
                feats = extract_features(file_path)
                if feats is None:
                    continue
                
                # Pad or truncate to MAX_FRAMES
                if feats.shape[0] < MAX_FRAMES:
                    pad_width = MAX_FRAMES - feats.shape[0]
                    feats = np.pad(feats, ((0, pad_width), (0, 0)), mode='constant')
                else:
                    feats = feats[:MAX_FRAMES, :]
                    
                X.append(feats)
                y.append(label_idx)
                
    return np.array(X), np.array(y)

def build_model(input_shape, num_classes):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=input_shape),
        tf.keras.layers.LSTM(64, return_sequences=True),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.LSTM(32),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(num_classes, activation='softmax')
    ])
    
    model.compile(optimizer='adam', 
                  loss='sparse_categorical_crossentropy', 
                  metrics=['accuracy'])
    return model

def main():
    print("Loading dataset...")
    X, y = load_dataset()
    
    if len(X) == 0:
        print("No data found. Please run data_loader.py first.")
        return
        
    print(f"Loaded {len(X)} samples. Shape: {X.shape}")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = build_model((MAX_FRAMES, NUM_FEATURES), len(CLASSES))
    model.summary()
    
    print("Training model...")
    model.fit(X_train, y_train, epochs=20, batch_size=8, validation_data=(X_test, y_test))
    
    loss, acc = model.evaluate(X_test, y_test)
    print(f"Test Accuracy: {acc:.4f}")
    
    # Save standard Keras model
    os.makedirs(MODEL_DIR, exist_ok=True)
    keras_model_path = os.path.join(MODEL_DIR, "vocalvitals_model.h5")
    model.save(keras_model_path)
    
    # Save TF.js model
    tfjs_dir = os.path.join(MODEL_DIR, "tfjs")
    tfjs.converters.save_keras_model(model, tfjs_dir)
    print(f"Saved TF.js model to {tfjs_dir}")

if __name__ == "__main__":
    main()
