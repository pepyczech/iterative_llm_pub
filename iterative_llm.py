import streamlit as st
import pandas as pd
import numpy as np

import warnings
from datetime import datetime
import json, os, sys, traceback, re, tempfile
import httpx, base64

import zipfile
from io import BytesIO
from zipfile import ZipFile

import openai
#from openai import OpenAI
from langchain.document_loaders import PyPDFLoader,Docx2txtLoader, TextLoader, CSVLoader #,PyMuPDFLoader
from langchain_community.document_loaders import UnstructuredExcelLoader, UnstructuredPowerPointLoader #, CSVLoader

# pip install "unstructured[all-docs]"

def check_openai_models(OPENAI_API_KEY,pattern=None):

    sys_prompt = "You are a helpful assistant that answers questions asked by the user."
        
    prompts = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": 'What color is snow?'}
            ]
    
    openai.api_key = OPENAI_API_KEY
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.models.list()
    
    model_overview={}
    for model in response.data:
    
        model_id = model.id
        
        cond = False
        if pattern is None: 
            cond=True
        else:
            if pattern.lower() in model_id.lower(): cond=True
    
        if cond:
            try:
                response = client.chat.completions.create(
                    model=model.id,
                    messages=prompts,
                    temperature=0.9,
                    max_tokens=5
                )
                value='Y'
                print(model_id)
            except:
                value='N'

            model_overview[model_id]=value

    return(model_overview)

def save_to_cwd_tempfile(uploaded_file):
    """
    Saves the uploaded file to a NamedTemporaryFile in the current working directory.
    Returns the temporary file's path.
    """
    # Preserve the original file extension
    suffix = os.path.splitext(uploaded_file.name)[1]
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=os.getcwd())
    temp.write(uploaded_file.getbuffer())  # write bytes to file
    temp.flush()
    temp.close()
    return temp.name

def load_document(file,imgs=False):
    
    name, extension = os.path.splitext(file)
    print(f'Loading {file}')

    load=1
    
    if extension == '.pdf':
            #pip install pymupdf
            #from langchain_community.document_loaders import PyMuPDFLoader
            # Initialize the loader with the path to your PDF file and set extract_images to True
            #loader = PyMuPDFLoader(file_path=file, extract_images=True)

            #pip install langchain pypdf
            #from langchain.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path=file, extract_images=imgs)
    elif extension == '.docx': 
        #from langchain.document_loaders import Docx2txtLoader 
        loader = Docx2txtLoader(file)
    elif extension in ['.ppt', '.pptx']:
        #from langchain_community.document_loaders import UnstructuredPowerPointLoader
        loader = UnstructuredPowerPointLoader(file, mode="elements")
    elif extension == '.txt': 
        #from langchain.document_loaders import TextLoader 
        loader = TextLoader(file)
    elif extension == '.csv':
        #from langchain_community.document_loaders import CSVLoader
        loader = CSVLoader(file_path=file)
    elif '.xls' in extension: # requires unstructured package - tricky to install
        #from langchain_community.document_loaders import UnstructuredExcelLoader
        loader = UnstructuredExcelLoader(file, mode="elements")

        # from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader - requires Azure subscription
        # https://python.langchain.com/docs/modules/data_connection/document_loaders/office_file/

    elif ('.png' in extension)|('.jp' in extension):
        print('This is an image')
        load=0

        with open(file, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        padding = '=' * (len(data) % 4)
        data = data + padding

        string_data=data
    
    else:
        print('Document format is not supported!')
        return(None)

    if load:
        data = loader.load()
    
        string_data = [doc.page_content for doc in data]
        string_data = "\n\n---\n\n".join(string_data)

    return(data,string_data)

# ------------ MAIN BODY

st.set_page_config(layout="wide")

tday = datetime.today().strftime('%Y%m%d')

# Navigation
#tab1, tab2 = st.tabs(["Settings", "Main"])

if 'base' not in st.session_state: st.session_state.base = None
if 'key' not in st.session_state: st.session_state.key = None
    
st.header("Settings")

with st.expander("Click to expand / collapse...", expanded=False):

    test = st.sidebar.checkbox("Debug mode", value=False, key="test_checkbox")
    show_model_info = st.sidebar.checkbox("Show model info", value=False, key="models_checkbox")

    st.subheader("Credentials")

    login = st.sidebar.toggle("Credentials in a JSON file", value=True, key="login_toggle")

    if login:
        #st.write("API Credentials stored in a file")
        #st.write("API Credentials stored in a file")
        creds_path = st.file_uploader("Select JSON file with credentials", type=["json"], key="creds_path")
        st.write('Required credentials format: {"base": "<URL>", "key": "<API Key>"}')

        # Read the file and parse JSON
        if creds_path is not None:
            with open(creds_path.name, 'r') as f:
                creds = json.load(f)
            st.session_state.base = creds['base']
            st.session_state.key = creds['key']

    else:
        st.write("Enter your API credentials")
        base = st.text_input("API Base", "https://api.openai.com/v1/chat/completions")
        key = st.text_input("API Key")

        if key and base:

            # Save credentials to a JSON file
            creds = {"base": base, "key": key}

            creds_path = "api_creds_latest.json"
            with open(creds_path, 'w') as f:
                json.dump(creds, f)

            creds_path = f"api_creds_{tday}.json"
            with open(creds_path, 'w') as f:
                json.dump(creds, f)

            st.write(f"Credentials saved to {creds_path}")
            st.session_state.base = creds['base']
            st.session_state.key = creds['key']

    models=None

    if st.sidebar.button("Test credentials"):

        if (st.session_state.base is not None) & (st.session_state.key is not None):
            st.success("Credentials are set")
        else:
            st.error("Credentials are not set")

        # Make a test API call to verify credentials
        try:

            client = openai.OpenAI(api_key=st.session_state.key)
            
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "user", "content": "What is the capital of France?"},
                ],
            )

            answer=completion.choices[0].message.content
            if test: st.write(f'Test API response: {answer}')
            if 'paris' in answer.lower():
                st.success("API call successful. Credentials are valid.")
                creds_bytes = json.dumps(creds).encode("utf-8")
                st.sidebar.download_button(
                    label="Download credentials",
                    data=creds_bytes,
                    file_name=f"api_creds_{tday}.json",
                    mime="application/json",
                    icon=":material/download:",
                    key='download-creds-button'
                )

            else:
                st.error("API call did not return the expected result. Please check your credentials.")

        except Exception as e:

            st.error(f"An error occurred: {str(e)}")

    if st.sidebar.button("Re-check model availability"):

        models=check_openai_models(st.session_state.key,pattern=None)  

        if test | show_model_info: 
            st.write("Available models:")
            st.json(models)

        # Save models to JSON file
        with open(f'models_latest.json', 'w') as f:
            json.dump(models, f, indent=4)
        with open(f'models_{tday}.json', 'w') as f:
            json.dump(models, f, indent=4)

    else:

        # Load models from JSON file if it exists
        if os.path.exists('models_latest.json'):
            with open('models_latest.json', 'r') as f:
                models = json.load(f)

            if test | show_model_info: 
                st.write("Available models:")
                st.json(models)
        else:
            st.warning("No models file found. Please re-check model availability.")
    models_bytes = json.dumps(models).encode("utf-8")
    st.sidebar.download_button(
        label="Download model list",
        data=models_bytes,
        file_name=f"models_list_{tday}.json",
        mime="application/json",
        icon=":material/download:",
        key='download-models-button'
    )

    #st.subheader("Select LLM Model")

    if models is not None:
        available_models = [model for model, available in models.items() if available == 'Y']
        if available_models:
            model = st.sidebar.selectbox("Select a model", available_models, index=0)
        else:
            st.error("No available models found.")
            model = None

    #st.header("Main page")

    st.subheader("User and System Prompts")

    choice = st.toggle("Upload user prompt from a file", value=False, key="prompt_toggle")

    if choice:
        
        user_prompt_path = st.file_uploader("Select a file with the user prompt")
        st.write('Compatible file types: txt, pdf, docx')

        # Read the file
        user_prompt = None

    else:
        
        user_prompt = st.text_input("Enter your user prompt", None)

    sys_choice = st.toggle("Upload system prompt from a file", value=False, key="sys_prompt_toggle")

    if sys_choice:
        
        sys_prompt_path = st.file_uploader("Select a file with the system prompt")
        st.write('Compatible file types: txt, pdf, docx')

        # Read the file

    else:
        
        sys_prompt = st.text_input("Enter your system prompt", "You are a helpful assistant.")

st.header("Process Documents")

with st.expander("Click to expand / collapse...", expanded=True):

    st.subheader("Upload one or more documents")

    web_search = st.sidebar.checkbox("Enable web search", value=False, key="web_search_checkbox")
    allow_api = st.sidebar.checkbox("Allow API calls", value=True, key="api_checkbox")

    if (user_prompt is None): 
        st.error("API calls are allowed but user_prompt is empty - disabling API calls.")
        allow_api=False

    if (sys_prompt is None): 
        st.error("API calls are allowed but sys_prompt is empty - disabling API calls.")
        allow_api=False

    if (st.session_state.key is None): 
        st.error("API calls are allowed but API key is missing - disabling API calls.")
        allow_api=False

    temp=st.sidebar.slider('Temperature', 0.0, 1.0, 0.1)
    #max_tokens=st.sidebar.slider('Max tokens', 0, 4096, (0, 4096))

    uploaded_file = st.file_uploader("Upload files", accept_multiple_files=True)

    allowed_extensions = ['pdf', 'docx', 'txt', 'csv', 'xls', 'xlsx', 'ppt', 'pptx']

    if uploaded_file:
        show_files = st.sidebar.checkbox("Show filenames", value=False, key="file_checkbox")
        if show_files: 
            files=[file.name for file in uploaded_file]
            st.write(f"Uploaded files: {files}")

        count=0

        if allow_api: client = openai.OpenAI(api_key=st.session_state.key)

        # Initialize zipFile in memory
        #with ZipFile('response.zip', mode='w') as zf:
        zip_buffer = BytesIO()

        # Initialize an empty ZIP archive in memory
        with zipfile.ZipFile(zip_buffer, mode='w') as zip_archive:
            pass  # No files added yet — this sets up the ZIP structure

        # Rewind the buffer to the beginning
        zip_buffer.seek(0)

        for file in uploaded_file:

            try:

                # Save the uploaded file to a temporary file
                st.write(f'Processing file {file.name} - file no {count+1} of {len(uploaded_file)}')
                count+=1
                file_name = save_to_cwd_tempfile(file)

                file_extension = file_name.split('.')[-1].lower()

                if test: st.write(f'File extension: {file_extension}')

                if file_extension in allowed_extensions:

                    _,docs=load_document(file_name)

                    if test: 
                        st.write(uploaded_file)
                        st.write(file)
                        st.write(docs)

                # Process the data

                if sys_prompt is None: sys_prompt = "You are a helpful assistant that answers questions asked by the user."
                
                prompts = [
                        {"role": "system", "content": str(sys_prompt)},
                        {"role": "user", "content": str(user_prompt) + "\n\n" + docs}
                        ]

                if test: print(prompts)

                response=''
                final_response = "No response"

                if allow_api:
                    if web_search:
                        response = client.responses.create(
                            model=model,
                            tools=[{"type": "web_search_preview"}],
                            input=prompts,
                            temperature=temp
                        )
                        final_response = response.output_text
                    else:
                        response = client.chat.completions.create(
                            model=model,
                            messages=prompts,
                            temperature=temp
                        )

                        final_response = response.choices[0].message.content
                    
                if test: 
                    print(response)
                    print(final_response)

                fn_out = file.name.split('\\')[-1].split('/')[-1].replace('.','-')
                fn_out = f'response_{fn_out}_{tday}'

                # Save response to a text file
                response_file = f'{fn_out}.txt'

                with open(response_file, 'w') as f:
                    f.write(final_response)

                response_file_md = f'{fn_out}.md'

                with open(response_file_md, 'w', encoding='utf-8') as f:
                    f.write(final_response)

                # Add the response file to the zip archive
                #with ZipFile('response.zip', mode='a') as zf:
                with zipfile.ZipFile(zip_buffer, mode='a', compression=zipfile.ZIP_DEFLATED) as zip_archive:
                    #zip_archive.write(response_file_md)
                    zip_archive.writestr(response_file_md, final_response)

            except Exception as e:

                st.write(f'Error reading file {file_name}: {e}')
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback,limit=5, file=sys.stdout)

        zip_buffer.seek(0)

        # Downlad zip file ...
        st.download_button(
            label="Download zipped response files...",
            data=zip_buffer,
            file_name=f"responses_{tday}.zip",
            mime="application/zip",
            icon=":material/download:",
            key='download-zip-button'
        )