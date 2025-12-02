import os
import sys
import time
import logging
import modal
import io

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

# Docker image environment - COMPREHENSIVE DEPENDENCIES
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install(
        "git", 
        "libgl1",           # OpenCV
        "libglib2.0-0",     # OpenCV
        "libsm6",           # OpenCV
        "libxext6",         # OpenCV
        "libxrender-dev",   # OpenCV
        "libgomp1",         # OpenMP for fairscale
        "procps"
    )
    .pip_install(
    # ========== CORE ML FRAMEWORKS ==========
    "torch==2.1.2",
    "torchvision==0.16.2",
    
    # ========== DIFFUSION & TRANSFORMERS ==========
    "diffusers==0.30.0",        # ✅ CHANGED: 0.28.0 → 0.30.0 (guaranteed SD3)
    "transformers==4.43.0",     # ✅ CHANGED: 4.40.0 → 4.43.0 (stable with diffusers 0.30)
    "accelerate==0.30.0",       # ✅ CHANGED: 0.28.0 → 0.30.0 (matches diffusers)
    "huggingface-hub==0.24.0",  # Keep same
    
    # ========== LORA & PEFT ==========
    "peft==0.11.0",             # ✅ CHANGED: 0.10.0 → 0.11.0 (compatible with transformers 4.43)
    "loralib==0.1.2",
    
    # ========== DISTRIBUTED TRAINING ==========
    "fairscale==0.4.13",
    
    # ========== VISION & VLM ==========
    "qwen-vl-utils==0.0.8",
    "timm==1.0.3",
    
    # ========== UTILITIES ==========
    "gradio==4.16.0",
    "Pillow==10.2.0",
    "numpy==1.26.4",
    "scipy==1.11.4",
    "opencv-python-headless==4.9.0.80",
    "einops==0.7.0",
    
    # ========== NLP & TOKENIZATION ==========
    "sentencepiece==0.2.0",
    "tokenizers==0.19.1",
    "regex==2024.7.24",
    
    # ========== IMAGE QUALITY ==========
    "lpips==0.1.4",
    
    # ========== OTHER ==========
    "tqdm==4.66.1",
    "omegaconf==2.3.0",
    "safetensors==0.4.5",       # ✅ CHANGED: 0.4.3 → 0.4.5 (for accelerate 0.30)
    "fsspec==2024.2.0"
)

    .run_commands("git clone https://github.com/Rakesh-207/Chain-of-Zoom.git /root/coz_repo")
    .run_commands("cp -r /root/coz_repo/* /root/")
    .add_local_file("osediff_sd3.py", remote_path="/root/osediff_sd3.py")
    .add_local_file("inference_coz_full.py", remote_path="/root/inference_coz_full.py")
)

app = modal.App("chain-of-zoom-coz", image=image)

@app.cls(
    gpu="A100",
    volumes={MODEL_DIR: ckpt_volume},
    timeout=1200,
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True}
)
class ChainOfZoom:
    
    @modal.enter(snap=True)
    def setup(self):
        """
        Loads models into GPU memory during the snapshot phase.
        """
        logger.info("=== Starting Snapshot Setup (GPU) ===")
        start_time = time.time()
        
        try:
            # 1. Environment Setup
            sys.path.append("/root")
            import torch
            from osediff_sd3 import OSEDiff_SD3_TEST_TILE, SD3Euler
            # ✅ CRITICAL FIX: Use the CORRECT import name
            from transformers import AutoModelForVision2Seq, AutoProcessor
            from peft import PeftModel
            from ram.models.ram_lora import ram
            
            self.device = "cuda"
            logger.info(f"✅ Imports successful")
            
            # 2. Load SD3
            logger.info("Loading SD3...")
            sd3_path = f"{MODEL_DIR}/sd3_medium_diffusers"
            if not os.path.exists(sd3_path):
                raise FileNotFoundError(f"SD3 model not found at {sd3_path}")
            
            self.sd3_model = SD3Euler(model_key=sd3_path, device='cuda')
            logger.info(f"✅ SD3 loaded from {sd3_path}")
            
            # Move to GPU and freeze
            self.sd3_model.text_enc_1.to('cuda')
            self.sd3_model.text_enc_2.to('cuda')
            self.sd3_model.text_enc_3.to('cuda')
            self.sd3_model.transformer.to('cuda', dtype=torch.float32)
            self.sd3_model.vae.to('cuda', dtype=torch.float32)
            
            for p in [self.sd3_model.text_enc_1, self.sd3_model.text_enc_2, self.sd3_model.text_enc_3,
                      self.sd3_model.transformer, self.sd3_model.vae]:
                p.requires_grad_(False)
            
            logger.info("✅ SD3 components moved to GPU and frozen")
            
            # 3. Initialize OSEDiff
            class MockArgs:
                lora_rank = 4
                lora_path = f"{MODEL_DIR}/ckpt/SR_LoRA/model_20001.pkl"
                vae_path = f"{MODEL_DIR}/ckpt/SR_VAE/vae_encoder_20001.pt"
                latent_tiled_size = 64
                latent_tiled_overlap = 16
                vae_encoder_tiled_size = 1024
                vae_decoder_tiled_size = 128
            
            self.args = MockArgs()
            
            # Verify checkpoint files exist
            if not os.path.exists(self.args.lora_path):
                raise FileNotFoundError(f"SR LoRA not found: {self.args.lora_path}")
            if not os.path.exists(self.args.vae_path):
                raise FileNotFoundError(f"SR VAE not found: {self.args.vae_path}")
            
            self.model_test = OSEDiff_SD3_TEST_TILE(self.args, self.sd3_model)
            logger.info("✅ OSEDiff initialized with LoRA")
            
            # 4. Load Qwen VLM
            logger.info("Loading VLM...")
            vlm_path = f"{MODEL_DIR}/qwen_vl_3b"
            if not os.path.exists(vlm_path):
                raise FileNotFoundError(f"Qwen VL model not found at {vlm_path}")
            
            # ✅ Use AutoModelForVision2Seq for better compatibility
            self.vlm_model = AutoModelForVision2Seq.from_pretrained(
                vlm_path, 
                torch_dtype="auto", 
                device_map="auto",
                trust_remote_code=True  # ✅ Required for Qwen models
            )
            self.vlm_processor = AutoProcessor.from_pretrained(
                vlm_path,
                trust_remote_code=True
            )
            logger.info(f"✅ Qwen VLM loaded from {vlm_path}")
            
            # Load VLM LoRA  
            vlm_lora_path = f"{MODEL_DIR}/ckpt/VLM_LoRA"
            if os.path.exists(vlm_lora_path):
                # Check if adapter files exist
                adapter_config = os.path.join(vlm_lora_path, "adapter_config.json")
                if os.path.exists(adapter_config):
                    logger.info(f"Loading VLM LoRA from {vlm_lora_path}")
                    self.vlm_model = PeftModel.from_pretrained(self.vlm_model, vlm_lora_path)
                    self.vlm_model = self.vlm_model.merge_and_unload()
                    logger.info("✅ VLM LoRA merged")
                else:
                    logger.warning(f"VLM LoRA path exists but no adapter_config.json found")
            else:
                logger.warning(f"VLM LoRA path not found: {vlm_lora_path}")
            
            self.vlm_model.eval()
            
            # 5. Load RAM/DAPE
            logger.info("Loading DAPE...")
            ram_path = f"{MODEL_DIR}/ckpt/RAM/ram_swin_large_14m.pth"
            dape_path = f"{MODEL_DIR}/ckpt/DAPE/DAPE.pth"
            
            if not os.path.exists(ram_path):
                raise FileNotFoundError(f"RAM model not found: {ram_path}")
            if not os.path.exists(dape_path):
                raise FileNotFoundError(f"DAPE model not found: {dape_path}")
            
            self.dape = ram(
                pretrained=ram_path,
                pretrained_condition=dape_path,
                image_size=384,
                vit='swin_l'
            )
            self.dape.eval().to("cuda")
            logger.info("✅ DAPE loaded and moved to GPU")
            
            logger.info(f"🎉 GPU Snapshot Setup Complete in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            logger.critical(f"❌ Snapshot Setup FAILED: {e}")
            logger.critical(f"Error type: {type(e).__name__}")
            
            # Enhanced debugging
            if os.path.exists(MODEL_DIR):
                logger.info(f"📁 Contents of {MODEL_DIR}:")
                for root, dirs, files in os.walk(MODEL_DIR):
                    level = root.replace(MODEL_DIR, '').count(os.sep)
                    indent = ' ' * 2 * level
                    logger.info(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 2 * (level + 1)
                    for file in files[:10]:  # Limit to first 10 files per dir
                        logger.info(f"{subindent}{file}")
                    if len(files) > 10:
                        logger.info(f"{subindent}... and {len(files) - 10} more files")
            else:
                logger.critical(f"Directory {MODEL_DIR} does not exist!")
            
            raise e
    
    @modal.method()
    def process_image(self, image_bytes, upscale_factor=4):
        """Process image with Chain-of-Zoom upscaling"""
        # Defensive check: Ensure setup ran
        if not hasattr(self, "model_test"):
            logger.warning("⚠️ Snapshot state missing! Running manual setup...")
            self.setup()
        
        import torch
        from PIL import Image
        from torchvision import transforms
        
        # 1. Save bytes to temp file
        temp_input_path = f"/tmp/input_{int(time.time() * 1000)}.png"
        with open(temp_input_path, "wb") as f:
            f.write(image_bytes)
        
        logger.info(f"📥 Processing image: {temp_input_path}")
        
        try:
            original_img = Image.open(temp_input_path).convert("RGB")
            w, h = original_img.size
            logger.info(f"📐 Input size: {w}x{h}, Upscale: {upscale_factor}x")
            
            new_w, new_h = int(w * upscale_factor), int(h * upscale_factor)
            
            # Resize input
            input_tensor = transforms.ToTensor()(
                original_img.resize((new_w, new_h), Image.LANCZOS)
            ).unsqueeze(0).to("cuda") * 2 - 1  # Normalize to [-1, 1]
            
            # Temp paths for VLM processing
            temp_full = f"/tmp/temp_full_{int(time.time() * 1000)}.png"
            temp_patch = f"/tmp/temp_patch_{int(time.time() * 1000)}.png"
            
            # Save 512x512 reference for VLM
            original_img.resize((512, 512), Image.LANCZOS).save(temp_full)
            
            # Run Inference
            logger.info("🚀 Running Chain-of-Zoom inference...")
            with torch.no_grad():
                full_latent, _ = self.model_test.create_full_latent(
                    input_tensor,
                    self.vlm_model,
                    self.vlm_processor,
                    temp_full,
                    temp_patch,
                    "vlm"
                )
                output_img = self.model_test.decode_full_latent(full_latent).cpu()
            
            # Post-process
            out_pil = transforms.ToPILImage()((output_img[0] * 0.5 + 0.5).clamp(0, 1))
            logger.info(f"✅ Output size: {out_pil.size}")
            
            # Return as bytes
            img_byte_arr = io.BytesIO()
            out_pil.save(img_byte_arr, format='PNG')
            
            # Cleanup temp files
            for path in [temp_input_path, temp_full, temp_patch]:
                if os.path.exists(path):
                    os.remove(path)
            
            return img_byte_arr.getvalue()
            
        except Exception as e:
            logger.error(f"❌ Inference failed: {e}", exc_info=True)
            raise e


# --- Web Server (CPU Only) ---
@app.function(
    image=image,
    max_containers=1,
    cpu=2.0,
    memory=2048,
    timeout=3600,
)
@modal.web_server(port=8000, startup_timeout=300)
def gradio_app():
    import gradio as gr
    from PIL import Image
    import io
    
    def predict(image, scale):
        if image is None: 
            return None
        
        try:
            print("🎬 Starting prediction...")
            
            # Convert PIL to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Call GPU function
            coz = ChainOfZoom()
            print("📡 Calling remote GPU function...")
            res_bytes = coz.process_image.remote(img_bytes, upscale_factor=int(scale))
            
            print("✅ Processing complete!")
            return Image.open(io.BytesIO(res_bytes))
        
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise gr.Error(f"Processing failed: {str(e)}")
    
    with gr.Blocks(title="Chain-of-Zoom SR") as demo:
        gr.Markdown("# 🔬 Chain of Zoom: Full Image Super-Resolution")
        gr.Markdown("Upload an image and select upscale factor (2x-8x)")
        
        with gr.Row():
            with gr.Column():
                inp = gr.Image(type="pil", label="Input Image")
                scale = gr.Slider(2, 8, value=4, step=1, label="Upscale Factor")
                btn = gr.Button("🚀 Upscale", variant="primary")
            
            with gr.Column():
                out = gr.Image(label="Output Image")
        
        btn.click(predict, inputs=[inp, scale], outputs=[out])
        
        gr.Markdown("### ℹ️ Tips:\n- First run takes ~30s for cold start\n- Subsequent runs use GPU snapshot (~5s)\n- Works best on natural images")
    
    demo.launch(server_name="0.0.0.0", server_port=8000, prevent_thread_lock=True)
