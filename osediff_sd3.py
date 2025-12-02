import os
import sys
sys.path.append(os.getcwd())
import yaml
import copy
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Optional
import numpy as np
import lpips
from torchvision import transforms
from PIL import Image
from peft import LoraConfig, get_peft_model

from copy import deepcopy
from tqdm import tqdm

from diffusers import StableDiffusion3Pipeline
from lora.lora_layers import LoraInjectedLinear, LoraInjectedConv2d

from utils.vaehook import VAEHook


def inject_lora_vae(vae, lora_rank=4, init_lora_weights="gaussian", verbose=False):
    """
    Inject LoRA into the VAE's encoder
    """
    from peft import get_peft_model  # ✅ ADD THIS IMPORT
    
    vae.requires_grad_(False)
    vae.train()
    
    # Identify modules to LoRA-ify in the encoder
    l_grep = ["conv1", "conv2", "conv_in", "conv_shortcut",
              "conv", "conv_out", "to_k", "to_q", "to_v", "to_out.0"]
    
    l_target_modules_encoder = []
    for n, p in vae.named_parameters():
        if "bias" in n or "norm" in n:
            continue
        for pattern in l_grep:
            if (pattern in n) and ("encoder" in n):
                l_target_modules_encoder.append(n.replace(".weight", ""))
            elif ("quant_conv" in n) and ("post_quant_conv" not in n):
                l_target_modules_encoder.append(n.replace(".weight", ""))
    
    if verbose:
        print("The following VAE parameters will get LoRA:")
        print(l_target_modules_encoder)
    
    # Create and add a LoRA adapter
    lora_conf_encoder = LoraConfig(
        r=lora_rank,
        init_lora_weights=init_lora_weights,
        target_modules=l_target_modules_encoder
    )
    
    adapter_name = "default_encoder"
    
    # ✅ FIX: Use get_peft_model instead of add_adapter
    try:
        # Check if already a PeftModel
        if hasattr(vae, 'peft_config'):
            if adapter_name in vae.peft_config:
                print(f"Adapter '{adapter_name}' already exists. Skipping injection.")
                return vae, l_target_modules_encoder
            else:
                vae.add_adapter(lora_conf_encoder, adapter_name=adapter_name)
        else:
            # Convert to PEFT model first
            vae = get_peft_model(vae, lora_conf_encoder)
            vae.set_adapter(adapter_name)
    except Exception as e:
        print(f"Warning: PEFT injection failed: {e}")
        print("Falling back to no VAE LoRA (using pretrained weights only)")
        # Don't fail - just use the VAE without LoRA
    
    return vae, l_target_modules_encoder

def _find_modules(model, ancestor_class=None, search_class=[nn.Linear], exclude_children_of=[LoraInjectedLinear]):
    # Get the targets we should replace all linears under
    if ancestor_class is not None:
        ancestors = (
            module
            for module in model.modules()
            if module.__class__.__name__ in ancestor_class
        )
    else:
        # this, in case you want to naively iterate over all modules.
        ancestors = [module for module in model.modules()]

    for ancestor in ancestors:
        for fullname, module in ancestor.named_modules():
            if any([isinstance(module, _class) for _class in search_class]):
                *path, name = fullname.split(".")
                parent = ancestor
                while path:
                    parent = parent.get_submodule(path.pop(0))
                if exclude_children_of and any(
                    [isinstance(parent, _class) for _class in exclude_children_of]
                ):
                    continue
                yield parent, name, module

def inject_lora(model, ancestor_class, loras=None, r:int=4, dropout_p:float=0.0, scale:float=1.0, verbose:bool=False):
    
    model.requires_grad_(False)
    model.train()
    
    names = []
    require_grad_params = []  # to be updated

    total_lora_params = 0  

    if loras is not None:
        loras = torch.load(loras, map_location=model.device, weights_only=True)
        loras = [lora.float() for lora in loras]

    for _module, name, _child_module in _find_modules(model, ancestor_class):  # SiLU + Linear Block
        weight = _child_module.weight
        bias = _child_module.bias

        if verbose:
            print(f'LoRA Injection : injecting lora into {name}')

        _tmp = LoraInjectedLinear(
            _child_module.in_features,
            _child_module.out_features,
            _child_module.bias is not None,
            r=r,
            dropout_p=dropout_p,
            scale=scale,
        )
        _tmp.linear.weight = nn.Parameter(weight.float())
        if bias is not None:
            _tmp.linear.bias = nn.Parameter(bias.float())
        
        # switch the module
        _tmp.to(device=_child_module.weight.device, dtype=torch.float) # keep as float / mixed precision
        _module._modules[name] = _tmp

        require_grad_params.append(_module._modules[name].lora_up.parameters())
        require_grad_params.append(_module._modules[name].lora_down.parameters())

        if loras != None:
            _module._modules[name].lora_up.weight = nn.Parameter(loras.pop(0))
            _module._modules[name].lora_down.weight = nn.Parameter(loras.pop(0))

        _module._modules[name].lora_up.weight.requires_grad = True
        _module._modules[name].lora_down.weight.requires_grad = True
        names.append(name)

        if verbose:
            # -------- Count LoRA parameters just added --------
            lora_up_count = sum(p.numel() for p in _tmp.lora_up.parameters())
            lora_down_count = sum(p.numel() for p in _tmp.lora_down.parameters())
            lora_total_for_this_layer = lora_up_count + lora_down_count
            total_lora_params += lora_total_for_this_layer
            print(f"  Added {lora_total_for_this_layer} params "
                  f"(lora_up={lora_up_count}, lora_down={lora_down_count})")
    
    if verbose:
        print(f"Total new LoRA parameters added: {total_lora_params}")
    
    return require_grad_params, names

def add_mp_hook(transformer):
    '''
    For mixed precision of LoRA. (i.e. keep LoRA as float and others as half)
    '''
    def pre_hook(module, input):
        return input.float()
    
    def post_hook(module, input, output):
        return output.half()

    hooks = []
    for _module, name, _child_module in _find_modules(transformer):
        if isinstance(_child_module, LoraInjectedLinear):
            hook = _child_module.lora_up.register_forward_pre_hook(pre_hook)
            hooks.append(hook)
            hook = _child_module.lora_down.register_forward_hook(post_hook)
            hooks.append(hook)
    
    return transformer, hooks

def compute_density_for_timestep_sampling(
    weighting_scheme: str, batch_size: int, logit_mean: float = 0.0, logit_std: float = 1.0, mode_scale: Optional[float] = None
):
    """
    Compute the density for sampling the timesteps when doing SD3 training.

    Courtesy: This was contributed by Rafie Walker in https://github.com/huggingface/diffusers/pull/8528.

    SD3 paper reference: https://arxiv.org/abs/2403.03206v1.
    """
    if weighting_scheme == "logit_normal":
        # See 3.1 in the SD3 paper ($rf/lognorm(0.00,1.00)$).
        u = torch.normal(mean=logit_mean, std=logit_std, size=(batch_size,), device="cpu")
        u = torch.nn.functional.sigmoid(u)
    elif weighting_scheme == "mode":
        u = torch.rand(size=(batch_size,), device="cpu")
        u = 1 - u - mode_scale * (torch.cos(math.pi * u / 2) ** 2 - 1 + u)
    else:
        u = torch.rand(size=(batch_size,), device="cpu")
    return u

def compute_loss_weighting_for_sd3(weighting_scheme: str, sigmas):
    """
    Computes loss weighting scheme for SD3 training.

    Courtesy: This was contributed by Rafie Walker in https://github.com/huggingface/diffusers/pull/8528.

    SD3 paper reference: https://arxiv.org/abs/2403.03206v1.
    """
    if weighting_scheme == "sigma_sqrt":
        weighting = (sigmas**-2.0).float()
    elif weighting_scheme == "cosmap":
        bot = 1 - 2 * sigmas + 2 * sigmas**2
        weighting = 2 / (math.pi * bot)
    else:
        weighting = torch.ones_like(sigmas)
    return weighting


class StableDiffusion3Base():
    def __init__(self, model_key:str='stabilityai/stable-diffusion-3-medium-diffusers', device='cuda', dtype=torch.float16):
        self.device = device
        self.dtype = dtype

        pipe = StableDiffusion3Pipeline.from_pretrained(model_key, torch_dtype=self.dtype)

        self.scheduler = pipe.scheduler

        self.tokenizer_1 = pipe.tokenizer
        self.tokenizer_2 = pipe.tokenizer_2
        self.tokenizer_3 = pipe.tokenizer_3
        self.text_enc_1 = pipe.text_encoder.to(device)
        self.text_enc_2 = pipe.text_encoder_2.to(device)
        self.text_enc_3 = pipe.text_encoder_3.to(device)

        self.vae=pipe.vae.to(device)

        self.transformer = pipe.transformer.to(device)
        self.transformer.eval()
        self.transformer.requires_grad_(False)

        self.vae_scale_factor = (
            2 ** (len(self.vae.config.block_out_channels)-1) if hasattr(self, "vae") and self.vae is not None else 8
        )

        del pipe

    def encode_prompt(self, prompt: List[str], batch_size:int=1) -> List[torch.Tensor]:
        '''
        We assume that
        1. number of tokens < max_length
        2. one prompt for one image
        '''
        # CLIP encode (used for modulation of adaLN-zero)
        # now, we have two CLIPs
        text_clip1_ids = self.tokenizer_1(prompt,
                                          padding="max_length",
                                          max_length=77,
                                          truncation=True,
                                          return_tensors='pt').input_ids
        text_clip1_emb = self.text_enc_1(text_clip1_ids.to(self.device), output_hidden_states=True)
        pool_clip1_emb = text_clip1_emb[0].to(dtype=self.dtype, device=self.device)
        text_clip1_emb = text_clip1_emb.hidden_states[-2].to(dtype=self.dtype, device=self.device)

        text_clip2_ids = self.tokenizer_2(prompt,
                                          padding="max_length",
                                          max_length=77,
                                          truncation=True,
                                          return_tensors='pt').input_ids
        text_clip2_emb = self.text_enc_2(text_clip2_ids.to(self.device), output_hidden_states=True)
        pool_clip2_emb = text_clip2_emb[0].to(dtype=self.dtype, device=self.device)
        text_clip2_emb = text_clip2_emb.hidden_states[-2].to(dtype=self.dtype, device=self.device)
        
        # T5 encode (used for text condition)
        text_t5_ids = self.tokenizer_3(prompt,
                                       padding="max_length",
                                       max_length=512,
                                       truncation=True,
                                       add_special_tokens=True,
                                       return_tensors='pt').input_ids
        text_t5_emb = self.text_enc_3(text_t5_ids.to(self.device))[0]
        text_t5_emb = text_t5_emb.to(dtype=self.dtype, device=self.device)

        # Merge
        clip_prompt_emb = torch.cat([text_clip1_emb, text_clip2_emb], dim=-1)
        clip_prompt_emb = torch.nn.functional.pad(
            clip_prompt_emb, (0, text_t5_emb.shape[-1] - clip_prompt_emb.shape[-1])
        )
        prompt_emb = torch.cat([clip_prompt_emb, text_t5_emb], dim=-2)
        pooled_prompt_emb = torch.cat([pool_clip1_emb, pool_clip2_emb], dim=-1)

        return prompt_emb, pooled_prompt_emb

    def initialize_latent(self, img_size:Tuple[int], batch_size:int=1, **kwargs):
        H, W = img_size
        lH, lW = H//self.vae_scale_factor, W//self.vae_scale_factor
        lC = self.transformer.config.in_channels
        latent_shape = (batch_size, lC, lH, lW)

        z = torch.randn(latent_shape, device=self.device, dtype=self.dtype)

        return z

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        z = self.vae.encode(image).latent_dist.sample()
        z = (z-self.vae.config.shift_factor) * self.vae.config.scaling_factor
        return z
    
    def decode(self, z: torch.Tensor) -> torch.Tensor:
        z = (z/self.vae.config.scaling_factor) + self.vae.config.shift_factor
        return self.vae.decode(z, return_dict=False)[0]
    
    
class SD3Euler(StableDiffusion3Base):
    def __init__(self, model_key:str='stabilityai/stable-diffusion-3-medium-diffusers', device='cuda'):
        super().__init__(model_key=model_key, device=device)

    def inversion(self, src_img, prompts: List[str], NFE:int, cfg_scale: float=1.0, batch_size: int=1):

        # encode text prompts
        prompt_emb, pooled_emb = self.encode_prompt(prompts, batch_size)
        null_prompt_emb, null_pooled_emb = self.encode_prompt([""], batch_size)

        # initialize latent
        src_img = src_img.to(device=self.device, dtype=self.dtype)
        with torch.no_grad():
            z = self.encode(src_img)
            z0 = z.clone()

        # timesteps (default option. You can make your custom here.)
        self.scheduler.set_timesteps(NFE, device=self.device)
        timesteps = self.scheduler.timesteps
        timesteps = torch.cat([timesteps, torch.zeros(1, device=self.device)])
        timesteps = reversed(timesteps)
        sigmas = timesteps / self.scheduler.config.num_train_timesteps

        # Solve ODE
        pbar = tqdm(timesteps[:-1], total=NFE, desc='SD3 Euler Inversion')
        for i, t in enumerate(pbar):
            timestep = t.expand(z.shape[0]).to(self.device)
            pred_v = self.predict_vector(z, timestep, prompt_emb, pooled_emb)
            if cfg_scale != 1.0:
                pred_null_v = self.predict_vector(z, timestep, null_prompt_emb, null_pooled_emb)
            else:
                pred_null_v = 0.0

            sigma = sigmas[i]
            sigma_next = sigmas[i+1]

            z = z + (sigma_next - sigma) * (pred_null_v + cfg_scale * (pred_v - pred_null_v))

        return z

    def sample(self, prompts: List[str], NFE:int, img_shape: Optional[Tuple[int]]=None, cfg_scale: float=1.0, batch_size: int = 1, latent:Optional[torch.Tensor]=None):
        imgH, imgW = img_shape if img_shape is not None else (512, 512)

        # encode text prompts
        with torch.no_grad():
            prompt_emb, pooled_emb = self.encode_prompt(prompts, batch_size)
            null_prompt_emb, null_pooled_emb = self.encode_prompt([""], batch_size)

        # initialize latent
        if latent is None:
            z = self.initialize_latent((imgH, imgW), batch_size)
        else:
            z = latent

        # timesteps (default option. You can make your custom here.)
        self.scheduler.set_timesteps(NFE, device=self.device)
        timesteps = self.scheduler.timesteps
        sigmas = timesteps / self.scheduler.config.num_train_timesteps

        # Solve ODE
        pbar = tqdm(timesteps, total=NFE, desc='SD3 Euler')
        for i, t in enumerate(pbar):
            timestep = t.expand(z.shape[0]).to(self.device)
            pred_v = self.predict_vector(z, timestep, prompt_emb, pooled_emb)
            if cfg_scale != 1.0:
                pred_null_v = self.predict_vector(z, timestep, null_prompt_emb, null_pooled_emb)
            else:
                pred_null_v = 0.0

            sigma = sigmas[i]
            sigma_next = sigmas[i+1] if i+1 < NFE else 0.0

            z = z + (sigma_next - sigma) * (pred_null_v + cfg_scale * (pred_v - pred_null_v))

        # decode
        with torch.no_grad():
            img = self.decode(z)
        return img


class OSEDiff_SD3_GEN(torch.nn.Module):
    def __init__(self, args, base_model):
        super().__init__()
        
        self.args = args
        self.model = base_model
        
        # Add lora to transformer
        print('Adding LoRA to OSEDiff_SD3_GEN')
        self.transformer_gen = copy.deepcopy(self.model.transformer)
        self.transformer_gen.to('cuda:1')
        
        self.transformer_gen.requires_grad_(False)
        self.transformer_gen.train()
        self.transformer_gen, hooks = add_mp_hook(self.transformer_gen)
        self.hooks = hooks

        lora_params, _ = inject_lora(self.transformer_gen, {"AdaLayerNormZero"}, r=args.lora_rank, verbose=False)
        for name, param in self.transformer_gen.named_parameters():
            if "lora_" in name:
                param.requires_grad = True   # LoRA up/down
            else:
                param.requires_grad = False  # everything else
        
        # Insert LoRA into VAE
        print("Adding LoRA to VAE")
        self.model.vae, self.lora_vae_modules_encoder = inject_lora_vae(self.model.vae, lora_rank=args.lora_rank, verbose=False)

    def predict_vector(self, z, t, prompt_emb, pooled_emb):
        v = self.transformer_gen(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v

    def forward(self, x_src, batch=None, args=None):
        
        z_src = self.model.encode(x_src.to(dtype=torch.float32, device=self.model.vae.device))
        z_src = z_src.to(self.transformer_gen.device)
        
        # calculate prompt_embeddings and neg_prompt_embeddings
        batch_size, _, _, _ = x_src.shape
        with torch.no_grad():
            prompt_embeds, pooled_embeds = self.model.encode_prompt(batch["prompt"], batch_size)
            neg_prompt_embeds, neg_pooled_embeds = self.model.encode_prompt(batch["neg_prompt"], batch_size)
        
        NFE = 1
        self.model.scheduler.set_timesteps(NFE, device=self.model.device)
        timesteps = self.model.scheduler.timesteps
        sigmas = timesteps / self.model.scheduler.config.num_train_timesteps
        sigmas = sigmas.to(self.transformer_gen.device)

        # Solve ODE
        i = 0
        t = timesteps[0]

        timestep = t.expand(z_src.shape[0]).to(self.transformer_gen.device)
        prompt_embeds = prompt_embeds.to(self.transformer_gen.device, dtype=torch.float32)
        pooled_embeds = pooled_embeds.to(self.transformer_gen.device, dtype=torch.float32)
        pred_v = self.predict_vector(z_src, timestep, prompt_embeds, pooled_embeds)
        pred_null_v = 0.0

        sigma = sigmas[i]
        sigma_next = sigmas[i+1] if i+1 < NFE else 0.0
        
        z_src = z_src + (sigma_next - sigma) * (pred_null_v + 1 * (pred_v - pred_null_v))
        
        output_image = self.model.decode(z_src.to(dtype=torch.float32, device=self.model.vae.device))

        return output_image, z_src, prompt_embeds, pooled_embeds


class OSEDiff_SD3_REG(torch.nn.Module):
    def __init__(self, args, base_model):
        super().__init__()
        
        self.args = args
        self.model = base_model
        self.transformer_org = self.model.transformer
        
        # Add lora to transformer
        print('Adding LoRA to OSEDiff_SD3_REG')
        self.transformer_reg = copy.deepcopy(self.transformer_org)
        self.transformer_reg.to('cuda:1')
        
        self.transformer_reg.requires_grad_(False)
        self.transformer_reg.train()
        self.transformer_reg, hooks = add_mp_hook(self.transformer_reg)
        self.hooks = hooks
        
        lora_params, _ = inject_lora(self.transformer_reg, {"AdaLayerNormZero"}, r=args.lora_rank, verbose=False)
        for name, param in self.transformer_reg.named_parameters():
            if "lora_" in name:
                param.requires_grad = True   # LoRA up/down
            else:
                param.requires_grad = False  # everything else
        
    def predict_vector_reg(self, z, t, prompt_emb, pooled_emb):
        v = self.transformer_reg(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v
    
    def predict_vector_org(self, z, t, prompt_emb, pooled_emb):
        v = self.transformer_org(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v

    def distribution_matching_loss(self, z0, prompt_embeds, pooled_embeds, global_step, args):
        
        with torch.no_grad():
            device = self.transformer_reg.device
            # get timesteps and sigma
            u = compute_density_for_timestep_sampling(
                        weighting_scheme="uniform",
                        batch_size=1,
                        logit_mean=0.0,
                        logit_std=1.0,
                        mode_scale=1.29,
                    )
            
            t_idx = (u*1000).long().to(device)
            self.model.scheduler.set_timesteps(1000, device=device)
            times = self.model.scheduler.timesteps
            t = times[t_idx]
            sigma = t / 1000
            
            # get noise and xt
            z0 = z0.to(device)
            noise = torch.randn_like(z0)
            sigma = sigma.half()
            zt = (1-sigma) * z0 + sigma * noise
            
            # Get x0_prediction of transformer_reg
            v_pred_reg = self.predict_vector_reg(zt, t, prompt_embeds.to(device), pooled_embeds.to(device))
            reg_model_pred = v_pred_reg * (-sigma) + zt         # this is x0_prediction for reg
            
            # Get x0_prediction of transformer_org
            org_device = self.transformer_org.device
            v_pred_org = self.predict_vector_org(zt.to(org_device), t.to(org_device), prompt_embeds.to(org_device), pooled_embeds.to(org_device))
            org_model_pred = v_pred_org * (-sigma.to(org_device)) + zt.to(org_device)         # this is x0_prediction for org
            
            # Visualization
            if global_step % 100 == 1:
                self.vsd_visualization(z0, noise, zt, reg_model_pred, org_model_pred, global_step, args)
            
        weighting_factor = torch.abs(z0 - org_model_pred.to(device)).mean(dim=[1, 2, 3], keepdim=True)

        grad = (reg_model_pred - org_model_pred.to(device)) / weighting_factor
        loss = F.mse_loss(z0, (z0 - grad).detach())

        return loss
    
    def vsd_visualization(self, z0, noise, zt, reg_model_pred, org_model_pred, global_step, args):
        #-------- Visualization --------#
        # 1. Visualize latents, noise, zt
        z0_img = self.model.decode(z0.to(dtype=torch.float32, device=self.model.vae.device))
        ns_img = self.model.decode(noise.to(dtype=torch.float32, device=self.model.vae.device))
        zt_img = self.model.decode(zt.to(dtype=torch.float32, device=self.model.vae.device))
        
        z0_img_pil = transforms.ToPILImage()(torch.clamp(z0_img[0].cpu(), -1.0, 1.0) * 0.5 + 0.5)
        ns_img_pil = transforms.ToPILImage()(torch.clamp(ns_img[0].cpu(), -1.0, 1.0) * 0.5 + 0.5)
        zt_img_pil = transforms.ToPILImage()(torch.clamp(zt_img[0].cpu(), -1.0, 1.0) * 0.5 + 0.5)
        
        # 2. Visualize reg_img, org_img
        reg_img = self.model.decode(reg_model_pred.to(dtype=torch.float32, device=self.model.vae.device))
        org_img = self.model.decode(org_model_pred.to(dtype=torch.float32, device=self.model.vae.device))
        
        reg_img_pil = transforms.ToPILImage()(torch.clamp(reg_img[0].cpu(), -1.0, 1.0) * 0.5 + 0.5)
        org_img_pil = transforms.ToPILImage()(torch.clamp(org_img[0].cpu(), -1.0, 1.0) * 0.5 + 0.5)
        
        # Concatenate images side by side
        w, h = z0_img_pil.width, z0_img_pil.height
        combined_image = Image.new('RGB', (w*5, h))
        combined_image.paste(z0_img_pil, (0, 0))
        combined_image.paste(ns_img_pil, (w, 0))
        combined_image.paste(zt_img_pil, (w*2, 0))
        combined_image.paste(reg_img_pil, (w*3, 0))
        combined_image.paste(org_img_pil, (w*4, 0))
        combined_image.save(os.path.join(args.output_dir, f'visualization/vsd/{global_step}.png'))
        #-------- Visualization --------#
    
    def diff_loss(self, z0, prompt_embeds, pooled_embeds, net_lpips, args):
        
        device = self.transformer_reg.device
        u = compute_density_for_timestep_sampling(
                        weighting_scheme="uniform",
                        batch_size=1,
                        logit_mean=0.0,
                        logit_std=1.0,
                        mode_scale=1.29,
                    )
        
        t_idx = (u*1000).long().to(device)
        self.model.scheduler.set_timesteps(1000, device=device)
        times = self.model.scheduler.timesteps
        t = times[t_idx]
        sigma = t / 1000
        
        z0 = z0.to(device)
        z0, prompt_embeds = z0.detach(), prompt_embeds.detach()
        noise = torch.randn_like(z0)
        sigma = sigma.half()
        zt = (1-sigma) * z0 + sigma * noise         # noisy latents

        # v-prediction
        v_pred = self.predict_vector_reg(zt, t, prompt_embeds.to(device), pooled_embeds.to(device))
        model_pred = v_pred * (-sigma) + zt
        target = z0
        
        loss_weight = compute_loss_weighting_for_sd3("logit_normal", sigma)
        diffusion_loss = loss_weight.float() * F.mse_loss(model_pred.float(), target.float()) 
        
        loss_d = diffusion_loss

        return loss_d.mean()

class OSEDiff_SD3_TEST(torch.nn.Module):
    def __init__(self, args, base_model):
        super().__init__()
        
        self.args = args
        self.model = base_model
        self.lora_path = args.lora_path
        self.vae_path = args.vae_path
        
        # Add lora to transformer
        print(f'Loading LoRA to Transformer from {self.lora_path}')
        self.model.transformer.requires_grad_(False)
        lora_params, _ = inject_lora(self.model.transformer, {"AdaLayerNormZero"}, loras=self.lora_path, r=args.lora_rank, verbose=False)
        for name, param in self.model.transformer.named_parameters():
            param.requires_grad = False
        
        # Insert LoRA into VAE
        print(f"Loading LoRA to VAE from {self.vae_path}")
        self.model.vae, self.lora_vae_modules_encoder = inject_lora_vae(self.model.vae, lora_rank=args.lora_rank, verbose=False)
        encoder_state_dict_fp16 = torch.load(self.vae_path, map_location="cpu")
        self.model.vae.encoder.load_state_dict(encoder_state_dict_fp16)

    def predict_vector(self, z, t, prompt_emb, pooled_emb):
        v = self.model.transformer(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v

    @torch.no_grad()
    def forward(self, x_src, prompt):
        
        z_src = self.model.vae.encode(x_src.to(dtype=torch.float32, device=self.model.vae.device)).latent_dist.sample() * self.model.vae.config.scaling_factor
        
        z_src = z_src.to(self.model.transformer.device)
        
        # calculate prompt_embeddings and neg_prompt_embeddings
        batch_size, _, _, _ = x_src.shape
        with torch.no_grad():
            prompt_embeds, pooled_embeds = self.model.encode_prompt([prompt], batch_size)
        
        self.model.scheduler.set_timesteps(1, device=self.model.device)
        timesteps = self.model.scheduler.timesteps

        # Solve ODE
        t = timesteps[0]
        timestep = t.expand(z_src.shape[0]).to(self.model.transformer.device)
        prompt_embeds = prompt_embeds.to(self.model.transformer.device, dtype=torch.float32)
        pooled_embeds = pooled_embeds.to(self.model.transformer.device, dtype=torch.float32)
        pred_v = self.predict_vector(z_src, timestep, prompt_embeds, pooled_embeds)
        
        z_src = z_src - pred_v
        
        with torch.no_grad():
            output_image = self.model.decode(z_src.to(dtype=torch.float32, device=self.model.vae.device))

        return output_image


class OSEDiff_SD3_TEST_efficient(torch.nn.Module):
    def __init__(self, args, base_model):
        super().__init__()
        
        self.args = args
        self.model = base_model
        self.lora_path = args.lora_path
        self.vae_path = args.vae_path
        
        # Add lora to transformer
        print(f'Loading LoRA to Transformer from {self.lora_path}')
        self.model.transformer.requires_grad_(False)
        lora_params, _ = inject_lora(self.model.transformer, {"AdaLayerNormZero"}, loras=self.lora_path, r=args.lora_rank, verbose=False)
        for name, param in self.model.transformer.named_parameters():
            param.requires_grad = False
        
        # Insert LoRA into VAE
        print(f"Loading LoRA to VAE from {self.vae_path}")
        self.model.vae, self.lora_vae_modules_encoder = inject_lora_vae(self.model.vae, lora_rank=args.lora_rank, verbose=False)
        encoder_state_dict_fp16 = torch.load(self.vae_path, map_location="cpu")
        self.model.vae.encoder.load_state_dict(encoder_state_dict_fp16)

    def predict_vector(self, z, t, prompt_emb, pooled_emb):
        v = self.model.transformer(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v

    @torch.no_grad()
    def forward(self, x_src, prompt):
        
        z_src = self.model.vae.encode(x_src.to(dtype=torch.float32, device=self.model.vae.device)).latent_dist.sample() * self.model.vae.config.scaling_factor
        
        z_src = z_src.to(self.model.transformer.device)
        
        # calculate prompt_embeddings
        batch_size, _, _, _ = x_src.shape
        prompt_embeds, pooled_embeds = self.model.encode_prompt([prompt], batch_size)
        
        self.model.scheduler.set_timesteps(1, device=self.model.device)
        timesteps = self.model.scheduler.timesteps

        # Solve ODE
        t = timesteps[0]
        timestep = t.expand(z_src.shape[0]).to(self.model.transformer.device)
        prompt_embeds = prompt_embeds.to(self.model.transformer.device, dtype=torch.float32)
        pooled_embeds = pooled_embeds.to(self.model.transformer.device, dtype=torch.float32)
        pred_v = self.predict_vector(z_src, timestep, prompt_embeds, pooled_embeds)
        z_src = z_src - pred_v
        
        output_image = self.model.decode(z_src.to(dtype=torch.float32, device=self.model.vae.device))

        return output_image


class OSEDiff_SD3_TEST_TILE(torch.nn.Module):
    def __init__(self, args, base_model):
        super().__init__()
        
        self.args = args
        self.model = base_model
        self.lora_path = args.lora_path
        self.vae_path = args.vae_path
        
        # Add lora to transformer
        print(f'Loading LoRA to Transformer from {self.lora_path}')
        self.model.transformer.requires_grad_(False)
        lora_params, _ = inject_lora(self.model.transformer, {"AdaLayerNormZero"}, loras=self.lora_path, r=args.lora_rank, verbose=False)
        for name, param in self.model.transformer.named_parameters():
            param.requires_grad = False
        
        # Insert LoRA into VAE
        print(f"Loading LoRA to VAE from {self.vae_path}")
        self.model.vae, self.lora_vae_modules_encoder = inject_lora_vae(self.model.vae, lora_rank=args.lora_rank, verbose=False)
        encoder_state_dict_fp16 = torch.load(self.vae_path, map_location="cpu")
        self.model.vae.encoder.load_state_dict(encoder_state_dict_fp16)
        
        # save original forward (only once)
        if not hasattr(self.model.vae.encoder, 'original_forward'):
            setattr(self.model.vae.encoder, 'original_forward', self.model.vae.encoder.forward)
        if not hasattr(self.model.vae.decoder, 'original_forward'):
            setattr(self.model.vae.decoder, 'original_forward', self.model.vae.decoder.forward)
        encoder_tile = args.vae_encoder_tiled_size
        decoder_tile = args.vae_decoder_tiled_size
        self.model.vae.encoder.forward = VAEHook(
            self.model.vae.encoder,
            tile_size=encoder_tile,
            is_decoder=False,
            fast_decoder=False,
            fast_encoder=True,
            color_fix=False,
            to_gpu=True
        )
        self.model.vae.decoder.forward = VAEHook(
            self.model.vae.decoder,
            tile_size=decoder_tile,
            is_decoder=True,
            fast_decoder=True,
            fast_encoder=False,
            color_fix=False,
            to_gpu=True
        )

    def predict_vector(self, z, t, prompt_emb, pooled_emb):
        v = self.model.transformer(hidden_states=z,
                             timestep=t,
                             pooled_projections=pooled_emb,
                             encoder_hidden_states=prompt_emb,
                             return_dict=False)[0]
        return v
    
    @torch.no_grad()
    def create_full_latent(self, x_full: torch.Tensor, vlm_model, vlm_processor, full_path, next_path, prompt_type) -> torch.Tensor:
        device = self.model.transformer.device
        # 1) encode to full latent (via VAEHook)
        z_full = self.model.vae.encode(x_full).latent_dist.sample() \
                * self.model.vae.config.scaling_factor
        z_full = z_full.to(device)
        B, C, H, W = z_full.shape

        # 2) grid size
        tsize = self.args.latent_tiled_size
        tover  = self.args.latent_tiled_overlap
        stride = tsize - tover
        rows = (H - tsize + stride - 1)//stride + 1
        cols = (W - tsize + stride - 1)//stride + 1
        print(f'TILE SIZE: {tsize}, TILE OVERLAP: {tover}, STRIDE: {stride}, ROWS: {rows}, COLS: {cols}')

        # 3) make gaussian weight patched [B,C,tsize,tsize]
        weights = self._make_gaussian(tsize, tsize, 1).to(z_full.device)

        # 4) collect all patches
        positions = []
        out_tiles = []
        timestep = self.model.scheduler.timesteps[0].expand(B).to(z_full.device)

        for i in range(rows):
            y0 = min(i*stride, H - tsize)
            for j in range(cols):
                x0 = min(j*stride, W - tsize)
                positions.append((y0, x0))
                patch = z_full[:, :, y0:y0+tsize, x0:x0+tsize]
                
                # decode and save patch for later usage
                patch_path = f'{next_path[:-4]}_patch_row{i}col{j}.png'
                patch_img = self.decode_full_latent(patch)
                patch_pil = transforms.ToPILImage()((patch_img[0] * 0.5 + 0.5).clamp(0,1))
                patch_pil.save(patch_path)
                
                # create prompt to explain patch (CoZ)
                prompt = self.create_prompt(vlm_model, vlm_processor, full_path, patch_path, prompt_type)
                print('PROMPT: ', prompt)
                prompt_emb, pooled_emb = self.model.encode_prompt([prompt], batch_size=B)
                prompt_emb = prompt_emb.to(z_full.device, dtype=torch.float32)
                pooled_emb = pooled_emb.to(z_full.device, dtype=torch.float32)
                
                v = self.predict_vector(patch, timestep, prompt_emb, pooled_emb)
                out_tiles.append(patch - v)

        # 5) accumulate + normalize
        z_out = torch.zeros_like(z_full)
        z_norm = torch.zeros_like(z_full)
        norm  = torch.zeros_like(z_full)

        for (y0,x0), tile in zip(positions, out_tiles):
            z_out[:, :, y0:y0+tsize, x0:x0+tsize] += tile
            z_norm[:, :, y0:y0+tsize, x0:x0+tsize] += tile * weights
            norm[:, :, y0:y0+tsize, x0:x0+tsize] += weights

        # 6) avoid division by zero and finalize
        eps = 1e-10
        z_norm = z_norm / (norm + eps)
        return z_norm, z_out

    @torch.no_grad()
    def decode_full_latent(self, z_full: torch.Tensor) -> torch.Tensor:
        """
        Decode the tiled full latent into an RGB image (with tiled VAE decoder).
        """
        z_full = z_full.to(self.model.vae.device)
        img = self.model.vae.decode(z_full / self.model.vae.config.scaling_factor).sample
        return img.clamp(-1,1)
    
    @torch.no_grad()
    def create_prompt(self, vlm_model, vlm_processor, full_path, patch_path, prompt_type):
        if prompt_type in ('vlm','vlm_base'):
            from qwen_vl_utils import process_vision_info
            
            message_text = None
            start_image_path = full_path
            input_image_path = patch_path
            
            message_text = "The second image is a zoom-in of the first image. Based on this knowledge, what is in the second image? Give me a set of words."
            messages = [
                {"role": "system", "content": f"{message_text}"},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": start_image_path},
                        {"type": "image", "image": input_image_path}
                    ]
                }
            ]

            text = vlm_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = vlm_processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            generated_ids = vlm_model.generate(**inputs, max_new_tokens=16)
            generated_ids_trimmed = [
                out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            output_text = vlm_processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )

            prompt_text = output_text[0]
            return prompt_text
        else:
            raise ValueError(f"Unknown prompt_type: {prompt_type}")
    
    def _make_gaussian(self, w, h, nb):
        from numpy import pi, exp, sqrt
        import numpy as np

        latent_width = w
        latent_height = h

        var = 0.01
        midpoint = (latent_width - 1) / 2       # -1 because index goes from 0 to latent_width - 1
        x_probs = [exp(-(x-midpoint)*(x-midpoint)/(latent_width*latent_width)/(2*var)) / sqrt(2*pi*var) for x in range(latent_width)]
        midpoint = latent_height / 2
        y_probs = [exp(-(y-midpoint)*(y-midpoint)/(latent_height*latent_height)/(2*var)) / sqrt(2*pi*var) for y in range(latent_height)]

        weights = np.outer(y_probs, x_probs)
        return torch.tile(torch.tensor(weights, device=self.model.vae.device), (nb, self.model.vae.config.latent_channels, 1, 1))
