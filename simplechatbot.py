from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import traceback

def main():
    print("Loading Phi-3-mini-4k-instruct model...")
    print("This may take a moment on first run...\n")
    model_name = "microsoft/Phi-3-mini-4k-instruct"
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
            attn_implementation="eager"
        )
        
        print("Model loaded successfully!")
        print("Enter your prompts below. Type 'x' to exit.\n")
        print("-" * 50)
        
        while True:
            user_prompt = input("\nYou: ").strip()
            
            if user_prompt.lower() == 'x':
                print("\nGoodbye!")
                break
            
            if not user_prompt:
                continue
            
            messages = [{"role": "user", "content": user_prompt}]
            
            tokenized = tokenizer.apply_chat_template(
                messages,
                return_tensors="pt",
                add_generation_prompt=True
            )

            if isinstance(tokenized, dict):
                inputs = tokenized["input_ids"]
            else:
                inputs = tokenized

            input_len = inputs.shape[1]
            device = next(model.parameters()).device
            inputs = inputs.to(device)

            print("\nAssistant: ", end="", flush=True)

            with torch.no_grad():
                outputs = model.generate(
                    inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            
            # Decode only the newly generated tokens
            new_tokens = outputs[0][input_len:]
            response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

            if response:
                print(response)
            else:
                # Fallback: decode the full output and strip the prompt
                full = tokenizer.decode(outputs[0], skip_special_tokens=True)
                prompt_text = tokenizer.decode(inputs[0], skip_special_tokens=True)
                response = full[len(prompt_text):].strip()
                print(response if response else "(no response generated)")
            
    except Exception as e:
        print(f"\n--- ERROR ---")
        traceback.print_exc()
        print(f"-------------")

if __name__ == "__main__":
    main()