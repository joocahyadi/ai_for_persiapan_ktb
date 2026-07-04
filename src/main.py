import os
from google.cloud import bigquery
from google.oauth2 import service_account
from google import genai
import urllib.parse
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Function to get the tasks from bigquery
def get_tasks():
   
    # bigquery table details
    project_id = 'database-kp-gki-puri'
    dataset_id = 'ktb_pemuda'
    table_id = 'task_list_pktb'

    # bigquery credentials
    bigq_credentials_file = os.getenv('BIGQUERY_CREDENTIALS')
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credential_path = os.path.join(base_dir, bigq_credentials_file)

    # bigquery scopes
    # need to add these so bigquery can access google sheet, as our table source is from gsheet
    scopes = [
        "https://www.googleapis.com/auth/bigquery",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    # final credentials to be injected when the system do the query
    bigq_credentials = service_account.Credentials.from_service_account_file(credential_path, scopes=scopes)

    # bigquery client
    bigq_client = bigquery.Client(project=project_id, credentials=bigq_credentials)

    # query
    query = f"""
        select *
        from {project_id}.{dataset_id}.{table_id}
        where
            status != 'Done'
    """

    query_job = bigq_client.query(query)
    rows = query_job.result()

    tasks = []
    for row in rows:
        tasks.append({
            'pic_name': row['pic']
            , 'task_name': row['task']
            , 'deadline': row['task_deadline_date']
            , 'status': row['status']
        })
    
    return tasks


# Function to activate gemini and make a message based on the list of tasks that we got from query earlier
def generate_ai_reminder(tasks):

    # Activate Google Gen AI client (to use Gemini later)
    ai_client = genai.Client(api_key=os.getenv('GEN_AI_API_KEY'))

    # Prompt for the AI agent
    prompt = f"""
    You are a group coordinator that reminds each person of their own tasks. Draft a short, conversational 
    whatsapp reminder.

    Here is the list of tasks that need a reminder today:
    {tasks}

    Requirements:
    - Keep it very brief (maximum 3-4 sentences)
    - Tone: Helpful and kind peer

    Output format:
    - Begin by saying Hi all or Hello all in cheerful tone and give a wave emoji
    - After that, enter a newline and open with saying a sentence about the message, e.g. Here's the summary of uncomplete tasks
    - For each person, state these things in its own bullet points
    -- Task name, Current Task Status, and Deadline
    - If there are more than 1 tasks that have same PIC, do not combine them. Re-state the PIC name. 
    - Add a closing sentence, to support and encourage in a friendly tone. Please also add strong and fire emojis.
    - After that, remind all to fill their task in this link https://bit.ly/task-list-pktb
    - Please comply to these output formats.

    Output template:
    Opening 
    PIC Name (No need to bold the name)

    - Task Name (straightly state the Task Name)
    - Current Status: the Current Status
    - Deadline: the deadline

    Closing
    """

    # To get the Gemini response
    response = ai_client.models.generate_content(
        model = 'gemini-2.5-flash'
        , contents = prompt
    )

    print(response.text)


if __name__ == "__main__":
    # run = get_tasks()
    run = generate_ai_reminder(get_tasks())