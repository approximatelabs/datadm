import guidance
from transformers import AutoModelForCausalLM, AutoTokenizer
import os


# TODO: fix this to check devices and packages to dynamically adjust available LLMs and models
try:
    import accelerate
    local_available = True
except ImportError:
    local_available = False

class StarcoderChat(guidance.llms.Transformers):
    def __init__(self, **kwargs):
        import torch
        tokenizer = AutoTokenizer.from_pretrained(kwargs['model_path'], device_map='auto', revision=kwargs['revision'])
        model = AutoModelForCausalLM.from_pretrained(kwargs['model_path'], device_map='auto', torch_dtype=torch.bfloat16, revision=kwargs['revision'])
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
        self.llms = {
            # 'starcoderchat-cpu': {'state': 'unloaded', 'llm': None},
            'openai-gpt-3.5': {'state': 'unloaded', 'llm': None, 'mode': 'api'},
            'openai-gpt-4': {'state': 'unloaded', 'llm': None, 'mode': 'api'},
        }

        if local_available:
            self.llms['starcoderchat-cuda-alpha'] = {'state': 'unloaded', 'llm': None, 'mode': 'cuda', 'model_path': 'HuggingFaceH4/starchat-alpha', 'revision': '5058bd8557100137ade3c459bfc8100e90f71ec7'}
            self.llms['starcoderchat-cuda-beta'] = {'state': 'unloaded', 'llm': None, 'mode': 'cuda', 'model_path': 'HuggingFaceH4/starchat-beta', 'revision': 'b1bcda690655777373f57ea6614eb095ec2c886f'}

    def load(self, llm_name):
        if self.llms[llm_name]['state'] == 'unloaded':
            if llm_name == 'starcoderchat-cuda-alpha' or llm_name == 'starcoderchat-cuda-beta':
                kwArgs = {'model_path' : self.llms[llm_name]['model_path'], 'revision': self.llms[llm_name]['revision']}
                self.llms[llm_name]['state'] = 'loading'
                self.llms[llm_name]['llm'] = StarcoderChat(**kwArgs)
                self.llms[llm_name]['state'] = 'ready'
            elif llm_name == 'openai-gpt-4':
                self.llms[llm_name]['state'] = 'loading'
                if 'OPENAI_API_KEY' not in os.environ:
                    raise RuntimeError("OPENAI_API_KEY not found in environment")
                self.llms[llm_name]['llm'] = guidance.llms.OpenAI("gpt-4")
                self.llms[llm_name]['state'] = 'ready'
            elif llm_name == 'openai-gpt-3.5':
                self.llms[llm_name]['state'] = 'loading'
                if 'OPENAI_API_KEY' not in os.environ:
                    raise RuntimeError("OPENAI_API_KEY not found in environment")
                self.llms[llm_name]['llm'] = guidance.llms.OpenAI("gpt-3.5-turbo")
                self.llms[llm_name]['state'] = 'ready'
            else:
                raise RuntimeError(f"LLM {llm_name} not supported")
        return self.model_status(llm_name)
    
    def unload(self, llm_name):
        if llm_name in self.llms:
            self.llms[llm_name]['state'] = 'unloaded'
            self.llms[llm_name]['llm'] = None

    def model_status(self, llm_name):
        state = self.llms[llm_name]['state']
        return [(llm_name, state)]


llm_manager = BackendLLMManager()
