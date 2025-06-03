import os
import sys
sys.path.append(os.getcwd())
import glob
import argparse
import torch
from torchvision import transforms
import torchvision.transforms.functional as F
import numpy as np
from PIL import Image

from ram.models.ram_lora import ram
from ram import inference_ram as inference
from utils.wavelet_color_fix import adain_color_fix, wavelet_color_fix

tensor_transforms = transforms.Compose([
    transforms.ToTensor(),
])
ram_transforms = transforms.Compose([
    transforms.Resize((384, 384)),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def resize_and_center_crop(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    scale = size / min(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - size) // 2
    top  = (new_h - size) // 2
    return img.crop((left, top, left + size, top + size))

def get_validation_prompt(args, image, prompt_image_path, dape_model=None, vlm_model=None, device='cuda'):
    # prepare low-res tensor for SR input
    lq = tensor_transforms(image).unsqueeze(0).to(device)
    # select prompt source
    if args.prompt_type == "null":
        prompt_text = args.prompt or ""
    elif args.prompt_type == "dape":
        lq_ram = ram_transforms(lq).to(dtype=weight_dtype)
        captions = inference(lq_ram, dape_model)
        prompt_text = f"{captions[0]}, {args.prompt}," if args.prompt else captions[0]
    elif args.prompt_type in ("vlm"):
        message_text = None
        
        if args.rec_type == "recursive":
            message_text = "What is in this image? Give me a set of words."
            print(f'MESSAGE TEXT: {message_text}')
            messages = [
                {"role": "system", "content": f"{message_text}"},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": prompt_image_path}
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
            
        elif args.rec_type == "recursive_multiscale":
            start_image_path = prompt_image_path[0]
            input_image_path = prompt_image_path[1]
            message_text = "The second image is a zoom-in of the first image. Based on this knowledge, what is in the second image? Give me a set of words."
            print(f'START IMAGE PATH: {start_image_path}\nINPUT IMAGE PATH: {input_image_path}\nMESSAGE TEXT: {message_text}')
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
            print(f'MESSAGES\n{messages}')

            text = vlm_processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = vlm_processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )

        else:
            raise ValueError(f"VLM prompt generation not implemented for rec_type: {args.rec_type}")

        inputs = inputs.to("cuda")

        original_sr_devices = {}
        if args.efficient_memory and 'model' in globals() and hasattr(model, 'text_enc_1'): # Check if SR model is defined
            print("Moving SR model components to CPU for VLM inference.")
            original_sr_devices['text_enc_1'] = model.text_enc_1.device
            original_sr_devices['text_enc_2'] = model.text_enc_2.device
            original_sr_devices['text_enc_3'] = model.text_enc_3.device
            original_sr_devices['transformer'] = model.transformer.device
            original_sr_devices['vae'] = model.vae.device
            
            model.text_enc_1.to('cpu')
            model.text_enc_2.to('cpu')
            model.text_enc_3.to('cpu')
            model.transformer.to('cpu')
            model.vae.to('cpu')

        generated_ids = vlm_model.generate(**inputs, max_new_tokens=128)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = vlm_processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )

        prompt_text = f"{output_text[0]}, {args.prompt}," if args.prompt else output_text[0]

        if args.efficient_memory and 'model' in globals() and hasattr(model, 'text_enc_1'):
            print("Restoring SR model components to original devices.")
            model.text_enc_1.to(original_sr_devices['text_enc_1'])
            model.text_enc_2.to(original_sr_devices['text_enc_2'])
            model.text_enc_3.to(original_sr_devices['text_enc_3'])
            model.transformer.to(original_sr_devices['transformer'])
            model.vae.to(original_sr_devices['vae'])
    else:
        raise ValueError(f"Unknown prompt_type: {args.prompt_type}")
    return prompt_text, lq


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_image', '-i', type=str, default='preset/datasets/test_dataset/input', help='path to the input image')
    parser.add_argument('--output_dir', '-o', type=str, default='preset/datasets/test_dataset/output', help='the directory to save the output')
    parser.add_argument('--pretrained_model_name_or_path', type=str, default=None, help='sd model path')
    parser.add_argument('--seed', type=int, default=42, help='Random seed to be used')
    parser.add_argument('--process_size', type=int, default=512)
    parser.add_argument('--upscale', type=int, default=4)
    parser.add_argument('--align_method', type=str, choices=['wavelet', 'adain', 'nofix'], default='nofix')
    parser.add_argument('--lora_path', type=str, default=None, help='for LoRA of SR model')
    parser.add_argument('--vae_path', type=str, default=None)
    parser.add_argument('--prompt', type=str, default='', help='user prompts')
    parser.add_argument('--prompt_type', type=str, choices=['null','dape','vlm'], default='dape', help='type of prompt to use')
    parser.add_argument('--ram_path', type=str, default=None)
    parser.add_argument('--ram_ft_path', type=str, default=None)
    parser.add_argument('--save_prompts', type=bool, default=True)
    parser.add_argument('--mixed_precision', type=str, choices=['fp16', 'fp32'], default='fp16')
    parser.add_argument('--merge_and_unload_lora', action='store_true', help='merge lora weights before inference')
    parser.add_argument('--lora_rank', type=int, default=4)
    parser.add_argument('--vae_decoder_tiled_size', type=int, default=224)
    parser.add_argument('--vae_encoder_tiled_size', type=int, default=1024)
    parser.add_argument('--latent_tiled_size', type=int, default=96)
    parser.add_argument('--latent_tiled_overlap', type=int, default=32)
    parser.add_argument('--rec_type', type=str, choices=['nearest', 'bicubic','onestep','recursive','recursive_multiscale'], default='recursive', help='type of inference to use')
    parser.add_argument('--rec_num', type=int, default=4)
    parser.add_argument('--efficient_memory', default=False, action='store_true')
    args = parser.parse_args()

    global weight_dtype
    weight_dtype = torch.float32
    if args.mixed_precision == "fp16":
        weight_dtype = torch.float16

    # initialize SR model
    model = None
    if args.rec_type not in ('nearest', 'bicubic'):
        if not args.efficient_memory:
            from osediff_sd3 import OSEDiff_SD3_TEST, SD3Euler
            model = SD3Euler()
            model.text_enc_1.to('cuda:0')
            model.text_enc_2.to('cuda:0')
            model.text_enc_3.to('cuda:0')
            model.transformer.to('cuda:1', dtype=torch.float32)
            model.vae.to('cuda:1', dtype=torch.float32)
            for p in [model.text_enc_1, model.text_enc_2, model.text_enc_3, model.transformer, model.vae]:
                p.requires_grad_(False)
            model_test = OSEDiff_SD3_TEST(args, model)
        else:
            # For efficient memory, text encoders are moved to CPU/GPU on demand in get_validation_prompt
            # Only load transformer and VAE initially if they are always on GPU
            from osediff_sd3 import OSEDiff_SD3_TEST_efficient, SD3Euler
            model = SD3Euler()
            model.transformer.to('cuda', dtype=torch.float32)
            model.vae.to('cuda', dtype=torch.float32)
            for p in [model.text_enc_1, model.text_enc_2, model.text_enc_3, model.transformer, model.vae]:
                p.requires_grad_(False)
            model_test = OSEDiff_SD3_TEST_efficient(args, model)

    # gather input images
    if os.path.isdir(args.input_image):
        image_names = sorted(glob.glob(f'{args.input_image}/*.png'))
    else:
        image_names = [args.input_image]

    # load DAPE if needed
    DAPE = None
    if args.prompt_type == "dape":
        DAPE = ram(pretrained=args.ram_path,
                   pretrained_condition=args.ram_ft_path,
                   image_size=384,
                   vit='swin_l')
        DAPE.eval().to("cuda")
        DAPE = DAPE.to(dtype=weight_dtype)

    # load VLM pipeline if needed
    vlm_model = None
    global vlm_processor
    global process_vision_info
    vlm_processor = None
    if args.prompt_type == "vlm":
        from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
        from qwen_vl_utils import process_vision_info

        vlm_model_name = "Qwen/Qwen2.5-VL-3B-Instruct"
        print(f"Loading base VLM model: {vlm_model_name}")
        vlm_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            vlm_model_name,
            torch_dtype="auto",
            device_map="auto"
        )
        vlm_processor = AutoProcessor.from_pretrained(vlm_model_name)
        print('Base VLM LOADING COMPLETE')

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, 'per-sample'), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, 'per-scale'), exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, 'recursive'), exist_ok=True)
    print(f'There are {len(image_names)} images.')
    print(f'Align Method Used: {args.align_method}')
    print(f'Prompt Type: {args.prompt_type}')

    # inference loop
    for image_name in image_names:
        bname = os.path.basename(image_name)
        rec_dir = os.path.join(args.output_dir, 'per-sample', bname[:-4])
        os.makedirs(rec_dir, exist_ok=True)
        if args.save_prompts:
            txt_path = os.path.join(rec_dir, 'txt')
            os.makedirs(txt_path, exist_ok=True)
        print(f'#### IMAGE: {bname}')

        # first image
        os.makedirs(os.path.join(args.output_dir, 'per-scale', 'scale0'), exist_ok=True)
        first_image = Image.open(image_name).convert('RGB')
        first_image = resize_and_center_crop(first_image, args.process_size)
        first_image.save(f'{rec_dir}/0.png')
        first_image.save(os.path.join(args.output_dir, 'per-scale', 'scale0', bname))

        # recursion
        for rec in range(args.rec_num):
            print(f'RECURSION: {rec}')
            os.makedirs(os.path.join(args.output_dir, 'per-scale', f'scale{rec+1}'), exist_ok=True)
            start_image_path = None
            input_image_path = None
            prompt_image_path = None    # this will hold the path(s) for prompt extraction
            
            current_sr_input_image_pil = None

            if args.rec_type in ('nearest', 'bicubic', 'onestep'):
                start_image_pil_path = f'{rec_dir}/0.png'
                start_image_pil = Image.open(start_image_pil_path).convert('RGB')
                rscale = pow(args.upscale, rec+1)
                w, h = start_image_pil.size
                new_w, new_h = w // rscale, h // rscale
                
                # crop from the original highest-res image available for this step
                cropped_region = start_image_pil.crop(((w-new_w)//2, (h-new_h)//2, (w+new_w)//2, (h+new_h)//2))
                
                if args.rec_type == 'onestep':
                    current_sr_input_image_pil = cropped_region.resize((w, h), Image.BICUBIC)
                    prompt_image_path = f'{rec_dir}/0_input_for_{rec+1}.png'
                    current_sr_input_image_pil.save(prompt_image_path)
                elif args.rec_type == 'bicubic':
                    current_sr_input_image_pil = cropped_region.resize((w, h), Image.BICUBIC)
                    current_sr_input_image_pil.save(f'{rec_dir}/{rec+1}.png')
                    current_sr_input_image_pil.save(os.path.join(args.output_dir, 'per-scale', f'scale{rec+1}', bname))
                    continue
                elif args.rec_type == 'nearest':
                    current_sr_input_image_pil = cropped_region.resize((w, h), Image.NEAREST)
                    current_sr_input_image_pil.save(f'{rec_dir}/{rec+1}.png')
                    current_sr_input_image_pil.save(os.path.join(args.output_dir, 'per-scale', f'scale{rec+1}', bname))
                    continue

            elif args.rec_type == 'recursive':
                # input for SR is based on the previous SR output, cropped and resized
                prev_sr_output_path = f'{rec_dir}/{rec}.png'
                prev_sr_output_pil = Image.open(prev_sr_output_path).convert('RGB')
                rscale = args.upscale
                w, h = prev_sr_output_pil.size
                new_w, new_h = w // rscale, h // rscale
                cropped_region = prev_sr_output_pil.crop(((w-new_w)//2, (h-new_h)//2, (w+new_w)//2, (h+new_h)//2))
                current_sr_input_image_pil = cropped_region.resize((w, h), Image.BICUBIC)

                # this resized image is also the input for VLM
                input_image_path = f'{rec_dir}/{rec+1}_input.png'
                current_sr_input_image_pil.save(input_image_path)
                prompt_image_path = input_image_path

            elif args.rec_type == 'recursive_multiscale':
                prev_sr_output_path = f'{rec_dir}/{rec}.png'
                prev_sr_output_pil = Image.open(prev_sr_output_path).convert('RGB')
                rscale = args.upscale
                w, h = prev_sr_output_pil.size
                new_w, new_h = w // rscale, h // rscale
                cropped_region = prev_sr_output_pil.crop(((w-new_w)//2, (h-new_h)//2, (w+new_w)//2, (h+new_h)//2))
                current_sr_input_image_pil = cropped_region.resize((w, h), Image.BICUBIC)

                # save the SR input image (which is the "zoomed-in" image for VLM)
                zoomed_image_path = f'{rec_dir}/{rec+1}_input.png'
                current_sr_input_image_pil.save(zoomed_image_path)
                prompt_image_path = [prev_sr_output_path, zoomed_image_path]

            else:
                raise ValueError(f"Unknown recursion_type: {args.rec_type}")

            # generate prompts
            validation_prompt, lq = get_validation_prompt(args, current_sr_input_image_pil, prompt_image_path, DAPE, vlm_model)
            if args.save_prompts:
                with open(os.path.join(txt_path, f'{rec}.txt'), 'w', encoding='utf-8') as f:
                    f.write(validation_prompt)
            print(f'TAG: {validation_prompt}')

            # super-resolution
            with torch.no_grad():
                lq = lq * 2 - 1

                if args.efficient_memory and model is not None:
                    print("Ensuring SR model components are on CUDA for SR inference.")
                    if not isinstance(model_test, OSEDiff_SD3_TEST_efficient):
                        model.text_enc_1.to('cuda:0')
                        model.text_enc_2.to('cuda:0')
                        model.text_enc_3.to('cuda:0')
                    # transformer and VAE should already be on CUDA per initialization
                    model.transformer.to('cuda', dtype=torch.float32)
                    model.vae.to('cuda', dtype=torch.float32)

                output_image = model_test(lq, prompt=validation_prompt)
                output_image = torch.clamp(output_image[0].cpu(), -1.0, 1.0)
                output_pil = transforms.ToPILImage()(output_image * 0.5 + 0.5)
                if args.align_method == 'adain':
                    output_pil = adain_color_fix(target=output_pil, source=current_sr_input_image_pil)
                elif args.align_method == 'wavelet':
                    output_pil = wavelet_color_fix(target=output_pil, source=current_sr_input_image_pil)

            output_pil.save(f'{rec_dir}/{rec+1}.png')   # this is the SR output
            output_pil.save(os.path.join(args.output_dir, 'per-scale', f'scale{rec+1}', bname))

        # concatenate and save
        imgs = [Image.open(os.path.join(rec_dir, f'{i}.png')).convert('RGB') for i in range(args.rec_num+1)]
        concat = Image.new('RGB', (sum(im.width for im in imgs), max(im.height for im in imgs)))
        x_off = 0
        for im in imgs:
            concat.paste(im, (x_off, 0))
            x_off += im.width
        concat.save(os.path.join(rec_dir, bname))
        concat.save(os.path.join(args.output_dir, 'recursive', bname))