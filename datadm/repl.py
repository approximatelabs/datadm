import atexit
import json
import os
import signal
import subprocess
import tempfile
import time
import uuid
from queue import Empty

from jupyter_client.blocking import BlockingKernelClient


class REPL:
    # TODO: add a "save as ipynb file" as serialization option 
    #   (allow for "added readme" comment operations, so `bot` can write the conversation into it)
    #   Use this to offer "jupyter file" or even better: "in colab"
    #   -> For any uploaded files, call them out in the header that the notebook expects those files ("system was run with {x} {y}")
    #   -> "Add secret" -> doesn't show up in the conversation, shows up in notebooks as an env-var
    #   "download conversation as webpage" -> {ipynb} -> {html}
    def __init__(self):
        self.history = []
        self.uid = str(uuid.uuid4())
        self.conn_file = tempfile.NamedTemporaryFile(suffix='.json')
        self.runtime_dir = tempfile.TemporaryDirectory()
        self.work_dir = self.runtime_dir.name
        kernel_process = subprocess.Popen(
            ['jupyter-kernel', '--KernelManager.connection_file', self.conn_file.name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=self.work_dir,
            start_new_session=True
        )
        self.kernel_pid = kernel_process.pid
        atexit.register(lambda: os.kill(self.kernel_pid, signal.SIGKILL))
        atexit.register(self.runtime_dir.cleanup)
        self.kc = self.connect()
    
    def read_all(self):
        while True:
            try:
                yield self.kc.iopub_channel.get_msg(timeout=0.01)
            except Empty:
                break

    def snapshot(self):
        self.kc.stop_channels()
        os.makedirs(f"/tmp/{self.uid}", exist_ok=True)
        subprocess.run(
            [
                'sudo', 'criu', 'dump',
                '-t', str(self.kernel_pid),
                '-D', f'/tmp/{self.uid}',
                '--tcp-established',
                '--ext-unix-sk',
                '--shell-job',
                '--track-mem',
                # '--leave-running'
            ],
            check=True
        )
        self.restore()
        # okay, should be back up, now reconnect the kernel client
        # self.connect()

    def restore(self):
        self.kc.stop_channels()
        # TODO: fix this?
        os.kill(self.kernel_pid, signal.SIGTERM)
        time.sleep(10)
        subprocess.run(
            ['sudo', 'criu', 'restore',
            '-d',
            '-D', f'/tmp/{self.uid}',
            '--pidfile', str(self.kernel_pid),
            '-x',
            '--tcp-established'],
            check=True
        )
        self.connect()

    def connect(self, n_retries=100):
        tries = 0
        while tries < n_retries:
            try:
                kc = BlockingKernelClient(connection_file=self.conn_file.name)
                kc.load_connection_file()
                kc.start_channels()
                break
            except json.decoder.JSONDecodeError:
                time.sleep(0.2)
                tries += 1
        else:
            raise RuntimeError('Kernel did not start')
        self.kc = kc
        time.sleep(0.5)  # sleep to let things settle...
        return kc

    def exec(self, code, timeout=10):
        list(self.read_all())  # flush
        self.kc.execute(code)
        self.kc.get_shell_msg(timeout=timeout)
        output = {
            'stdout': '',
            'tracebacks': '',
            'data': [],
        }
        results = []
        for result in self.read_all():
            results.append(result)
            if result['msg_type'] == 'status':
                if result['content']['execution_state'] == 'idle':
                    continue  # done in theory
                elif result['content']['execution_state'] == 'busy':
                    continue  # beginning execution
                elif result['content']['execution_state'] == 'starting':
                    continue
                elif result['content']['execution_state'] == 'restarting':
                    continue
                else:
                    raise RuntimeError(f'Unknown execution state: {result["content"]["execution_state"]}')
            elif result['msg_type'] == 'execute_input':
                continue  # ignore
            else:
                content = result['content']
                if result['msg_type'] == 'stream':
                    output['stdout'] += content['text']
                elif result['msg_type'] == 'error':
                    output['tracebacks'] += "\n".join(content['traceback'])
                elif result['msg_type'] == 'display_data':
                    output['data'].append(content['data'])
                elif result['msg_type'] == 'execute_result':
                    output['data'].append(content['data'])
                else:
                    raise RuntimeError(f'Unknown message type {result["msg_type"]}')
        self.history.append({
            'code': code,
            'output': output,
            'results': results,
        })
        return output

    def whos(self, type=None):
        if type:
            return self.exec(f'%whos {type}')['stdout']
        # assume it always responds w/ no error
        return self.exec('%whos')['stdout']

    def upload_file(self, filepath):
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            filebytes = f.read()
        return self.upload_bytes(filebytes, filename=filename)

    def upload_bytes(self, filebytes, filename=None):
        if filename is None:
            with tempfile.NamedTemporaryFile(dir=self.work_dir, delete=False) as f:
                f.write(filebytes)
                filename = f.name
        else:
            with open(os.path.join(self.work_dir, filename), 'wb') as f:
                f.write(filebytes)
        return filename
