import json
import re

import pandas as pd
import sketch
import guidance

from datadm.repl import REPL
from datadm.conversation import conversation_list_to_history, clean_conversation_list
from datadm.backend import llm_manager


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

def bot(repl, conversation, model_selection=None):
    llm = llm_manager.llms.get(model_selection, {}).get('llm')
    if llm is None:
        yield conversation_list_to_history(conversation + [{'role': 'assistant', 'content': 'Please select and load a model'}]), conversation
        return
    starting_convo = conversation

    tries = 0
    while tries < 3:
        precode = guidance(base_prompt + '''
{{#assistant~}}
{{gen "thoughts" temperature=0.1 max_tokens=120 stop=["```", "<|end|>"]}}
```python
{{gen "code" temperature=0.0 max_tokens=800 stop=["```", "<|end|>"]}}
{{~/assistant}}
'''
, llm=llm)

        for result in precode(conversation=clean_conversation_list(starting_convo), silent=True, stream=True):
            resolved_content = result.get('thoughts') or ''
            code = result.get('code') or ''
            if code:
                resolved_content += '\n```python\n'+code+'\n```'
            resolved_convo = starting_convo + [{'role': 'assistant', 'content': resolved_content}]
            yield conversation_list_to_history(resolved_convo), resolved_convo

        starting_convo += [{'role': 'assistant', 'content': resolved_content}]

        exec_result = repl.exec(result['code'])
        starting_convo += [{'role': 'assistant', 'content': exec_result}]
        yield conversation_list_to_history(starting_convo), starting_convo
        if exec_result['tracebacks']:
            tries += 1
            continue
        else:
            break
        
    postcode = guidance(base_prompt + '''
{{#assistant~}}
Looking at the executed results above, we can see {{gen "summary" temperature=0.0 max_tokens=120 stop=["```", "<|end|>"]}}
{{~/assistant}}
''', llm=llm)

    for result in postcode(conversation=clean_conversation_list(starting_convo), silent=True, stream=True):
        resolved_convo = starting_convo + [{'role': 'assistant', 'content': f'Looking at the executed results above, we can see {result.get("summary") or ""}'}]
        yield conversation_list_to_history(resolved_convo), resolved_convo


def user(message, history, conversation):
    # Append the user's message to the conversation history
    return "", history + [[message, None]], conversation + [{'role': 'user', 'content': message}]


def add_data(file, repl, conversation):
    repl.upload_file(file.name)
    basename = file.name.split('/')[-1]
    def clean(varStr): return re.sub('\W|^(?=\d)','_', varStr)
    varname = clean(basename.split('.')[0])
    result = repl.exec(f"{varname} = pd.read_csv('{basename}')")
    dataframe = pd.read_csv(file.name)
    datasummary = json.dumps(sketch.pandas_extension.get_description_from_parts(*sketch.pandas_extension.get_parts_from_df(dataframe)))
    conversation.append({'role': 'user', 'content': f"Added {basename}"})
    conversation.append({'role': 'assistant', 'content': f"Loading the data...\n```python\n{varname} = pd.read_csv('{basename}')\n```\n-SUMMARY-\n```\n{datasummary}\n```\n{result}"})
    return conversation_list_to_history(conversation), conversation


def setup_repl():
    repl = REPL()
    repl.exec('import pandas as pd')
    repl.exec('import numpy as np')
    repl.exec('import matplotlib.pyplot as plt')
    return repl

