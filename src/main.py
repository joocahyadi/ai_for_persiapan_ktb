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
from email.utils import formataddr

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
        "https://www.googleapis.com/auth/bigquery"
        , "https://www.googleapis.com/auth/drive"
        , "https://www.googleapis.com/auth/spreadsheets"
    ]

    # final credentials to be injected when the system do the query
    bigq_credentials = service_account.Credentials.from_service_account_file(credential_path, scopes=scopes)

    # bigquery client
    bigq_client = bigquery.Client(project=project_id, credentials=bigq_credentials)

    # query
    query = f"""
        with upcoming_ktb_dates as (
            select
                ktb_date
            from {project_id}.{dataset_id}.{table_id}
            where
                status != 'Done'
            group by 1
        )

        select *
        from {project_id}.{dataset_id}.{table_id}
        where
            status != 'Done'
            and ktb_date = (select min(ktb_date) from upcoming_ktb_dates)
    """

    # to pull the tasks data from bigquery table
    query_job = bigq_client.query(query)
    rows = query_job.result()

    # compile all tasks
    tasks = []
    for row in rows:
        tasks.append({
            'pic_name': row['pic']
            , 'task_name': row['task']
            , 'deadline': row['task_deadline_date']
            , 'status': row['status']
            , 'ktb_date': row['ktb_date']
        })
    
    # To get the KTB date (will be used for email's subject later)
    unique_ktb_dates = {task['ktb_date'] for task in tasks}
    unique_ktb_dates = sorted(list(unique_ktb_dates))
    ktb_dates_for_email = [date.strftime('%d %B %Y') for date in unique_ktb_dates]
    ktb_dates_for_email = ', '.join(ktb_dates_for_email)
    
    return tasks, ktb_dates_for_email


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
    - Enter 3 newlines and close with saying "Thank You!" and add a thankful emoji
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

    return response.text

# Function to send email
def send_email(receiver_email_addresses, subject, body):

    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    sender_email_address = os.getenv('SENDER_EMAIL_ADDRESS')
    sender_email_password = os.getenv('SENDER_EMAIL_PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = formataddr(('KTB Reminder', sender_email_address))
    msg['To'] = ', '.join(receiver_email_addresses)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(sender_email_address, sender_email_password)
        server.sendmail(
            from_addr = sender_email_address
            , to_addrs = receiver_email_addresses
            , msg = msg.as_string()
        )

# Function to run the overall pipeline
def run_pipeline():

    try:
        # Get the tasks
        tasks, ktb_date = get_tasks()

        # Get the AI message
        ai_message = generate_ai_reminder(tasks)

        # Send the AI message via email
        recipient_list = [
            'joocahyadi@gmail.com'
            , 'joocahyadimy@gmail.com'
        ]
        subject = f'Tasks Reminder for Upcoming KTB {ktb_date}'
        send_email(recipient_list, subject, ai_message)
    
    except Exception as e:
        print(f'Error encountered: {str(e)}')

if __name__ == "__main__":
    run = run_pipeline()