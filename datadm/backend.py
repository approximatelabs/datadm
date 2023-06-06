import torch
import guidance
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer


class StarcoderChat(guidance.llms.Transformers):
    def __init__(self, model_path="HuggingFaceH4/starchat-alpha", **kwargs):
        tokenizer = AutoTokenizer.from_pretrained(model_path, device_map='auto', revision='5058bd8557100137ade3c459bfc8100e90f71ec7')
        model = AutoModelForCausalLM.from_pretrained(model_path, device_map='auto', torch_dtype=torch.bfloat16, revision='5058bd8557100137ade3c459bfc8100e90f71ec7')
        model.eval()
        super().__init__(model, tokenizer=tokenizer, device_map='auto', **kwargs)
    
    @staticmethod
    def role_start(role):
        return f"<|{role}|>"
    
    @staticmethod
    def role_end(role):
        return '<|end|>'


class BackendLLMManager():
    def __init__(self):
        # state machine [unloaded, loading, ready, error]
        self.llms = {
            'starcoderchat-cuda': {'state': 'unloaded', 'llm': None},
            'starcoderchat-cpu': {'state': 'unloaded', 'llm': None},
            'openai-gpt-3.5': {'state': 'unloaded', 'llm': None},
            'openai-gpt-4': {'state': 'unloaded', 'llm': None},
        }
    
    def load(self, llm_name):
        # create a background thread to load the llm
        if self.llms[llm_name]['state'] == 'unloaded':
            match llm_name:
                case 'starcoderchat-cuda':
                    self.llms[llm_name]['state'] = 'loading'
                    self.llms[llm_name]['llm'] = StarcoderChat()
                    self.llms[llm_name]['state'] = 'ready'
                case _:
                    print(f"LLM {llm_name} not found")
        return self.model_status(llm_name)
    
    def unload(self, llm_name):
        if llm_name in self.llms:
            self.llms[llm_name]['state'] = 'unloaded'
            self.llms[llm_name]['llm'] = None

    def model_status(self, llm_name):
        state = self.llms[llm_name]['state']
        update = gr.Button.update(visible = state != 'ready')
        return [(llm_name, state)], update


llm_manager = BackendLLMManager()