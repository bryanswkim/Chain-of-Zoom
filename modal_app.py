import os
import sys
import time
import logging
import shutil
import modal

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chain-of-zoom")

# --- Configuration ---
VOL_NAME = "COZ"
MODEL_DIR = "/models"
ckpt_volume = modal.Volume.from_name(VOL_NAME)

# Docker image environment
# Note: We define the image once.
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "libgl1", "libglib2.0-0", "procps")
    .pip_install(
        "torch==2.1.2",
        "torchvision==0.16.2",
        "diffusers==0.25.0",
        "transformers==4.36.2",
        "accelerate==0.25.0",
        "gradio==4.16.0",
        "peft==0.7.1",
        "numpy<2.0.0",
        "Pillow",
        "tqdm",
        "lpips",
        "omegaconf",
        "timm",
        "huggingface_hub",
        "sentencepiece"
    )
    # Run commands to setup repo structure
    .run_commands("git clone https://github.com/Rakesh-207/Chain-of-Zoom.git /root/coz_repo")
    .run_commands("cp -r /root/coz_repo/* /root/") 
    # Add local files LAST
    .add_local_file("osediff_sd3.py", remote_path="/root/osediff_sd3.py")
    .add_local_file("inference_coz_full.py", remote_path="/root/inference_coz_full.py")
)

app = modal.App("chain-of-zoom-coz", image=image)

@app.cls(
    gpu="A100", 
    volumes={MODEL_DIR: ckpt_volume}, 
    timeout=600,
    enable_memory_snapshot=True,
)
class ChainOfZoom:
    def __enter__(self):
        """
        This runs ONCE when the GPU container starts.
        """
        logger.info("=== Starting Cold Boot Setup (GPU) ===")
        start_time = time.time()

        try:
            # --- 1. Verify Files ---
            # (Kept your verification logic but shortened for brevity here, 
            # it effectively checks paths before loading)
            required_files = [
                f"{MODEL_DIR}/sd3_medium",
                f"{MODEL_DIR}/qwen_vl_3b",
                f"{MODEL_DIR}/ckpt/SR_LoRA/model_20001.pkl",
            ]
            for p in required_files:
                if not os.path.exists(p):
                    raise FileNotFoundError(f"Critical model file missing: {p}")

            # --- 2. Setup Environment ---
            sys.path.append("/root")
            import torch
            from osediff_sd3 import OSEDiffSD3TESTTILE, SD3Euler
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
            from peft import PeftModel
            from ram.models.ram_lora import ram
            
            self.device = "cuda"

            # --- 3. Load SD3 ---
            logger.info("Loading SD3...")
            self.sd3_model = SD3Euler(model_key=f"{MODEL_DIR}/sd3_medium", device='cuda')
            # Move to GPU and freeze
            self.sd3_model.text_enc1.to('cuda')
            self.sd3_model.text_enc2.to('cuda')
            self.sd3_model.text_enc3.to('cuda')
            self.sd3_model.transformer.to('cuda', dtype=torch.float32)
            self.sd3_model.vae.to('cuda', dtype=torch.float32)
            for p in [self.sd3_model.text_enc1, self.sd3_model.text_enc2, self.sd3_model.text_enc3, 
                      self.sd3_model.transformer, self.sd3_model.vae]:
                 p.requires_grad_(False)

            # --- 4. Initialize OSEDiff ---
            class MockArgs:
                lora_rank = 4
                lora_path = f"{MODEL_DIR}/ckpt/SR_LoRA/model_20001.pkl"
                vae_path = f"{MODEL_DIR}/ckpt/SR_VAE/vae_encoder_20001.pt"
                latent_tiled_size = 64
                latent_tiled_overlap = 16
                vae_encoder_tiled_size = 1024
                vae_decoder_tiled_size = 128
            
            self.args = MockArgs()
            self.model_test = OSEDiffSD3TESTTILE(self.args, self.sd3_model)

            # --- 5. Load Qwen VLM ---
            logger.info("Loading VLM...")
            vlm_path = f"{MODEL_DIR}/qwen_vl_3b"
            self.vlm_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                vlm_path, torch_dtype="auto", device_map="auto"
            )
            self.vlm_processor = AutoProcessor.from_pretrained(vlm_path)
            
            # Load VLM LoRA
            self.vlm_model = PeftModel.from_pretrained(
                self.vlm_model, f"{MODEL_DIR}/ckpt/VLM_LoRA/checkpoint-10000"
            )
            self.vlm_model = self.vlm_model.merge_and_unload()
            self.vlm_model.eval()

            # --- 6. Load RAM/DAPE ---
            logger.info("Loading DAPE...")
            self.dape = ram(
                pretrained=f"{MODEL_DIR}/ckpt/RAM/ram_swin_large_14m.pth",
                pretrained_condition=f"{MODEL_DIR}/ckpt/DAPE/DAPE.pth",
                image_size=384,
                vit='swin_l'
            )
            self.dape.eval().to("cuda")

            logger.info(f"Setup Complete in {time.time() - start_time:.2f}s")

        except Exception as e:
            logger.critical(f"GPU Setup FAILED: {e}")
            raise e

    @modal.method()
    def process_image(self, input_image_path, upscale_factor=4):
        # Runs on GPU
        import torch
        from PIL import Image
        from torchvision import transforms
        
        logger.info(f"Processing image: {input_image_path}")
        
        original_img = Image.open(input_image_path).convert("RGB")
        w, h = original_img.size
        new_w, new_h = int(w * upscale_factor), int(h * upscale_factor)
        
        # Resize input
        input_tensor = transforms.ToTensor()(
            original_img.resize((new_w, new_h), Image.LANCZOS)
        ).unsqueeze(0).to("cuda")
        
        # Temp paths for internal logic
        temp_full = f"/tmp/temp_full_{int(time.time())}.png"
        temp_patch = f"/tmp/temp_patch_{int(time.time())}.png"
        original_img.resize((new_w, new_h), Image.LANCZOS).save(temp_full)
        
        with torch.no_grad():
             # Call the model logic
             full_latent = self.model_test.create_full_latent(
                 input_tensor, 
                 self.vlm_model, 
                 self.vlm_processor, 
                 temp_full, 
                 temp_patch, 
                 "vlm"
             )
             output_img = self.model_test.decode_full_latent(full_latent.cpu())
             
        out_pil = transforms.ToPILImage()(output_img[0] * 0.5 + 0.5).clamp(0, 1)
        
        # Return bytes
        out_path = f"/tmp/out_{int(time.time())}.png"
        out_pil.save(out_path)
        with open(out_path, "rb") as f:
            return f.read()

# --- Web Server ---
@app.function(
    image=image, 
    max_containers=1,
    # Give the web container decent resources so Gradio doesn't choke
    cpu=2.0,
    memory=2048,
    timeout=3600,
)
@modal.web_server(port=8000, startup_timeout=300)
def gradio_app():
    import gradio as gr
    from PIL import Image
    import io
    
    # Instantiate the class handle. 
    # This is lightweight and does NOT start the GPU container yet.
    coz = ChainOfZoom()
    
    def predict(image, scale):
        if image is None: return None
        
        try:
            path = f"/tmp/gradio_in_{int(time.time())}.png"
            image.save(path)
            
            print("Calling remote GPU function...")
            # This is where the GPU container starts!
            res_bytes = coz.process_image.remote(path, upscale_factor=scale)
            
            return Image.open(io.BytesIO(res_bytes))
        except Exception as e:
            raise gr.Error(f"Processing failed: {str(e)}")

    with gr.Blocks() as demo:
        gr.Markdown("# Chain of Zoom: Full Image Super-Resolution")
        
        with gr.Row():
            inp = gr.Image(type="pil", label="Input")
            out = gr.Image(label="Output")
        
        scale = gr.Slider(2, 8, value=4, step=1, label="Upscale Factor")
        btn = gr.Button("Upscale")
        btn.click(predict, [inp, scale], [out])
        
    return demo
