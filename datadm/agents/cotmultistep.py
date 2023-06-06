import guidance

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

precode_prompt = '''
{{#assistant~}}
{{gen "thoughts" temperature=0.1 max_tokens=120 stop=["```", "<|end|>"]}}
```python
{{gen "code" temperature=0.0 max_tokens=800 stop=["```", "<|end|>"]}}
{{~/assistant}}
'''

postcode_prompt = '''
{{#assistant~}}
Looking at the executed results above, we can see {{gen "summary" temperature=0.0 max_tokens=120 stop=["```", "<|end|>"]}}
{{~/assistant}}
'''

class CoTMultiStep(Agent):
    is_local = True

    def _bot(self, repl, conversation, llm):
        starting_convo = conversation

        tries = 0
        while tries < 2:
            precode = guidance(base_prompt + precode_prompt, llm=llm)

            for result in precode(conversation=clean_conversation_list(starting_convo), silent=True, stream=True):
                resolved_content = result.get('thoughts') or ''
                resolved_content += '\n```python\n'+(result.get('code') or '')+'\n```'
                resolved_convo = starting_convo + [{'role': 'assistant', 'content': resolved_content}]
                yield resolved_convo
            starting_convo += [{'role': 'assistant', 'content': resolved_content}]

            exec_result = repl.exec(result['code'])
            starting_convo += [{'role': 'assistant', 'content': exec_result}]
            yield starting_convo

            if exec_result['tracebacks']:
                tries += 1
                continue
            break
            
        postcode = guidance(base_prompt + postcode_prompt, llm=llm)

        for result in postcode(conversation=clean_conversation_list(starting_convo), silent=True, stream=True):
            yield starting_convo + [{'role': 'assistant', 'content': f'Looking at the executed results above, we can see {result.get("summary") or ""}'}]
