import dotenv
import gradio as gr
import requests

import os
import requests
import dotenv

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


css = """
footer {display: none !important;}
.gradio-container {min-height: 0px !important;}
.disclaimer {font-variant-caps: all-small-caps;}
#chatbox {flex-grow: 1; overflow-y: hidden !important;}
#fullheight {height: 87vh; flex-wrap: nowrap;}
#chatbox > .wrap { max-height: none !important; }
#chatbox img { max-height: none !important; max-width: 100% !important; }
#justify_center {justify-content: center !important;}
#load_model_button {flex-grow: 0 !important;}
#upload_button {flex-grow: 0 !important;}
"""

posthog_default_off_analytics_script = """
async () => {
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    posthog.init('phc_xouauQgYqQd2eBqYH4rjzkGewA19JsdrGrnL04m1pSL',{api_host:'https://app.posthog.com'})
}
"""

class DataSearchResultRowComponent:
    def __init__(self):
        self.data = {
            'repo': 'unknown',
            'subpath': 'unknown',
            'fullurl': 'unknown',
            'text': 'unknown'
        }
        self.gradios = {
            'html': {'class': gr.HTML, 'kwargs': {'value': '<div></div>'}},
            'url': {'class': gr.Text, 'kwargs': {'value': 'unknown', "visible": False}},
            'download': {'class': gr.Button, 'kwargs': {'value': 'Add To Chat'}},
        }
        self.ref_order = []

    def component(self, name, **extra_kwargs):
        self.ref_order.append(name)
        kwargs = self.gradios.get(name, {}).get('kwargs', {})
        return self.gradios.get(name, {}).get('class', gr.Text)(**kwargs, **extra_kwargs)

    def gradio_gen(self, upload_magic_thens):
        objs = []
        with gr.Column(scale=10):
            objs.append(self.component('html'))
            objs.append(self.component('url'))
        with gr.Column(scale=1, elem_id="justify_center", min_width=180):
            objs.append(self.component('download', container=False))
        events = objs[-1].click(lambda url: print(f"Downloading CSV: {url}"), objs[-2], None)
        for then_args in upload_magic_thens(objs[-2]):
            events.then(*then_args)
        return objs
    
    def gradio_update(self):
        res = []
        for k in self.ref_order:
            res.append(self.gradios[k]['class'].update(**self.gradios[k]['kwargs']))
        return res
    
    def update_from_dict(self, data):
        self.data = data
        if data is None:
            self.gradios['html']['kwargs']['value'] = '<div></div>'
            self.gradios['url']['kwargs']['value'] = 'unknown'
            return
        self.gradios['html']['kwargs']['value'] = f"""
            <div style="border-color:black; border-width:2px; border-radius:10px">
                <div style="padding: 4px; font-size: 18px;">
                    <span style="font-weight: bold;">{data['repo']}</span>
                    <span>{data['subpath']}</span>
                </div>
                <pre style="padding: 8px; background-color: #333333; color: #CCCCCC; font-size: 12px; overflow-x: scroll;">{data['text']}</pre>
            </div>
        """
        self.gradios['url']['kwargs']['value'] = data['fullurl']


class Container:
    def __init__(self, n):
        self.n = n
        self.data = []
        self.objs = []
        for _ in range(n):
            self.objs.append(DataSearchResultRowComponent())

    def gradio_gen(self, upload_magic_thens):
        ret = []
        for obj in self.objs:
            with gr.Row():
                for obj in obj.gradio_gen(upload_magic_thens):
                    ret.append(obj)
        return ret

    def update_values(self, tables):
        self.data = tables

    def set_offset(self, offset):
        to_be_rendered = self.data[offset:offset+self.n]
        for i, obj in enumerate(self.objs):
            if i < len(to_be_rendered):
                obj.update_from_dict(to_be_rendered[i])
            else:
                obj.update_from_dict(None)

    def updater(self, offset):
        self.set_offset(offset)
        updates = []
        for obj in self.objs:
            updates.extend(obj.gradio_update())
        return updates


def search_code(query):
    base_url = "https://api.github.com"
    endpoint = "/search/code"
    params = {
        "q": f"{query} .csv in:path",
        "per_page": 5,
    }
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": "Bearer " + os.environ.get("GITHUB_ACCESS_TOKEN"),
    }
    response = requests.get(base_url + endpoint, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data.get("items", [])


def format_items(items):
    formatted_results = []
    for item in items:
        repo = item["repository"]["full_name"]
        subpath = item["path"]
        fullurl = item["html_url"].replace("/blob/", "/raw/")
        
        response = requests.get(fullurl, stream=True)
        if response.status_code == 200:
            lines_count = 0
            content = ''
            for line in response.iter_lines():
                if lines_count >= 3:
                    break
                content += line.decode('utf-8', errors="ignore") + "\n"
                lines_count += 1
        else:
            content = ""
        
        result = {
            "repo": repo,
            "subpath": subpath,
            "fullurl": fullurl,
            "text": content,
        }
        formatted_results.append(result)
    
    return formatted_results


def searchupdate(query, container):
    results = search_code(query)
    formatted_results = format_items(results)
    container.update_values(formatted_results)
    return container.updater(0)


with gr.Blocks(
    theme=gr.themes.Soft(),
    css=css,
    analytics_enabled=False,
    title="DataDM"
) as demo:
    repl = gr.State(None)
    files = []
    conversation = gr.State([])
    gr.Markdown("# Welcome to DataDM!")
    with gr.Tabs() as tabs:
        with gr.Tab("Chat", id=0):
            with gr.Row():
                with gr.Column(scale=5, elem_id="fullheight"):
                    chatbot = gr.Chatbot(elem_id="chatbox", show_label=False)
                    with gr.Row():
                        with gr.Column():
                            msg = gr.Textbox(
                                label="Chat Message Box",
                                placeholder="Chat Message Box",
                                show_label=False,
                                elem_id="chat_message_box",
                                container=False
                            )
                        with gr.Column():
                            with gr.Row():
                                submit = gr.Button("Submit", elem_id="submit_button")
                                cancel = gr.Button("Cancel", variant="stop", visible=False)
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
                            interactive=True,
                            container=False)
                    with gr.Row():
                        model_selection = gr.Dropdown(
                            choices=list(llm_manager.llms.keys()),
                            value=list(llm_manager.llms.keys())[0],
                            label="model",
                            multiselect=False,
                            show_label=True,
                            interactive=True,
                            elem_id='model_selection_dropdown',
                            container=False)
                        model_state = gr.HighlightedText(label=False, container=False)
                    load_model = gr.Button("Load Model", visible=False, elem_id="load_model_button")
                    files.append(gr.Text("No Data Files", label="Data Files"))
                    for _ in range(10):
                        f = gr.File(__file__, visible=False)
                        files.append(f)
                    upload = gr.UploadButton(label="Upload CSV", elem_id="upload_button")
        upload_magic_thens = lambda filepath_object: [
            (add_data, [agent_selection, filepath_object, repl, conversation], [chatbot, conversation]),
            (get_downloads, repl, files),
            (lambda: gr.Tabs.update(selected=0), None, tabs)
        ]

        with gr.Tab("Search", id=1):
            container = gr.State(Container(5))
            results = []
            with gr.Row():
                query = gr.Textbox(
                    label="Search",
                    placeholder="What data are you looking for?",
                    show_label=False,
                    elem_id="search_textbox",
                    container=False
                )
                search = gr.Button("Search")
            with gr.Column():
                results.extend(container.value.gradio_gen(upload_magic_thens))
    
    # Run analytics tracking javascript only if in analytics tracking mode (default is off)
    if os.environ.get("ANALYTICS_TRACKING", "0") == "1":
        demo.load(None, None, None, _js=posthog_default_off_analytics_script)

    # Search Blocks
    query.submit(searchupdate, [query, container], results)
    search.click(searchupdate, [query, container], results)
        
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