import dotenv
import random 
import json
import gradio as gr
import csv
import requests

from datadm.repl import REPL
from datadm.backend import llm_manager
from datadm.agent import agent_manager
from datadm.conversation import conversation_list_to_history

dotenv.load_dotenv()


def get_downloads(repl):
    frames = repl.dataframes_as_csvs()
    if len(frames) == 0:
        result = [gr.Text.update(visible=True)]
    else:
        result = [gr.Text.update(visible=False)]
    for frame in frames:
        result.append(
            gr.File.update(
                value = frame['csv'],
                label = f"{frame['name']} ({frame['rows']} rows, {len(frame['columns'])} cols)",
                visible=True,
            )
        )
    while len(result) < 11:
        result.append(gr.File.update(visible=False))
    return result


def remove_to_last_talker(conversation, model_selection):
    # assume you want to clear cache as well
    llm_manager.llms.get(model_selection, {}).get('llm').cache.clear()
    if len(conversation) == 0:
        return conversation_list_to_history(conversation), conversation
    last_talker = conversation[-1]['role']
    while len(conversation) > 0 and conversation[-1]['role'] == last_talker:
        conversation.pop()
    return conversation_list_to_history(conversation), conversation


def bot(agent_selection, repl, conversation, model_selection):
    agent = agent_manager.get(agent_selection)
    yield from agent.bot(repl, conversation, model_selection)

def user(agent_selection, message, history, conversation):
    agent = agent_manager.get(agent_selection)
    return agent.user(message, history, conversation)

def add_data(agent_selection, file, repl, conversation):
    agent = agent_manager.get(agent_selection)
    return agent.add_data(file, repl, conversation)

def setup_repl():
    repl = REPL()
    repl.exec('import pandas as pd')
    repl.exec('import numpy as np')
    repl.exec('import matplotlib.pyplot as plt')
    repl.exec("pd.set_option('display.max_columns', 500)")
    repl.exec("pd.set_option('display.width', 1000)")
    return repl


def tab_results(query, ntab):
    url = "https://gist.githubusercontent.com/rnirmal/e01acfdaf54a6f9b24e91ba4cae63518/raw/6b589a5c5a851711e20c5eb28f9d54742d1fe2dc/datasets.csv"
    response = requests.get(url)
    if response.status_code == 200:
        content = response.text
        content = content.splitlines()
        nrows = len(content)
        rows = csv.reader(content)
        header = next(rows)
        tables = []
        
        for _ in range(nrows):
            row = next(rows, None)
            if row is None:
                break
            table = {
                "description": row[1],
                "table": row[0],
                "url": row[2]
            }
            tables.append(table)
        
        if query is not None:
            tables = [table for table in tables if query.lower() in table['description'].lower() or query.lower() in table['table'].lower()]

        response = {
            "tables": tables
        }
    else:
        response = {
            "tables": []
        }

    return json.dumps(response)

css = """
footer {display: none !important;}
.gradio-container {min-height: 0px !important;}
.disclaimer {font-variant-caps: all-small-caps;}
#chatbox {flex-grow: 1; overflow-y: hidden !important;}
#fullheight {height: 90vh; flex-wrap: nowrap;}
#chatbox > .wrap { max-height: none !important; }
#chatbox img { max-height: none !important; max-width: 100% !important; }
"""

class DataSearchResultRowComponent:
    def __init__(self):
        self.data = {
            'title': {'class': gr.Text, 'kwargs': {'value': 'hello', 'show_label': False}},
            'description': {'class': gr.Markdown, 'kwargs': {'value': 'description'}},
            'download': {'class': gr.Button, 'kwargs': {'value': '📁'}},
        }
        self.ref_order = []

    def component(self, name):
        self.ref_order.append(name)
        kwargs = self.data.get(name, {}).get('kwargs', {})
        return self.data.get(name, {}).get('class', gr.Text)(**kwargs)

    def gradio_gen(self):
        objs = []
        with gr.Column():
            objs.append(self.component('title').style(container=False))
            objs.append(self.component('description'))
        with gr.Column():
            objs.append(self.component('download').style(container=False))

        return objs
    
    def gradio_update(self):
        res = []
        for k in self.ref_order:
            res.append(self.data[k]['class'].update(**self.data[k]['kwargs']))
        return res

class Container:
    def __init__(self, n):
        self.n = n
        self.data = []
        self.objs = []
        for _ in range(n):
            self.objs.append(DataSearchResultRowComponent())

    def gradio_gen(self):
        ret = []
        for obj in self.objs:
            with gr.Row():
                for obj in obj.gradio_gen():
                    ret.append(obj)
        return ret

    def update_values(self, tables):
        self.data = tables

    def set_offset(self, offset):
        to_be_rendered = self.data[offset:offset+self.n]
        for i, obj in enumerate(self.objs):
            if i < len(to_be_rendered):
                obj.data['title']['kwargs']['value'] = to_be_rendered[i]['table']
                obj.data['description']['kwargs']['value'] = to_be_rendered[i]['description']
                obj.data['download']['kwargs']['value'] = f'📁 {to_be_rendered[i]["url"]}'
            else:
                obj.data['title']['kwargs']['value'] = ''
                obj.data['description']['kwargs']['value'] = ''
                obj.data['download']['kwargs']['value'] = ''

    def updater(self, offset):
        self.set_offset(offset)
        updates = []
        for obj in self.objs:
            updates.extend(obj.gradio_update())
        return updates


def randomupdate(query, container):
    tables = tab_results(query=query, ntab=5)
    tables = json.loads(tables)
    if isinstance(tables, dict):
        tables = tables['tables']
    container.update_values(tables)
    return container.updater(0)

with gr.Blocks(
    theme=gr.themes.Soft(),
    css=css,
    analytics_enabled=False,
) as demo:
    container = gr.State(Container(1))
    results = []
    conversation = gr.State([])
    with gr.Row():
        query = gr.Textbox(
            label="Search",
            placeholder="What data are you looking for?",
            show_label=False,
            elem_id="search_textbox"
        ).style(container=False)
        search = gr.Button("Search")
    with gr.Column():
        results.extend(container.value.gradio_gen())
        index_offset = gr.Number(0, interactive=True)
    search.click(randomupdate, [query, container], results).then(lambda: 0, None, index_offset)
    index_offset.change(lambda container, ioff: container.updater(int(ioff)), [container, index_offset], results)
    repl = gr.State(None)
    files = []
    gr.Markdown("# Welcome to DataDM!")
    with gr.Row():
        with gr.Column(scale=5, elem_id="fullheight"):
            chatbot = gr.Chatbot(elem_id="chatbox", show_label=False)
            with gr.Row():
                with gr.Column():
                    msg = gr.Textbox(
                        label="Chat Message Box",
                        placeholder="Chat Message Box",
                        show_label=False,
                        elem_id="chat_message_box"
                    ).style(container=False)
                with gr.Column():
                    with gr.Row():
                        submit = gr.Button("Submit", elem_id="submit_button")
                        cancel = gr.Button("Cancel", visible=False)
                        undo = gr.Button("Undo")
                        retry = gr.Button("Retry")
        with gr.Column(scale=1):
            with gr.Row():
                agent_selection = gr.Dropdown(
                    choices=agent_manager.names,
                    value="Baseline",
                    label="agent",
                    multiselect=False,
                    show_label=True,
                    interactive=True).style(container=False)
            with gr.Row():
                model_selection = gr.Dropdown(
                    choices=list(llm_manager.llms.keys()),
                    value=list(llm_manager.llms.keys())[0],
                    label="model",
                    multiselect=False,
                    show_label=True,
                    interactive=True,
                    elem_id='model_selection_dropdown').style(container=False)
                model_state = gr.HighlightedText(label=False).style(container=False)
            load_model = gr.Button("Load Model", visible=False, elem_id="load_model_button")
            files.append(gr.Text("No Data Files", label="Data Files"))
            for _ in range(10):
                f = gr.File(__file__, visible=False)
                files.append(f)
            upload = gr.UploadButton(label="Upload CSV", elem_id="upload_button")

    # Setup Blocks
    demo.load(lambda: gr.Button.update(visible=False), None, load_model
        ).then(llm_manager.model_status, model_selection, model_state
        ).then(lambda llm_name: gr.Button.update(visible=(llm_manager.llms[llm_name]['state'] != 'ready')), model_selection, load_model)
    demo.load(setup_repl, None, repl)

    # Configuration Blocks
    model_selection.change(lambda x: (x, llm_manager.model_status(x)), model_selection, [model_selection, model_state]
        ).then(lambda llm_name: gr.Button.update(visible=(llm_manager.llms[llm_name]['state'] != 'ready')), model_selection, load_model)
    agent_selection.change(
        lambda x: gr.Dropdown.update(
            choices=agent_manager.get(x).valid_models & set(llm_manager.llms.keys()),
            value=list(agent_manager.get(x).valid_models)[0]
        ), 
        agent_selection,
        [model_selection]
    ).then(lambda llm_name: gr.Button.update(visible=(llm_manager.llms[llm_name]['state'] != 'ready')), model_selection, load_model)

    load_model.click(llm_manager.load, model_selection, model_state
        ).then(lambda llm_name: gr.Button.update(visible=(llm_manager.llms[llm_name]['state'] != 'ready')), model_selection, load_model)

    # Agent Blocks
    upload_event = upload.upload(add_data, [agent_selection, upload, repl, conversation],[chatbot, conversation]
        ).then(get_downloads, repl, files)

    buttonset = [submit, cancel, undo, retry]
    running_buttons = [gr.Button.update(**k) for k in [{'visible': False}, {'visible': True}, {'interactive': False}, {'interactive': False}]]
    idle_buttons = [gr.Button.update(**k) for k in [{'visible': True}, {'visible': False}, {'interactive': True}, {'interactive': True}]]

    msg_enter_event = msg.submit(user, [agent_selection, msg, chatbot, conversation], [msg, chatbot, conversation], queue=False
        ).then(lambda: running_buttons, None, buttonset, queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True)
    msg_enter_finalize = msg_enter_event.then(get_downloads, repl, files
        ).then(lambda: idle_buttons, None, buttonset, queue=False)

    submit_click_event = submit.click(user, [agent_selection, msg, chatbot, conversation], [msg, chatbot, conversation], queue=False
        ).then(lambda: running_buttons, None, buttonset, queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True)
    submit_click_finalize = submit_click_event.then(get_downloads, repl, files
        ).then(lambda: idle_buttons, None, buttonset, queue=False)

    # Control Blocks
    undo.click(remove_to_last_talker, [conversation, model_selection], outputs=[chatbot, conversation], queue=False)
    cancel.click(None, cancels=[msg_enter_event, submit_click_event], queue=False
        ).then(lambda: idle_buttons, None, buttonset, queue=False)
    retry.click(remove_to_last_talker, [conversation, model_selection], outputs=[chatbot, conversation], queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True
        ).then(get_downloads, repl, files)

demo.queue(max_size=128, concurrency_count=1)

def main(share=False):
    demo.launch(share=share, server_name="0.0.0.0")

if __name__ == "__main__":
    main()