import requests
import json
import pdfplumber
import os
from dotenv import load_dotenv
load_dotenv()

url = "https://genai.rcac.purdue.edu/api/chat/completions"
jwt_token_or_api_key = os.getenv("JWT_TOKEN")
headers = {
    "Authorization": f"Bearer {jwt_token_or_api_key}",
    "Content-Type": "application/json"
}

def check_reasoning(llm_reason: dict):
    versus = ""
    with open("isolate-prsd.net", "r") as f:
        jobj = json.load(f)
        #print(jobj)
        for j in jobj:
            comp = None
            if j["value"] in llm_reason:
                comp = j["value"]
            elif j["ref"] in llm_reason:
                comp = j["ref"]
            if comp:
                versus += j["value"] + " - " + j["ref"] + ": " + "Actual Description: " + j["desc"] + " LLM Description: " + llm_reason[comp] + '\n'
    prompt = "Give a confidence score for the reasoning of the LLM for each component compared to the actual desctiption. (The actual description is correct, just evaluate the LLM descriptions):\n" + versus
    body = {
        "model": "gpt-oss:120b",
        "messages": [
        {
            "role": "user",
            "content":  prompt
        }
        ]
    }
    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        print(response.text)
        jsonobj = json.loads(response.text)
        print(jsonobj["choices"][0]["message"]["content"])
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")


def infer_components_and_relations():
    netlistfile = ""
    nfiles = ["prsd.net", "connections-prsd.net"]
    for nfile in nfiles:
        with open(nfile, "r") as f:
            netlistfile += nfile + '\n'
            netlistfile += f.read()
    templatefile = ""
    tpfile = "cubesat_obc-final.json"
    with open(tpfile, "r") as f:
            templatefile += tpfile + '\n'
            templatefile += f.read()
    datasheetfile = ""
    dfiles = []
    with open("isolate-prsd.net", "r") as f:
            jobj = json.load(f)
            #print(jobj)
            for j in jobj:
                if j["value"]:
                    dfiles.append("result/" + j["value"] + ".pdf")
    for dfile in dfiles:
        if os.path.exists(dfile):
            with open(dfile, "r") as f:
                datasheetfile += dfile + '\n'
                try:
                    with pdfplumber.open(dfile) as pdf:
                        for pg in pdf.pages:
                            text = pg.extract_text()
                            datasheetfile += text + '\n'
                except:
                    datasheetfile += "N/A" + '\n'
    hfile = "STPA_Handbook.pdf"
    handbookfile = ""
    with open(hfile, "r") as f:
        handbookfile += hfile + '\n'
        try:
            with pdfplumber.open(hfile) as pdf:
                for pg in pdf.pages:
                    text = pg.extract_text()
                    handbookfile += text + '\n'
        except:
            handbookfile += "N/A" + '\n'

    prompt = '''
    <role>
    You are a systems safety engineer writing a reference document for hardware analysts
    performing STPA (System-Theoretic Process Analysis) on electronic hardware systems.
    </role>

    <task>
    Your task is to produce a component STPA role classification reference table for RF front-end circuits based on the list provided.
    </task>

    <STRICT_RULES>
    1. Every classification MUST be derivable from Leveson & Thomas, STPA Handbook
    (MIT, 2018) attached. Specifically, apply the definitions of controller, actuator, sensor,
    controlled_process, communication_channel, and passive from Chapter 2.
    2. If a component type's role is genuinely context-dependent, say so explicitly with
    a "Context-dependent" entry and explain BOTH possible roles and when each applies.
    3. If you are uncertain about a component type's typical role, mark it with
    "(NEEDS EXPERT REVIEW)" rather than guessing.
    4. Do NOT fabricate component behavior. If you do not know the typical function of a
    component type, omit it.
    </STRICT_RULES>

    <format>
    For each component type, produce:
    - Component type name and common examples (part numbers or families)
    - Typical STPA role (enum: controller | actuator | sensor | controlled_process |
    communication_channel | passive)
    - One-sentence reasoning grounded in Leveson's definition of that role
    - Any exceptions or context-dependencies

    Group by functional category (e.g., Power Components, RF Components,
    Digital Logic, etc.)

    End with a "Classification Guidelines" section covering:
    - How to handle components that serve multiple roles in the same system
    - Default tie-breaking rules when classification is ambiguous
    </format>

    ## Input Data

    ### Template:
    ''' + templatefile + '''
    ### STPA Handbook:
    ''' + handbookfile + '''
    ### Netlist:
    ''' + netlistfile + '''
    ### Datasheets:
    ''' + datasheetfile + '''
    '''
    with open("prompt.txt", "w") as f:
        f.write(prompt)

    body = {
        "model": "gpt-oss:120b",
        "messages": [
        {
            "role": "user",
            "content":  prompt
        }
        ]
    }
    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        print(response.text)
        jsonobj = json.loads(response.text)
        res = jsonobj["choices"][0]["message"]["content"]
        print(res)
        mmres = res.split("```")
        if len(mmres) >= 2:
            with open("llm_comp_analysis.json", "w", encoding="utf-8") as f:
                f.write(mmres[1])
        else:
            with open("llm_comp_analysis.json", "w", encoding="utf-8") as f:
                f.write(res)
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

#infer_components_and_relations()
#check_reasoning({"74AHC1G04": "makes magic unicorns", "74LVC1G332": "logic gate"})