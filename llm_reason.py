import requests
import json
import pdfplumber
url = "https://genai.rcac.purdue.edu/api/chat/completions"
jwt_token_or_api_key = "sk-a3a93ca2995c4526ab43bf91b6cce823"
headers = {
    "Authorization": f"Bearer {jwt_token_or_api_key}",
    "Content-Type": "application/json"
}

def check_reasoning(llm_reason: dict):
    versus = ""
    with open("activator-isolate-prsd.net", "r") as f:
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
        #print(response.text)
        jsonobj = json.loads(response.text)
        print(jsonobj["choices"][0]["message"]["content"])
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")


def infer_components_and_relations():
    netlistfile = ""
    nfiles = ["activator-isolate-prsd.net", "activator-connections-prsd.net"]
    for nfile in nfiles:
        with open(nfile, "r") as f:
            netlistfile += nfile + '\n'
            netlistfile += f.read()

    datasheetfile = ""
    dfiles = []
    with open("activator-isolate-prsd.net", "r") as f:
            jobj = json.load(f)
            #print(jobj)
            for j in jobj:
                if j["value"]:
                    dfiles.append("result/" + j["value"] + ".pdf")
    for dfile in dfiles:
        with open(dfile, "r") as f:
            datasheetfile += dfile + '\n'
            with pdfplumber.open(dfile) as pdf:
                for pg in pdf.pages:
                    text = pg.extract_text()
                    datasheetfile += text + '\n'

    prompt = '''
    You are an electrical systems analyst.

    You are given:
    1. A parsed netlist describing components and their connections
    2. Datasheet excerpts for each component

    Your task is to infer:
    - The FUNCTION of each component in the system
    - The RELATIONSHIPS between components
    - The SIGNAL TYPE of each connection:
    (control signal, feedback, power, data)
    - Any SAFETY CONCERNS or risks

    ---

    ## Rules

    - Base all conclusions ONLY on:
    (a) the netlist connections
    (b) the provided datasheets

    - Do NOT assume missing components or invent functionality
    - If uncertain, explicitly say "UNKNOWN" and explain why

    - Prefer reasoning from:
    pin names, voltage levels, typical usage in datasheets

    
    ## Required Output Format (STRICT JSON) DO NOT PRODUCE ANY OTHER OUTPUT. Your entire response will be parsed into JSON.
    {
    "components": [
        {
        "name": "...",
        "inferred_role": "...",
        "justification": "...",
        "confidence": 0.0-1.0
        }
    ],
    "connections": [
        {
        "from": "...",
        "to": "...",
        "signal_type": "control | feedback | power | data | unknown",
        "justification": "...",
        "confidence": 0.0-1.0
        }
    ],
    "relationships": [
        {
        "description": "...",
        "components": ["...", "..."],
        "type": "dependency | regulation | amplification | conversion | protection",
        "justification": "..."
        }
    ],
    "safety_concerns": [
        {
        "issue": "...",
        "components": ["..."],
        "severity": "low | medium | high",
        "reason": "..."
        }
    ]
    }

    ---

    ## Reasoning Strategy (IMPORTANT)

    Follow this process internally:

    1. Identify power sources and ground references first
    2. Identify ICs and their roles from datasheets
    3. Classify connections by pin function:
    - VCC/GND → power
    - EN/CTRL → control
    - OUT→IN loops → feedback
    - digital buses → data
    4. Look for common circuit patterns:
    - voltage regulators
    - amplifiers
    - filters
    - microcontroller + peripherals
    5. Infer relationships ONLY after classifying signals

    ---

    ## Input Data

    ### Netlist:
    ''' + netlistfile + '''
    ### Datasheets:
    ''' + datasheetfile + '''
    '''
    print(prompt)

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
        #print(response.text)
        jsonobj = json.loads(response.text)
        res = jsonobj["choices"][0]["message"]["content"]
        print(res)
        mmres = res.split("```")
        if len(mmres) >= 2:
            with open("llm_comp_analysis.json", "w", encoding="utf-8") as f:
                f.write(mmres[1])
    else:
        raise Exception(f"Error: {response.status_code}, {response.text}")

infer_components_and_relations()
#check_reasoning({"74AHC1G04": "makes magic unicorns", "74LVC1G332": "logic gate"})