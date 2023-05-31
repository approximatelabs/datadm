import atexit
import base64
import hashlib
import json
import os
import re
import tempfile

import gradio as gr
import guidance
import pandas as pd
import sketch
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from datadm.repl import REPL


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


def conversation_list_to_history(convo_list):
    # assuming this is a conversation between user and assistant, return a list of list of [user, assistant] messages
    # if someone speaks out of turn, put [None, text] for assistant or [text, None] for user
    # [{'role': 'user', 'content': 'hello'}, {'role': 'assistant', 'content': 'hi'}] -> [['hello', 'hi']]
    # [{'role': 'user', 'content': 'hi'}, {'role': 'user', 'content': ' HEY! '}, {'role': 'assisstant', 'content': ' what do yo'}] -> [['hi', None], [' HEY! ', ' what do yo']]
    history = []
    for item in convo_list:
        if item['role'] == 'user':
            # this always causes a new entry
            history.append([item['content'], None])
        elif item['role'] == 'assistant':
            # this either appends to the last entry, or creates a new entry
            if len(history) == 0 or history[-1][1] is not None:
                history.append([None, item['content']])
            else:
                history[-1][1] = item['content']
    # for all history, check if any are not strings, and conver them to valid history objects
    new_history = []
    for i, c in enumerate(history):
        images_to_append = []
        new_row = []
        for j, val in enumerate(c):
            new_text = val
            new_html_text = ""
            if not isinstance(val, str) and val is not None:
                new_text = ""
                if val['stdout']:
                    new_text += val['stdout']
                if val['tracebacks']:
                    new_text += "\n".join(val['tracebacks'])[:400]
                if val['data']:
                    for dataentry in val['data']:
                        for k, v in dataentry.items():
                            if 'text' in k:
                                if 'html' in k:
                                    new_html_text += v
                                else:
                                    new_text += v
                            else:
                                # assume this is a file, written in base64... convert to bytes, save to determinstiic temporary file path, and replace with that path
                                filename = hashlib.sha256(v.encode('utf-8')).hexdigest()+'.png'
                                file_path = os.path.join(temp_image_dir.name, filename)
                                with open(file_path, 'wb') as f:
                                    f.write(base64.b64decode(v))
                                images_to_append += [file_path]
                if new_text:
                    new_text = f'```\n{new_text}\n```'
                new_text += new_html_text
            if new_text:
                new_row.append(new_text)
            else:
                new_row.append(None)
        new_history.append(new_row)
        if images_to_append:
            for image_file in images_to_append:
                new_history.append([None, (image_file,)])
    return new_history

def clean_conversation_list(convo_list):
    # for any "content" that is not a string, convert / replace it with something simple
    # assume that they are the output from `exec`, so they should have 3 keys, `stdout`, `tracebacks`, and `data`
    cleaned = []
    for convo in convo_list:
        if isinstance(convo['content'], str) or convo['content'] is None:
            cleaned.append(convo)
            continue
        new_html_text = ""
        new_text = ""
        if convo['content']['stdout']:
            new_text += convo['content']['stdout']
        if convo['content']['tracebacks']:
            new_text += "\n".join(convo['content']['tracebacks'][:400])  # limit to prevent overflow
        if convo['content']['data']:
            new_text += "\n".join([v for dataentry in convo['content']['data'] for k, v in dataentry.items() if 'text' in k and 'html' not in k])
            new_html_text += "\n".join([v for dataentry in convo['content']['data'] for k, v in dataentry.items() if 'html' in k])
        cleaned.append({'role': convo['role'], 'content': 'EXECUTION OF LAST CODE BLOCK RESULT: ' + (f'```\n{new_text}\n```' if new_text else '' )+new_html_text})
    return cleaned

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


def user(message, history, conversation):
    # Append the user's message to the conversation history
    return "", history + [[message, None]], conversation + [{'role': 'user', 'content': message}]

def bot(repl, conversation):
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


llm = StarcoderChat()

temp_image_dir = tempfile.TemporaryDirectory()
atexit.register(temp_image_dir.cleanup)


with gr.Blocks(
    theme=gr.themes.Soft(),
    css=".disclaimer {font-variant-caps: all-small-caps;}",
    analytics_enabled=False,
) as demo:
    dataframes = gr.State({})
    conversation = gr.State([])
    repl = gr.State(None)
    chatbot = gr.Chatbot(every=0.2).style(height=600)
    gr.Markdown("# Welcome to DataDM!")
    with gr.Row():
        with gr.Column():
            msg = gr.Textbox(
                label="Chat Message Box",
                placeholder="Chat Message Box",
                show_label=False,
            ).style(container=False)
        with gr.Column():
            with gr.Row():
                submit = gr.Button("Submit")
                stop = gr.Button("Stop")
                clear = gr.Button("Clear")
    with gr.Row():
        # add upload button 
        upload = gr.UploadButton(label="Upload CSV")  # , file_count="multiple")
    demo.load(setup_repl, None, repl)
    upload_event = upload.upload(
        fn=add_data,
        inputs=[upload, repl, conversation],
        outputs=[chatbot, conversation]
    )
    submit_event = msg.submit(
        fn=user,
        inputs=[msg, chatbot, conversation],
        outputs=[msg, chatbot, conversation],
        queue=False,
    ).then(
        fn=bot,
        inputs=[repl, conversation],
        outputs=[chatbot, conversation],
        queue=True,
    )
    submit_click_event = submit.click(
        fn=user,
        inputs=[msg, chatbot, conversation],
        outputs=[msg, chatbot, conversation],
        queue=False,
    ).then(
        fn=bot,
        inputs=[repl, conversation],
        outputs=[chatbot, conversation],
        queue=True,
    )
    stop.click(
        fn=None,
        inputs=None,
        outputs=None,
        cancels=[submit_event, submit_click_event],
        queue=False,
    )
    clear.click(lambda: (None, []), None, outputs=[chatbot, conversation], queue=False)


if __name__ == "__main__":
    demo.queue(max_size=128, concurrency_count=1)
    demo.launch(share=False)