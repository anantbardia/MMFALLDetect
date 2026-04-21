import os
import cv2
import mediapipe as mp
import pandas as pd
import numpy as np

# Kaggle Dataset Path
dataset_path = r"C:\Users\Anant\.cache\kagglehub\datasets\uttejkumarkandagatla\fall-detection-dataset\versions\1\fall_dataset"

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

data = []

print("Starting feature extraction...")
for split in ['train', 'val']:
    img_dir = os.path.join(dataset_path, "images", split)
    lbl_dir = os.path.join(dataset_path, "labels", split)
    
    if not os.path.exists(img_dir): continue
    
    for img_file in os.listdir(img_dir):
        if not img_file.lower().endswith(('.jpg', '.png', '.jpeg')): continue
        
        lbl_file = os.path.splitext(img_file)[0] + ".txt"
        lbl_path = os.path.join(lbl_dir, lbl_file)
        
        if not os.path.exists(lbl_path): continue
        
        # Read class
        with open(lbl_path, "r") as f:
            lines = f.readlines()
            if not lines: continue
            class_id = int(lines[0].split()[0])
            
        img_path = os.path.join(img_dir, img_file)
        image = cv2.imread(img_path)
        if image is None: continue
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)
        
        if results.pose_landmarks:
            row = [class_id]
            for lm in results.pose_landmarks.landmark:
                row.extend([lm.x, lm.y, lm.z, lm.visibility])
            data.append(row)

columns = ['class']
for i in range(33):
    columns.extend([f'x{i}', f'y{i}', f'z{i}', f'v{i}'])

df = pd.DataFrame(data, columns=columns)
df.to_csv("fall_features.csv", index=False)

print(f"Extracted {len(df)} samples.")
print(df['class'].value_counts())
