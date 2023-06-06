import atexit
import tempfile
import base64
import hashlib
import os

temp_image_dir = tempfile.TemporaryDirectory()
atexit.register(temp_image_dir.cleanup)


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
