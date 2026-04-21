import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle

df = pd.read_csv("fall_features.csv")
X = df.drop('class', axis=1).values
y = df['class'].values

# We noticed classes 0, 1, 2. Let's keep it robust.
num_classes = len(np.unique(y))
if num_classes < 2: num_classes = 2

scaler = StandardScaler()
X = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = Sequential([
    Dense(128, activation='relu', input_shape=(X.shape[1],)),
    Dropout(0.3),
    Dense(64, activation='relu'),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(num_classes, activation='softmax')
])

model.compile(optimizer='adam',
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy'])

print(f"Training Multi-class Neural Network for {num_classes} classes...")
model.fit(X_train, y_train, epochs=25, batch_size=32, validation_data=(X_test, y_test))

loss, acc = model.evaluate(X_test, y_test)
print(f"\nFinal Test Accuracy: {acc:.4f}")

model.save("cv_module/fall_model.keras")
with open("cv_module/scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)
    
print("Saved fall_model.keras and scaler.pkl to cv_module/")
