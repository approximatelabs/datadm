import guidance
import re

from datadm.agent import Agent
from datadm.conversation import clean_conversation_list


base_prompt = '''
{{#user~}}
You are a helpful AI code-writing assistant, the perfect data analyst who is jovial, fun and writes great code to solve data problems!

Answer my questions with both text describing your plan (but not an answer), and then the code in markdown that will be executed!

* Use `print` to show results.
* Don't answer the question directly, instead suggest how you will solve the problem, then write in a ```python markdown block, the code you will use to solve the problem.
* For plotting, please use `matplotlib`. use `plt.show()` to display the plot to the user.
{{~/user}}
{{#each conversation}}
{{#if (equal this.role 'user')}}
{{#user~}}
{{this.content}}
{{~/user}}
{{/if}}
{{#if (equal this.role 'assistant')}}
{{#assistant~}}
{{this.content}}
{{~/assistant}}
{{/if}}
{{/each}}
'''

gensponse = '''
{{#assistant~}}
{{gen "response" temperature=0.5 max_tokens=800}}
{{~/assistant}}
'''

def extract_all_code_blocks(text):    
    starts = [m.start() for m in re.finditer('```', text)]
    output = ""
    for i in range(0, len(starts), 2):
        res = text[starts[i]+3:starts[i+1]]
        if res.startswith('python'):
            res = res[6:]
        output += res
    return output


class Baseline(Agent):
    def _bot(self, repl, conversation, llm):
        starting_convo = conversation

        tries = 0
        while tries < 2:
            precode = guidance(base_prompt + gensponse, llm=llm)

            for result in precode(conversation=clean_conversation_list(starting_convo), silent=True, stream=True):
                yield starting_convo + [{'role': 'assistant', 'content': result.get('response') or ''}]
            starting_convo += [{'role': 'assistant', 'content': result.get('response')}]

            exec_result = repl.exec(extract_all_code_blocks(result['response']))
            starting_convo += [{'role': 'assistant', 'content': exec_result}]
            yield starting_convo

            if exec_result['tracebacks']:
                tries += 1
                continue
            break
