import guidance
from transformers import AutoModelForCausalLM, AutoTokenizer
import os


# TODO: fix this to check devices and packages to dynamically adjust available LLMs and models
try:
    import accelerate
    local_available = True
except ImportError:
    local_available = False

class StarChat(guidance.llms.Transformers):
    def __init__(self, model_path=None, revision=None, **kwargs):
        import torch
        tokenizer = AutoTokenizer.from_pretrained(model_path, device_map='auto', revision=revision)
        model = AutoModelForCausalLM.from_pretrained(model_path, device_map='auto', torch_dtype=torch.bfloat16, revision=revision)
        model.eval()
        super().__init__(model, tokenizer=tokenizer, device_map='auto', **kwargs)
    
    @staticmethod
    def role_start(role):
        return f"<|{role}|>"
    
    @staticmethod
    def role_end(role):
        return '<|end|>'


class BackendLLMManager():
    OPENAI_MODELS = ['gpt-3.5-turbo', 'gpt-4', 'gpt-3.5-turbo-16k', 'gpt-4-32k']

    def __init__(self):
        self.llms = {}
        if local_available:
            self.llms['starchat-alpha-cuda'] = {'state': 'unloaded', 'llm': None, 'mode': 'cuda', 'model_path': 'HuggingFaceH4/starchat-alpha', 'revision': '5058bd8557100137ade3c459bfc8100e90f71ec7'}
            self.llms['starchat-beta-cuda'] = {'state': 'unloaded', 'llm': None, 'mode': 'cuda', 'model_path': 'HuggingFaceH4/starchat-beta', 'revision': 'b1bcda690655777373f57ea6614eb095ec2c886f'}
        
        for model_name in self.OPENAI_MODELS:
            self.llms[model_name] = {'state': 'unloaded', 'llm': None, 'mode': 'api'}

    def load(self, llm_name):
        if self.llms[llm_name]['state'] == 'unloaded':
            self.llms[llm_name]['state'] = 'loading'
            if llm_name in ['starchat-alpha-cuda', 'starchat-beta-cuda']:
                self.llms[llm_name]['llm'] = StarChat(**self.llms[llm_name])
            elif llm_name in self.OPENAI_MODELS:
                if 'OPENAI_API_KEY' not in os.environ:
                    self.llms[llm_name]['state'] = 'error'
                    raise RuntimeError("OPENAI_API_KEY not found in environment")
                self.llms[llm_name]['llm'] = guidance.llms.OpenAI(llm_name)
            else:
                self.llms[llm_name]['state'] = 'error'
                raise RuntimeError(f"LLM {llm_name} not supported")
            self.llms[llm_name]['state'] = 'ready'
        return self.model_status(llm_name)
    
    def unload(self, llm_name):
        if llm_name in self.llms:
            self.llms[llm_name]['state'] = 'unloaded'
            self.llms[llm_name]['llm'] = None

    def model_status(self, llm_name):
        state = self.llms[llm_name]['state']
        return [(llm_name, state)]


llm_manager = BackendLLMManager()
