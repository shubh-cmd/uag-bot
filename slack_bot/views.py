from rest_framework.views import APIView
from rest_framework.response import Response
import subprocess
import requests
from slack_server.settings import BOT_ID, CLIENT, SLACK_TOKEN, SLACK_CHANNEL, BOT_BASE_DIR, UAG_BASE_DIR
import json
import os
import shutil
from queue import Queue
# Create your views here.
jobs = Queue()
IS_FREE = True

class SlackView(APIView):

    def post(self, request):
        if request.data['type'] == "url_verification":
            return Response({"challenge": request.data['challenge']})
        elif request.headers.get('X-Slack-Retry-Num') == '1':
            return Response(status=200, headers={"X-Slack-No-Retry": 1})
        else:
            e = request.data['event']
            if e['type'] == 'file_shared' and e['user_id'] != BOT_ID:
                res = CLIENT.files_info(file=str(e['file_id']))

                if res['file']['filetype'] == 'zip' or res['file']['title'] == 'inputs.dat':

                    file_name = res['file']['name']
                    file_url = res['file']['url_private']
                     
                    r = requests.get(file_url, headers={
                                     'Authorization': f'Bearer {SLACK_TOKEN}'})
                    
                    r.raise_for_status()
                    file_data = r.content
                    print(file_name)
                    with safe_open(f'{BOT_BASE_DIR}/'+e['user_id']+'/'+file_name) as f:
                        f.write(bytearray(file_data))
                    
                    CLIENT.chat_postEphemeral(
                        channel=e['channel_id'], user=e['user_id'], text="React any file you shared, by marking completed tick to start analysis")
            elif e['type'] == 'reaction_added' and e['user'] != BOT_ID:
                global jobs
                jobs.put(e['user'])
                global IS_FREE
                while jobs.qsize() and IS_FREE:
                    current_user = jobs.get()
                    IS_FREE = False
                    subprocess.run(['bash', f'{BOT_BASE_DIR}/bot.sh', SLACK_TOKEN, current_user, SLACK_CHANNEL, BOT_BASE_DIR, UAG_BASE_DIR])
                
                    result = CLIENT.files_upload(file=f'{BOT_BASE_DIR}/{current_user}/analysis-logs.zip',initial_comment="Result of the Analysis",channels=SLACK_CHANNEL)
                    file_download_url = result['file']['url_private_download']
                    CLIENT.chat_postEphemeral(channel=SLACK_CHANNEL,user=current_user,text=f'Find analysis report at {file_download_url}')
                    shutil.rmtree(f'{BOT_BASE_DIR}/{current_user}',onerror=handler)
                    IS_FREE = True


            return Response(status=200, headers={"X-Slack-No-Retry": 1})



def safe_open(path):
    ''' Open "path" for writing, creating any parent directories as needed.
    '''
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, 'w+b')

def handler(func, path, exc_info):
    print("Inside handler")
    print(exc_info)
