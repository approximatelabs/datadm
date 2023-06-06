import dotenv

import gradio as gr

from datadm.repl import REPL
from datadm.backend import llm_manager
from datadm.agent import agent_manager
from datadm.conversation import conversation_list_to_history

dotenv.load_dotenv()

css = """
footer {display: none !important;}
.gradio-container {min-height: 0px !important;}
.disclaimer {font-variant-caps: all-small-caps;}
"""

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
    return repl


with gr.Blocks(
    theme=gr.themes.Soft(),
    css=css,
    analytics_enabled=False,
) as demo:
    conversation = gr.State([])
    repl = gr.State(None)
    files = []
    gr.Markdown("# Welcome to DataDM!")
    with gr.Row():
        with gr.Column(scale=5):
            chatbot = gr.Chatbot().style(height=600)
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
                    interactive=True)
            with gr.Row():
                model_selection = gr.Dropdown(
                    choices=list(llm_manager.llms.keys()),
                    value="starcoderchat-cuda" if "starcoderchat-cuda" in llm_manager.llms else list(llm_manager.llms.keys())[0],
                    label="model",
                    multiselect=False,
                    show_label=True,
                    interactive=True)
                model_state = gr.HighlightedText(label=False)
            load_model = gr.Button("Load Model", visible=lambda: llm_manager.llms[llm_manager.selected]['state'] != 'loaded')
            files.append(gr.Text("No Data Files", label="Data Files"))
            for _ in range(10):
                f = gr.File(__file__, visible=False)
                files.append(f)
            upload = gr.UploadButton(label="Upload CSV")

    # Setup Blocks
    demo.load(llm_manager.model_status, model_selection, [model_state, load_model])
    demo.load(setup_repl, None, repl)

    # Configuration Blocks
    model_selection.change(lambda x: (x, *llm_manager.model_status(x)), model_selection, [model_selection, model_state, load_model],)
    agent_selection.change(
        lambda x: gr.Dropdown.update(
            choices=agent_manager.get(x).valid_models & set(llm_manager.llms.keys()),
            value=list(agent_manager.get(x).valid_models)[0]
        ), 
        agent_selection,
        [model_selection]
    )
    load_model.click(llm_manager.load, model_selection, [model_state, load_model])

    # Agent Blocks
    upload_event = upload.upload(add_data, [agent_selection, upload, repl, conversation],[chatbot, conversation]
        ).then(get_downloads, repl, files)

    submit_event = msg.submit(user, [agent_selection, msg, chatbot, conversation], [msg, chatbot, conversation], queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True
        ).then(get_downloads, repl, files)

    submit_click_event = submit.click(user, [agent_selection, msg, chatbot, conversation], [msg, chatbot, conversation], queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True
        ).then(get_downloads, repl, files)

    # Control Blocks
    undo.click(remove_to_last_talker, [conversation, model_selection], outputs=[chatbot, conversation], queue=False)
    retry.click(remove_to_last_talker, [conversation, model_selection], outputs=[chatbot, conversation], queue=False
        ).then(bot, [agent_selection, repl, conversation, model_selection], [chatbot, conversation], queue=True
        ).then(get_downloads, repl, files)

demo.queue(max_size=128, concurrency_count=1)

def main(share=False):
    demo.launch(share=share, server_name="0.0.0.0")

if __name__ == "__main__":
    main()