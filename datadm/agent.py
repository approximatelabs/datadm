import re
import os
import tenacity

from datadm.backend import llm_manager, local_available
from datadm.conversation import conversation_list_to_history


class Agent:
    is_local = False

    def __init__(self):
        pass

    @tenacity.retry(wait=tenacity.wait_fixed(1), stop=tenacity.stop_after_attempt(3))
    def bot(self, repl, conversation, model_selection):
        llm = llm_manager.llms.get(model_selection, {}).get('llm')
        if llm is None:
            yield conversation_list_to_history(conversation + [{'role': 'assistant', 'content': 'Please select and load a model'}]), conversation
            return

        for conversation in self._bot(repl, conversation, llm):
            yield conversation_list_to_history(conversation), conversation


    def _bot(self, repl, conversation, llm):
        raise NotImplementedError(f"Please Implement _bot method on {self.__class__.__name__}")
    
    def user(self, message, history, conversation):
        return "", history + [[message, None]], conversation + [{'role': 'user', 'content': message}]

    def add_data(self, file, repl, conversation):
        def clean(varStr): return re.sub('\W|^(?=\d)','_', varStr)
        if isinstance(file, str):
            basename = file
            varname = clean(basename.split('/')[-1].split('.')[0])
        else:
            repl.upload_file(file.name)
            basename = file.name.split('/')[-1]
            varname = clean(basename.split('.')[0])
        code_to_execute = f"{varname} = pd.read_csv('{basename}')\nprint({varname}.head())"
        result = repl.exec(code_to_execute)
        conversation.append({'role': 'user', 'content': f"Added {basename}"})
        conversation.append({'role': 'assistant', 'content': f"Loading the data...\n```python\n{code_to_execute}\n```"})
        conversation.append({'role': 'assistant', 'content': result})
        return conversation_list_to_history(conversation), conversation

    @property
    def valid_models(self):
        if self.is_local:
            return set([k for k, v in llm_manager.llms.items() if v['mode'] != 'api'])
        else:
            return set(llm_manager.llms.keys())

class AgentManager:
    def __init__(self):
        self.agents = {}
        for file in os.listdir(os.path.join(os.path.dirname(__file__), 'agents')):
            if file.endswith('.py') and not file.startswith('__'):
                module_name = file[:-3]
                try:
                    module = __import__(f"datadm.agents.{module_name}", fromlist=[module_name])
                    for name, obj in module.__dict__.items():
                        if isinstance(obj, type) and issubclass(obj, Agent) and obj != Agent:
                            if obj.is_local and not local_available:
                                continue
                            self.agents[name] = obj()
                except Exception as e:
                    print(f"Error importing agent {module_name}: {e}")

    def get(self, full_agent_text):
        agent_name = full_agent_text.split(' ')[0]
        return self.agents.get(agent_name, None)
    
    @property
    def names(self):
        names = []
        for agent in self.agents.values():
            names.append(agent.__class__.__name__ + (" (local-only)" if agent.is_local else ""))
        return names

agent_manager = AgentManager()