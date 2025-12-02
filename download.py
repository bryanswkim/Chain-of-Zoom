# download.py
import os
import shutil
import subprocess
import modal

VOL_NAME = "chain-of-zoom-weights"
MODEL_DIR = "/models"

# Define volume
volume = modal.Volume.from_name(VOL_NAME, create_if_missing=True)

# Define image
# We install 'curl' and 'git' to support the installation of the hf CLI
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("curl", "git")
    .pip_install("huggingface_hub")
)

app = modal.App("chain-of-zoom-downloader", image=image)

@app.function(
    volumes={MODEL_DIR: volume},
    timeout=3600
)
def download_models():
    from huggingface_hub import hf_hub_download, snapshot_download

    print(f"Starting robust download to {MODEL_DIR}...")
    
    # Create directories
    dirs = [
        f"{MODEL_DIR}/ckpt/SR_LoRA",
        f"{MODEL_DIR}/ckpt/SR_VAE",
        f"{MODEL_DIR}/ckpt/DAPE",
        f"{MODEL_DIR}/ckpt/RAM",
        f"{MODEL_DIR}/ckpt/VLM_LoRA",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # --- 1. DAPE Model (Use 'hf' CLI for robust Xet/LFS support) ---
    print("Downloading DAPE model from rakeshvallangi...")
    
    if not os.path.exists(f"{MODEL_DIR}/ckpt/DAPE/DAPE.pth"):
        # Install hf CLI (it's a single binary, fast to install)
        print("Installing hf CLI...")
        subprocess.run("curl -LsSf https://hf.co/cli/install.sh | bash", shell=True, check=True)
        
        # Download using the official command you shared
        # This downloads to a cache folder usually, or we can specify output
        # 'hf download repo_id filename --local-dir ...' is the modern way
        print("Running hf download...")
        try:
            # We assume the file inside your repo is named "DAPE.pth" (case sensitive)
            # If it is inside a subfolder in your repo, change the filename arg.
            subprocess.run(
                [
                    "/root/.local/bin/hf", "download", 
                    "rakeshvallangi/dape.pth", 
                    "--local-dir", f"{MODEL_DIR}/ckpt/DAPE"
                ], 
                check=True
            )
            print("DAPE downloaded successfully via CLI.")
        except subprocess.CalledProcessError:
            print("CLI download failed. Your repo might not have the file named exactly 'DAPE.pth' at root.")
            print("Attempting to download entire repo content just in case...")
            subprocess.run(
                [
                    "/root/.local/bin/hf", "download", 
                    "rakeshvallangi/dape.pth", 
                    "--local-dir", f"{MODEL_DIR}/ckpt/DAPE"
                ],
                check=True
            )

    # --- 2. RAM Model (Standard Download) ---
    print("Downloading RAM model...")
    if not os.path.exists(f"{MODEL_DIR}/ckpt/RAM/ram_swin_large_14m.pth"):
        hf_hub_download(
            repo_id="NGain/Medialab",
            filename="ram_swin_large_14m.pth",
            local_dir=f"{MODEL_DIR}/ckpt/RAM",
            local_dir_use_symlinks=False
        )

    # --- 3. SR Components (From Space) ---
    print("Downloading SR components from Space...")
    files_map = {
        "ckpt/SR_LoRA/model_20001.pkl": "alexnasa/Chain-of-Zoom",
        "ckpt/SR_VAE/vae_encoder_20001.pt": "alexnasa/Chain-of-Zoom"
    }
    for filename, repo_id in files_map.items():
        local_path = os.path.join(MODEL_DIR, filename)
        if not os.path.exists(local_path):
            hf_hub_download(
                repo_id=repo_id,
                repo_type="space",
                filename=filename,
                local_dir=MODEL_DIR,
                local_dir_use_symlinks=False
            )

    # --- 4. VLM LoRA (From Space) ---
    print("Downloading VLM LoRA...")
    if not os.path.exists(f"{MODEL_DIR}/ckpt/VLM_LoRA/checkpoint-10000"):
        snapshot_download(
            repo_id="alexnasa/Chain-of-Zoom",
            repo_type="space",
            allow_patterns=["ckpt/VLM_LoRA/checkpoint-10000/*"],
            local_dir=MODEL_DIR,
            local_dir_use_symlinks=False
        )

    print("SUCCESS: All models downloaded.")
    volume.commit()

if __name__ == "__main__":
    with app.run():
        download_models.remote()
