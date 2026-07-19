import os 
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel
import streamlit as st
import tempfile
import json

load_dotenv()

my_api_key = os.getenv("GROQ_API_KEY")

if not my_api_key:
    raise ValueError("Not found your api key!")

client = Groq(api_key=my_api_key)
model = "llama-3.3-70b-versatile"

#Paste job decription here
st.title("🤖 AI Resume Evaluator")

job_description = st.text_area(
    "Paste Job Description",
    height=250
)

class jobD(BaseModel):
    role:str
    required_skils:list[str]
    preferred_skils:list[str]
    minimum_experience:float | None
    education_requirements:list[str]
    responsibilities:list[str]

jobd_schema = jobD.model_json_schema()

sytem_prompt = f"""
You are an expert HR assistant.

Your job is to analyze the job description and extract
the following information from it.

Return only valid JSON matching the following schema:
{jobd_schema}

IMPORTANT:
DO NOT return schema itself.
DO NOT return fields like "properties", "title", or "type".
Fill schema fields with the information extracted from the job description.

If minimum_experience is not mentioned in the job description, return null for that field.
If information for list fields is not mentioned in the job description, return an empty list for that field.
Do not invent any information.
"""

# user_prompt = f"""
# Analysze the following job description
# {job_description}
# """

# message_system = {"role": "system", "content": sytem_prompt}
# message_user = {"role": "user", "content": user_prompt}

# response_format = {"type" : "json_object"}

# messages = [message_system, message_user]

# response = client.chat.completions.create(model=model, messages=messages, response_format=response_format)

# ans = response.choices[0].message.content
# raw_json = ans

# #convert text answer to json object
# import json
# job_data = json.loads(raw_json)

# job = jobD(**job_data)

# print(job.minimum_experience)
# print(job.role)

class MatchResult(BaseModel):
    score : float
    details : dict

class Experience(BaseModel):
    company : str |None = None
    role : str |None = None
    duration : str | None = None
    skills_used : list[str] = []
    description : str | None = None

class Resume(BaseModel):
    name : str | None = None
    email : str | None = None
    phone : str | None = None

    total_experience : float | None = None

    skills : list[str] = []
    experiences : list[Experience] = []
    education : list[str] = []
    projects : list[str] = []
    certifications : list[str] = []

resume_schema = Resume.model_json_schema()

uploaded_files = st.file_uploader(
    "Upload resumes",
    type=["pdf", "docx"],
    accept_multiple_files=True
)

def final_score(job,resume):
    match_schema = MatchResult.model_json_schema()
    prompt = f"""
    You are an HR recruiter.
    Compare candidate's resume with the job description.

    JOB DESCRIPTION:
    {job.model_dump_json(indent=2)}

    CANDIDATE RESUME:
    {resume.model_dump_json(indent=2)}
    Return JSON matching this schema:

    {match_schema}

    Give me:

    1. Candidate name
    2. Matching skills
    3. Missing important skills
    4. Whether experience requirement is met
    5. Overall match percentage from 0 to 100
    6. A short final verdict

    Keep the response concise and easy to read.
    """

    message={
        "role": "user",
        "content" : prompt
    }
    messages=[message]
    response_format={
        "type": "json_object"
    }
    response = client.chat.completions.create(model=model, messages=messages, response_format=response_format)
    data = json.loads(response.choices[0].message.content)
    return MatchResult(**data)

def parse_resume(resume_text):
    system_prompt = f"""
    You are an expert resume parser.

    Extract information from the resume based on its meaning,
    not only based on exact section headings.

    Different resumes may use different headings.

    For example:
    - Experience
    - Professional Experience
    - Work History
    - Employment
    - Internships

    These may all contain relevant experience.

    Skills may also appear in the skills section, work experience,
    internships or projects.

    Return ONLY valid JSON matching this schema:

    {resume_schema}

    Important rules:

    1. Do not invent information.
    2. If a value is not available, return null.
    3. If a list has no information, return an empty list.
    4. Include internships inside experiences.
    5. Extract skills mentioned across the entire resume.
    """
    user_prompt = f"""
    Parse the following resume:

    {resume_text}
    """
    message_system={
        "role" : "system",
        "content" : system_prompt
    }
    message_user={
        "role" : "user",
        "content" : user_prompt
    }
    messages=[message_system, message_user]
    response_format={
        "type": "json_object"
    }
    response=client.chat.completions.create(model=model, messages=messages, response_format=response_format)
    raw_output = response.choices[0].message.content
    data = json.loads(raw_output)
    resume = Resume(**data)
    return resume

from pypdf import PdfReader
from docx import Document
import time

def read_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def read_docx(file_path):
    document = Document(file_path)
    text = ""
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"
    
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text += cell.text + "\n"
    return text


def read_resume(file_path):
    if file_path.suffix.lower() == ".pdf":
        return read_pdf(file_path)
    elif file_path.suffix.lower() == ".docx":
        return read_docx(file_path)
    else:
        return None



if st.button("Evaluate"):

    if not job_description.strip():
        st.warning("Please enter a job description.")
        st.stop()

    
    user_prompt = f"""
    Analyze the following job description

    {job_description}
    """

    message_system = {
        "role":"system",
        "content":sytem_prompt
    }

    message_user = {
        "role":"user",
        "content":user_prompt
    }

    messages=[message_system,message_user]

    response_format={
        "type": "json_object"
    }

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format=response_format
    )

    ans = response.choices[0].message.content

    job_data = json.loads(ans)

    job = jobD(**job_data) #job is json object of jobD class

    if not uploaded_files:
        st.warning("Please upload at least one resume.")
        st.stop()

    all_results = []

    with st.spinner("Evaluating resumes..."):

        for uploaded_file in uploaded_files:

            suffix = Path(uploaded_file.name).suffix

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getbuffer())
                temp_path = Path(tmp.name)

            try:
                st.write(f"Processing **{uploaded_file.name}**")

                resume_text = read_resume(temp_path)

                parsed_resume = parse_resume(resume_text)

                time.sleep(5)

                result = final_score(job, parsed_resume)

                time.sleep(5)

                all_results.append({
                    "name": parsed_resume.name,
                    "score": result.score,
                    "details": result.details
                })
            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {e}")
            finally:
                temp_path.unlink(missing_ok=True)

    all_results.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    st.success("Evaluation Completed!")

    st.subheader("🏆 Top Candidates")

    for candidate in all_results[:2]:
        st.write(f"### {candidate['name']}")
        st.write(f"**Score:** {candidate['score']}%")
        st.json(candidate["details"])

    st.subheader("📉 Lowest Candidates")

    for candidate in all_results[-2:]:
        st.write(f"### {candidate['name']}")
        st.write(f"**Score:** {candidate['score']}%")
        st.json(candidate["details"])