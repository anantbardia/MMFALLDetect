import os

base_dir = r"C:\Users\Anant\.cache\kagglehub\datasets\uttejkumarkandagatla\fall-detection-dataset\versions\1\fall_dataset\labels\train"
files = [f for f in os.listdir(base_dir) if f.endswith('.txt')]

class_counts = {}
for f in files[:100]: # Sample 100
    with open(os.path.join(base_dir, f)) as txt:
        line = txt.readline().strip()
        if line:
            cid = line.split()[0]
            class_counts[cid] = class_counts.get(cid, 0) + 1

print(f"Classes found in sample: {class_counts}")
