import gradio as gr
from datadm.backend import llm_manager
from datadm.agents.starcoder01 import bot, user, add_data, setup_repl


css = """
footer {display: none !important;}
.gradio-container {min-height: 0px !important;}
.disclaimer {font-variant-caps: all-small-caps;}
"""

def get_downloads(repl):
    frames = repl.dataframes_as_csvs()
    result = []
    for frame in frames:
        result.append(
            gr.File.update(
                value = frame['csv'],
                label = f"{frame['name']} ({frame['rows']} rows, {len(frame['columns'])} cols)",
                visible=True,
            )
        )
    while len(result) < 10:
        result.append(gr.File.update(visible=False))
    return result

with gr.Blocks(
    theme=gr.themes.Soft(),
    css=css,
    analytics_enabled=False,
) as demo:
    conversation = gr.State([])
    repl = gr.State(None)
    files = []
    with gr.Row():
        with gr.Column(scale=5):
            gr.Markdown("# Welcome to DataDM!")
            chatbot = gr.Chatbot().style(height=600)
        with gr.Column(scale=1):
            with gr.Row():
                model_selection = gr.Dropdown(
                    choices=list(llm_manager.llms.keys()),
                    value="starcoderchat-cuda",
                    label="model",
                    multiselect=False,
                    show_label=False,
                    interactive=True)
                model_state = gr.HighlightedText(label=False)
            load_model = gr.Button("Load Model", visible=lambda: llm_manager.llms[llm_manager.selected]['state'] != 'loaded')
            for _ in range(10):
                f = gr.File("README.md", visible=False)
                files.append(f)
    with gr.Row():
        with gr.Column(scale=5):
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
        with gr.Column(scale=1):
            upload = gr.UploadButton(label="Upload CSV")
    demo.load(setup_repl, None, repl)
    demo.load(llm_manager.model_status, model_selection, outputs=[model_state, load_model])
    model_selection.change(
        lambda x: (x, *llm_manager.model_status(x)),
        inputs=[model_selection],
        outputs=[model_selection, model_state, load_model],
    )
    load_model.click(
        llm_manager.load,
        inputs=[model_selection],
        outputs=[model_state, load_model],
    )
    upload_event = upload.upload(
        fn=add_data,
        inputs=[upload, repl, conversation],
        outputs=[chatbot, conversation]
    ).then(
        fn=get_downloads,
        inputs=[repl],
        outputs=files,
    )
    submit_event = msg.submit(
        fn=user,
        inputs=[msg, chatbot, conversation],
        outputs=[msg, chatbot, conversation],
        queue=False,
    ).then(
        fn=bot,
        inputs=[repl, conversation, model_selection],
        outputs=[chatbot, conversation],
        queue=True,
    ).then(
        fn=get_downloads,
        inputs=[repl],
        outputs=files,
    )
    submit_click_event = submit.click(
        fn=user,
        inputs=[msg, chatbot, conversation],
        outputs=[msg, chatbot, conversation],
        queue=False,
    ).then(
        fn=bot,
        inputs=[repl, conversation, model_selection],
        outputs=[chatbot, conversation],
        queue=True,
    ).then(
        fn=get_downloads,
        inputs=[repl],
        outputs=files,
    )
    stop.click(
        fn=None,
        inputs=None,
        outputs=None,
        cancels=[submit_event, submit_click_event],
        queue=False,
    )
    clear.click(lambda: (None, []), None, outputs=[chatbot, conversation], queue=False)

demo.queue(max_size=128, concurrency_count=1)

def main():
    
    demo.launch(share=False)


if __name__ == "__main__":
    main()