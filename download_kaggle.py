import kagglehub

# Download latest version
path = kagglehub.dataset_download("uttejkumarkandagatla/fall-detection-dataset")

print(f"__KAGGLE_PATH__={path}")
