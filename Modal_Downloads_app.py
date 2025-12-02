import os
import modal

app = modal.App("sd3_medium")

# Define the volume and paths
volume = modal.Volume.from_name("COZ", create_if_missing=True)
MODEL_DIR = "/models"
HF_REPO = "stabilityai/stable-diffusion-3-medium"

# High-performance image with hf_transfer enabled
image = (
    modal.Image.debian_slim()
    # Install the specific high-speed transfer library
    .pip_install("huggingface_hub[hf_transfer]") 
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",  # <--- CRITICAL FOR SPEED
         "HF_TOKEN": "<replace with original token here>"    # Use if not using Modal Secrets  
    })
)

@app.function(
    image=image,
    volumes={MODEL_DIR: volume},
    timeout=3600,  # 1 hour max, though it should take <5 mins with hf_transfer
    secrets=[modal.Secret.from_name("HF_TOKEN")] # Ensure you have this secret or pass HF_TOKEN above
)
def download_flux2():
    from huggingface_hub import snapshot_download
    
    print(f"Starting high-speed download of {HF_REPO}...")
    
    # Download directly to the volume path
    snapshot_download(
        repo_id=HF_REPO,
        local_dir=f"{MODEL_DIR}/sd3_medium",
        # local_dir_use_symlinks=False  <-- REMOVED (deprecated/ignored)
    )
    print("Download completed successfully.")

