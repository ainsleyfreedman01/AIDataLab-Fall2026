"""
Scrapes official state- and school-district-level K-12 AI policy/guidance
documents (PDF, DOCX, or HTML) and writes the full extracted text of each into
a CSV for analysis.

States are grouped by 2025 private AI investment (Quid via the 2026 AI Index
report), following the map's buckets: >= $1B is ai_development_hub,
$100M-$1B is moderate_ai_development, < $100M or no data is
limited_ai_development.

Usage: python3 scrape_k12_ai_policies.py
Output: k12_ai_policies.csv (state, ai_private_investment_2025, comparison_group,
        level, doc_type, title, source_url, date_retrieved, status, char_count,
        full_text) and k12_ai_policies_singleline.csv (same, with full_text on
        one line)
"""

import csv
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import pdfplumber

# 2025 private AI investment in USD (Quid, 2025; chart: 2026 AI Index report).
# None = no data reported.
AI_INVESTMENT_2025 = {
    "California": 218e9, "Colorado": 19e9, "New York": 13e9, "Florida": 6e9,
    "Texas": 5e9, "Massachusetts": 5e9, "Delaware": 3e9, "Washington": 2e9,
    "Pennsylvania": 2e9, "Virginia": 2e9, "Georgia": 1e9,
    "Utah": 958e6, "North Carolina": 874e6, "New Jersey": 865e6,
    "Connecticut": 741e6, "Ohio": 723e6, "Illinois": 696e6, "Nevada": 539e6,
    "District of Columbia": 533e6, "Arizona": 504e6, "Maryland": 427e6,
    "Nebraska": 415e6, "Minnesota": 328e6, "Tennessee": 302e6, "Missouri": 280e6,
    "Michigan": 239e6, "Oregon": 189e6, "Mississippi": 117e6, "Wisconsin": 117e6,
    "Indiana": 86e6, "Hawaii": 86e6, "Rhode Island": 68e6, "Montana": 63e6,
    "Kansas": 50e6, "Vermont": 40e6, "New Hampshire": 36e6,
    "Wyoming": 35e6, "Kentucky": 34e6, "New Mexico": 33e6, "Iowa": 33e6,
    "Maine": 29e6, "Alabama": 28e6, "Idaho": 26e6, "Louisiana": 17e6, "Alaska": 11e6,
    "North Dakota": 6e6, "South Carolina": 6e6,
    "West Virginia": None, "Oklahoma": None, "Arkansas": None, "South Dakota": None,
}


def format_investment(amount: float | None) -> str:
    if amount is None:
        return "no data"
    return f"${amount / 1e9:g}B" if amount >= 1e9 else f"${amount / 1e6:g}M"


def comparison_group(state: str) -> str:
    amount = AI_INVESTMENT_2025[state] or 0
    if amount >= 1e9:
        return "ai_development_hub"
    if amount >= 100e6:
        return "moderate_ai_development"
    return "limited_ai_development"


GROUP_ORDER = ["ai_development_hub", "moderate_ai_development", "limited_ai_development"]

# doc_type vocabulary: guidance, model_policy, policy, draft_policy,
# guidebook_or_handbook, task_force_or_report, resource_page, position_statement
#
# Per state: the official state-level (or state-task-force) K-12 AI guidance,
# plus at least one real district-level AI policy/guidance document.
# Rows are append-only so existing policy_id values (POL-###) stay stable.
SOURCES = [
    {
        "state": "California",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence in Public Schools: Guidance (California Department of Education)",
        "url": "https://www.cde.ca.gov/ci/pl/documents/aiguidance.pdf",
    },
    {
        "state": "California",
        "level": "state",
        "doc_type": "model_policy",
        "title": "Model Policy: Artificial Intelligence in Education (California Department of Education; nonbinding template)",
        "url": "https://www.cde.ca.gov/ci/pl/documents/aimodelpolicy.docx",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "policy",
        "title": "Guidelines for the Authorized Use of Artificial Intelligence for the District (Los Angeles Unified School District Policy Bulletin)",
        "url": "https://media.edlio.net/3476a301/6d998082/01503609/1dd0fae97a594f01aadad0a950d4ea11?_=BUL-151113_0_Guidelines_for_the_Authorized_Use_of_Artificial_Intelligence_for_District.pdf",
    },
    {
        "state": "Washington",
        "level": "state",
        "doc_type": "guidance",
        "title": "Human-Centered AI Guidance for K-12 Public Schools (OSPI)",
        "url": "https://ospi.k12.wa.us/sites/default/files/2024-08/comprehensive-ai-guidance.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Artificial Intelligence Handbook for Seattle Public Schools",
        "url": "https://www.seattleschools.org/wp-content/uploads/2025/02/AI-Handbook-ADA.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Bellevue School District Artificial Intelligence Handbook",
        "url": "https://resources.finalsite.net/images/v1789071509/bsd405org/j5limaqb5svwn6mxyt27/BSD_AI_Handbook.pdf",
    },
    {
        "state": "Texas",
        "level": "state",
        "doc_type": "task_force_or_report",
        "title": "Texas AI in Education Task Force Report / Whitepaper (TACC, UT Austin)",
        "url": "https://tacc.utexas.edu/media/filer_public/18/e5/18e507b4-4f78-4566-8261-d9e3bb1ae6dd/whitepaper-aiedu-061726.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI in Dallas ISD (Dallas Independent School District)",
        "url": "https://www.dallasisd.org/departments/library-media-services/ai-in-dallas-isd",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Houston ISD AI Guidebook (Houston Independent School District)",
        "url": "https://resources.finalsite.net/images/v1777472784/houstonisdorg/ffvo6lng6pttnchgfzgh/25-26HISDAIGuidebook.pdf",
    },
    {
        "state": "New York",
        "level": "state",
        "doc_type": "task_force_or_report",
        "title": "Artificial Intelligence (AI) and P-12 Education (NYS Board of Regents / NYSED)",
        "url": "https://www.regents.nysed.gov/sites/regents/files/P-12%20-%20Artificial%20Intelligence%20AI%20and%20P-12%20Education.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "guidance",
        "title": "Guidance on Artificial Intelligence and Screen Time (New York City Public Schools)",
        "url": "https://www.schools.nyc.gov/about-us/policies/guidance-on-artificial-intelligence",
    },
    {
        "state": "Pennsylvania",
        "level": "state",
        "doc_type": "guidance",
        "title": "Implementing AI in Schools (Pennsylvania Department of Education)",
        "url": "https://www.pa.gov/agencies/education/ai-digital-media-literacy/implementingaiinschools",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 815.1 - Use of Artificial Intelligence in Education (Allentown School District)",
        "url": "https://go.boarddocs.com/pa/alen/Board.nsf/files/DJSJBG4C61DC/$file/Policy%20815.1%20-%20Use%20of%20Artificial%20Intelligence%20in%20Education.pdf",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI Resources - PSTV (School District of Philadelphia)",
        "url": "https://www.philasd.org/pstv/ai-resources/",
    },
    {
        "state": "Massachusetts",
        "level": "state",
        "doc_type": "guidance",
        "title": "Massachusetts Guidance for Artificial Intelligence in K-12 Education (DESE)",
        "url": "https://www.doe.mass.edu/edtech/ai/ai-guidance.pdf",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "policy",
        "title": "Boston Public Schools Artificial Intelligence (AI) Policy",
        "url": "https://resources.finalsite.net/images/v1781118968/bostonpublicschoolsorg/n10whyxn8axn0urvgidh/FINALAIPolicy.pdf",
    },
    {
        "state": "Georgia",
        "level": "state",
        "doc_type": "guidance",
        "title": "Leveraging AI in the K-12 Setting (Georgia Department of Education)",
        "url": "https://gystc.org/wp-content/uploads/2025/04/Leveraging-AI-in-the-K-12-Setting.pdf",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "position_statement",
        "title": "Position Statement on the Use of Artificial Intelligence (AI) (Atlanta Public Schools)",
        "url": "https://resources.finalsite.net/images/v1773083346/atlantapublicschoolsus/urglvv8r7nym56wp0yn2/FINALPositionStatementontheUseofArtificialIntelligenceAI.pdf",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "AI Use Policies for Educators and Students (Draft, Taliaferro County School District)",
        "url": "https://www.taliaferro.k12.ga.us/AIPOLICY",
    },
    # --- Comparison group: states with limited AI development ecosystems ---
    {
        "state": "Mississippi",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance for K-12 Classrooms (Mississippi Department of Education)",
        "url": "https://www.mdek12.org/sites/default/files/Offices/MDE/OTSS/DL/ai_guidance_final.pdf",
    },
    {
        "state": "Mississippi",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Jackson Public Schools Educational Technology)",
        "url": "https://go.jpsms.org/support/artificial-intelligence",
    },
    {
        "state": "Alabama",
        "level": "state",
        "doc_type": "model_policy",
        "title": "AI Policy Template for Local Education Agencies (Alabama State Department of Education; nonbinding template; copy hosted by AI for Education)",
        "url": "https://static1.squarespace.com/static/64398599b0c21f1705fb8fb3/t/678fd217426bd7762e1de99a/1737478679458/AL+AI_PolicyTemplate_UPDATED_20240524.docx",
    },
    {
        "state": "Alabama",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy 7.17 - Artificial Intelligence (Baldwin County Public Schools)",
        "url": "https://resources.finalsite.net/images/v1762964884/bcbeorg/rqjomwmvpurorthrpwvb/FinalAIPolicy3.pdf",
    },
    {
        "state": "West Virginia",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidance, Considerations, and Intentions for the Use of Artificial Intelligence in West Virginia Schools v1.2 (WVDE)",
        "url": "https://wvde.us/sites/default/files/2025-03/WVDE%20AI%20Guidance%201.2%20March%202025.pdf",
    },
    {
        "state": "West Virginia",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance (Berkeley County Schools)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/3649/Bcs/74ba6ef6-5970-4f68-9968-ac974b8a6d5e/AI_Guidance.pdf?disposition=inline",
    },
    {
        # KDE's full classroom guidance PDF is image-only (no text layer), so
        # the text-based KDE AI Guidance Brief is used instead.
        "state": "Kentucky",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance Brief (Kentucky Department of Education)",
        "url": "https://apps.legislature.ky.gov/CommitteeDocuments/28/30685/KDE%20AI%20Guidance%20Brief.pdf",
    },
    {
        "state": "Kentucky",
        "level": "district",
        "doc_type": "guidance",
        "title": "Guidance for the Use of Artificial Intelligence (Fayette County Public Schools)",
        "url": "https://resources.finalsite.net/images/v1725033477/fcpsnet/zjhpqsmaksfwrbitqpjy/AI_guidance.pdf",
    },
    {
        "state": "Oklahoma",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidance and Considerations for Using Artificial Intelligence in Oklahoma K-12 Schools v3.0 (Oklahoma State Department of Education)",
        "url": "https://oklahoma.gov/content/dam/ok/en/osde/ai-and-digital-learning/Guidance%20for%20Using%20AI%20in%20Oklahoma%20Schools%20v.3.pdf",
    },
    {
        "state": "Oklahoma",
        "level": "state",
        "doc_type": "model_policy",
        "title": "Model Policy: Artificial Intelligence (AI) Use in Schools (Oklahoma State Department of Education; nonbinding template)",
        "url": "https://oklahoma.gov/content/dam/ok/en/osde/ai-and-digital-learning/Model%20Policy%20Artificial%20Intelligence%20AI%20Use%20in%20Schools.docx.pdf",
    },
    {
        "state": "Oklahoma",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence (AI) Guiding Philosophy for Educator and Learner Use (Owasso Public Schools)",
        "url": "https://www.owassops.org/departments/instructional-services/artificial-intelligence-ai-guiding-philosophy-for-educator-and-learner-use",
    },
    {
        "state": "Oklahoma",
        "level": "district",
        "doc_type": "guidance",
        "title": "MPS AI Instructional Use Guidelines (Moore Public Schools)",
        "url": "https://resources.finalsite.net/images/v1708119964/mooreschoolscom/xa6lh9ryiy9zuu1amorz/MPSAIInstructionalUseGuidelines.pdf",
    },
    {
        "state": "Wyoming",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidance for Wyoming School Districts on Developing Artificial Intelligence Use Policy (Wyoming Department of Education)",
        "url": "https://edu.wyoming.gov/wp-content/uploads/2024/06/Guidance-for-AI-Policy-Development.pdf",
    },
    {
        "state": "Wyoming",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI in Education - Parent Information (Sheridan County School District 2)",
        "url": "https://scsd2.com/technology/ai-in-education-parent-information",
    },
    {
        "state": "Louisiana",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence in Louisiana Schools: Guidance for K-12 Schools (Louisiana Department of Education)",
        "url": "https://doe.louisiana.gov/docs/default-source/technology-footprint/ldoe-ai-guidance.pdf?sfvrsn=eb706e18_4",
    },
    {
        "state": "Louisiana",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI in EBR (East Baton Rouge Parish School System)",
        "url": "https://ebrschools.org/ai/",
    },
    # --- Additional district-level sources ---
    {
        "state": "California",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Long Beach Unified School District)",
        "url": "https://www.lbschools.net/departments/tisb/ai",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence (Tacoma Public Schools)",
        "url": "https://www.tacomaschools.org/departments/technology/artificial-intelligence",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "position_statement",
        "title": "AI Vision (Highline Public Schools)",
        "url": "https://resources.finalsite.net/images/v1780532492/highlineschoolsorg/acsezkof4hxj9y72y25r/HighlinePublicSchools-AIVision.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy CQD(LOCAL) - Technology Resources: Artificial Intelligence (Austin Independent School District)",
        "url": "https://go.boarddocs.com/tx/austinisd/Board.nsf/files/DTFRR56F2F31/$file/Attachment%201%20-%20CQD(LOCAL)%20Technology%20Resources%2C%20Artificial%20Intelligence.docx.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI in NISD (Northwest Independent School District)",
        "url": "https://ai.nisdtx.org/",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 232.1 - Use of Artificial Intelligence (IDEA Public Schools)",
        "url": "https://ideapublicschools.org/wp-content/uploads/2026/04/232.1-Artificial-Intelligence-signed-1.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "guidance",
        "title": "District AI Guidelines (Rochester City School District)",
        "url": "https://sites.google.com/rcsd121.org/artificial-intelligence/district-ai-guidelines",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Central Bucks School District)",
        "url": "https://www.cbsd.org/departments/technology-innovation/artificial-intelligence-ai",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "guidance",
        "title": "Generative AI (GenAI) Guidance (Cambridge Public Schools)",
        "url": "https://www.cpsd.us/administration/information-communication-technology-services/generative-ai-guidance",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI in NPS - District AI Guidelines (Newton Public Schools)",
        "url": "https://www.newton.k12.ma.us/departments-programs/information-technology-library-services/digital-learning/ai-in-nps",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "guidance",
        "title": "GCPS Guidance for Human-Centered AI Use (Gwinnett County Public Schools)",
        "url": "https://www.gcpsk12.org/programs-and-services/college-and-career-development/academies-and-career-technical-and-agricultural-education/artificial-intelligence-and-computer-science/guidance-for-human-centered-ai-use",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI for Students (DeKalb County School District)",
        "url": "https://its.dekalb.k12.ga.us/AIforStudents.aspx",
    },
    {
        "state": "West Virginia",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 7540.08 - Artificial Intelligence (Jackson County Schools)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/1141/Jcs/45059c8a-aeb6-40dc-ada6-b61a405a6e98/New_Policy_7540.08__Artificial_Intelligence.pdf?disposition=inline",
    },
    {
        "state": "Louisiana",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy EFAB - Employee and Student Acceptable Use Policy for Artificial Intelligence (Rapides Parish School Board)",
        "url": "https://resources.finalsite.net/images/v1771813417/rpsbus/d6bxrin71ffsarlvp82p/RPSB_AIPolicy_Nov2025.pdf",
    },
    {
        "state": "Louisiana",
        "level": "district",
        "doc_type": "policy",
        "title": "Employee Acceptable Use of Technology Resources Agreement and Artificial Intelligence Addendum (Grant Parish School Board)",
        "url": "https://grantpsb.org/wp-content/uploads/2026/08/GPPS_Employee_Acceptable_Use_Technology_AI_Addendum_Accessible.pdf",
    },
    {
        "state": "Wyoming",
        "level": "district",
        "doc_type": "policy",
        "title": "Technology Policies 7100/7100-R incl. AI Platforms (Campbell County School District 1)",
        "url": "https://www.ccsd.k12.wy.us/families/district-universal-handbook-pages/technology",
    },
    {
        "state": "Kentucky",
        "level": "district",
        "doc_type": "resource_page",
        "title": "About Digital Classrooms - AI in Education (Union County Public Schools)",
        "url": "https://www.union.kyschools.us/apps/pages/index.jsp?uREC_ID=488860&type=d&pREC_ID=1359141",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy 0441 - Artificial Intelligence (Lodi Unified School District)",
        "url": "https://www.lodiusd.net/boardpolicies/0000/0441-articicial-intelligence",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence (Palo Alto Unified School District)",
        "url": "https://www.pausd.org/school-life/education-technology/ai",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence (AI) Guidelines (Dinuba Unified School District)",
        "url": "https://www.dinuba.k12.ca.us/departments/educational-technology/ai",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence in Education (San Mateo Union High School District)",
        "url": "https://www.smuhsd.org/departments/curriculum-and-assessment/artificial-intelligence-in-education",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "guidance",
        "title": "Responsible Use of AI (ABC Unified School District)",
        "url": "https://www.abcusd.us/apps/pages/ai",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Fort Bend Independent School District)",
        "url": "https://www.fortbendisd.gov/departments/teaching-and-learning/artificial-intelligence",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "policy",
        "title": "Artificial Intelligence Guidelines - Administrative Regulations (Argyle Independent School District)",
        "url": "https://resources.finalsite.net/images/v1786047938/argyleisdcom/gg3wgliimqruy10i6crd/CQD_LOCAL_Artificial_Intelligence.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy CQD(LOCAL) - Technology Resources: Artificial Intelligence (Houston Independent School District)",
        "url": "https://resources.finalsite.net/images/v1786979170/houstonisdorg/ocfp4xhanpjdqctfjwcd/CQD_LOCAL.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 8636 - Artificial Intelligence (Valley Central School District)",
        "url": "https://www.vcsd.k12.ny.us/board-of-education/policies/8636-artificial-intelligence/",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 8636 - Artificial Intelligence (Hyde Park Central School District)",
        "url": "https://resources.finalsite.net/images/v1785424270/dcbocesorg/wqneizmsczobgndczgvq/BOEPolicy86360-ArtificialIntelligence.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 8636 - Artificial Intelligence (Hudson City School District)",
        "url": "https://www.hudsoncsd.org/wp-content/uploads/2026/01/Policy-8636-AI.pdf",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 815.1 - Use of Generative Artificial Intelligence in Education (Quaker Valley School District)",
        "url": "https://go.boarddocs.com/pa/qvsd/Board.nsf/pfiles/DXSQEX690146/$file/815.1%20%20Use%20of%20Generative%20Artificial%20Intelligence%20in%20Education%202nd.pdf",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 815.1 - Artificial Intelligence (Hempfield School District)",
        "url": "https://resources.finalsite.net/images/v1752586297/hempfieldsdorg/ufvcxsifr3kspwgnnknm/Policy_8151_Artificial_Intelligence.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Quincy School District)",
        "url": "https://www.qsd.wednet.edu/departments/technology/artificial-intelligence",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Peninsula School District)",
        "url": "https://www.psd401.net/ai",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI in FCS (Forsyth County Schools)",
        "url": "https://www.forsyth.k12.ga.us/district-services/technology-information-services/educational-technology-and-media/fcsai",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence - Approved Tools (Ben Hill County Schools)",
        "url": "https://www.ben-hill.k12.ga.us/school-specific-resources/artificial-intelligence",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "guidance",
        "title": "Administrative Guidelines Regarding Internet Acceptable Use (Artificial Intelligence) (Cherokee County School District)",
        "url": "https://resources.finalsite.net/images/v1753482957/cherokeek12net/zmgieuc1sfgh9xmwyy4l/ArtificialIntelligenceAIGuidelines.pdf",
    },
    {
        "state": "Georgia",
        "level": "district",
        "doc_type": "guidance",
        "title": "Parents and Community AI Guidance (Clayton County Public Schools)",
        "url": "https://www.clayton.k12.ga.us/about/artificial-intelligence-position-statement/parents-and-community-ai-guidance",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "AI Guide for Students (Hingham Public Schools)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/4900/Hps/85542e0f-dc91-4842-bec4-34c4b8f933d0/--_Hingham_Public_Schools_AI_Guide__Student_.pdf?disposition=inline",
    },
    {
        "state": "Louisiana",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy EFAB - Employee and Student Acceptable Use Policy for Artificial Intelligence (Ouachita Parish School Board)",
        "url": "https://resources.finalsite.net/images/v1772042917/opsbnet/iddnjyg0jsztduhlgb3g/EFAB-26hl.pdf",
    },
    {
        "state": "Oklahoma",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI Tools (Stillwater Public Schools)",
        "url": "https://www.stillwaterschools.com/academics/ai",
    },
    {
        "state": "Oklahoma",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy 3142 - AI & Emerging Technology (Bixby Public Schools)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/615/Bixby_Public_Schools/f5aaed8e-8033-49eb-ba94-6b2b0b2dd9cc/3142--AI-%26-Emerging-Technology.pdf?disposition=inline",
    },
    {
        "state": "Oklahoma",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Mustang Public Schools)",
        "url": "https://www.mustangps.org/departments/technology/artificial-intelligence",
    },
    {
        "state": "Alabama",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI (Artificial Intelligence) Guidelines (Dothan City Schools)",
        "url": "https://resources.finalsite.net/images/v1786037740/dothank12alus/rdjg8mwvjhssqim659nc/GArtificialIntelligenceAIGuidelines.pdf",
    },
    {
        "state": "Kentucky",
        "level": "district",
        "doc_type": "resource_page",
        "title": "DCPS Tech Help - AI (Daviess County Public Schools)",
        "url": "https://sites.google.com/daviess.kyschools.us/dcps-it/more/ai",
    },
    # --- States added from the 2026 AI Index private-investment map ---
    {
        "state": "Colorado",
        "level": "state",
        "doc_type": "guidance",
        "title": "Colorado Roadmap for AI in K-12 Education (Colorado Education Initiative with CDE)",
        "url": "https://www.coloradoedinitiative.org/wp-content/uploads/2024/08/Colorado-Roadmap-for-AI-in-K-12-Education_August-2024.pdf",
    },
    {
        "state": "Colorado",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Colorado Department of Education)",
        "url": "https://ed.cde.state.co.us/artificialintelligence",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI Guidance for Students (Jeffco Public Schools)",
        "url": "https://www.jeffcopublicschools.org/services/technology/artificial-intelligence/ai-guidance-for-students",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Jeffco Public Schools)",
        "url": "https://www.jeffcopublicschools.org/services/technology/artificial-intelligence",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence (AI) Guidance (Cherry Creek School District)",
        "url": "https://www.cherrycreekschools.org/programs-and-services/information-systems/ai-guidance",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (Douglas County School District)",
        "url": "https://www.dcsdk12.org/schools-academics/academics/digital-literacy/artificial-intelligence-ai",
    },
    {
        # FLDOE has no downloadable AI guidance; this is the UF-led statewide task force.
        "state": "Florida",
        "level": "state",
        "doc_type": "task_force_or_report",
        "title": "Florida K-12 AI Education Task Force - Introduction (CS Everyone Center, University of Florida)",
        "url": "https://fl-aitaskforce.org/introduction/",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence - District Guidance Hub (Orange County Public Schools)",
        "url": "https://www.ocps.net/ai",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Broward Powered by AI (Broward County Public Schools)",
        "url": "https://browardschools.ai/",
    },
    {
        "state": "Virginia",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidelines for AI Integration Throughout Education in the Commonwealth of Virginia (Office of the Secretary of Education)",
        "url": "https://www.education.virginia.gov/media/governorvirginiagov/secretary-of-education/pdf/AI-Education-Guidelines.pdf",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance for FCPS Faculty and Staff (Fairfax County Public Schools)",
        "url": "https://www.fcps.edu/artificial-intelligence-guidance-fcps-faculty-and-staff",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "FCPS Student Guide: Artificial Intelligence (Fairfax County Public Schools)",
        "url": "https://tjhsst.fcps.edu/sites/default/files/media/inline-files/FCPS%20Student%20AI%20Guide.pdf",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 5430 - Use of Generative Artificial Intelligence (Loudoun County Public Schools)",
        "url": "https://go.boarddocs.com/vsba/loudoun/Board.nsf/files/DGANMV5F933D/$file/Policy%205430%20May%207%2C%202025%20C%26I%20(clean%20copy).pdf",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI Use: Policies and Guidance (Virginia Beach City Public Schools)",
        "url": "https://www.vbschools.com/academics/digitalliteracy/ai-use-policies-and-guidance",
    },
    {
        "state": "Delaware",
        "level": "state",
        "doc_type": "guidance",
        "title": "Generative AI in Delaware Education (Delaware Department of Education)",
        "url": "https://education.delaware.gov/wp-content/uploads/2026/03/delaware_generative_ai_DE_guidance.pdf",
    },
    {
        "state": "Delaware",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Generative AI in the Classroom (Christina School District Technology Hub)",
        "url": "https://sites.google.com/christina.k12.de.us/csdinstructionaltechnologyhub/staff/ai-in-the-classroom",
    },
    {
        "state": "South Carolina",
        "level": "state",
        "doc_type": "guidance",
        "title": "South Carolina Artificial Intelligence (AI) Standards Framework (SC Department of Education; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/South%20Carolina/SC-AI-Framework.pdf",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "policy",
        "title": "Regulation 6325 - Artificial Intelligence (Richland School District One)",
        "url": "https://support.scr1.org/policiesregulations/policy-6325-artificial-intelligence/",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Generative AI (Charleston County School District)",
        "url": "https://www.ccsdschools.com/academics/artificial-intelligence-ai",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy IA - Instructional Program incl. Artificial Intelligence (Greenville County Schools)",
        "url": "https://greenville-sc.community.highbond.com/document/26925a4b-5a13-4d96-bd58-06e88de85e04/",
    },
    {
        "state": "North Dakota",
        "level": "state",
        "doc_type": "guidance",
        "title": "North Dakota K-12 AI Guidance Framework (ND Department of Public Instruction)",
        "url": "https://www.nd.gov/dpi/policyguidelines/north-dakota-k-12-ai-guidance-framework",
    },
    {
        "state": "North Dakota",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI in Education (Fargo Public Schools)",
        "url": "https://www.fargo.k12.nd.us/departments/technology/ai",
    },
    {
        # PED's site returns 403 to scripts; this is a mirror of the signed PDF.
        "state": "New Mexico",
        "level": "state",
        "doc_type": "guidance",
        "title": "New Mexico K-12 Education AI Guidance 1.0 (NM Public Education Department; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/New%20Mexico/NM-AI-Guidance-Signed-2025-04-29.pdf",
    },
    {
        "state": "Arkansas",
        "level": "state",
        "doc_type": "guidance",
        "title": "Planning Guide for AI: A Framework for School Districts (Virtual Arkansas)",
        "url": "https://virtualarkansas.org/wp-content/uploads/2024/02/ai_planning_guide_-_vlla-virtualarkansas-official-111023.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Bentonville Schools AI Guide (Bentonville Schools)",
        "url": "https://resources.finalsite.net/images/v1786046632/bentonvillek12org2/qapnhudwoo6q0futi5mh/BentonvilleSchoolsAIGuide1.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI Teacher Standards & Expectations (Bentonville Schools)",
        "url": "https://resources.finalsite.net/images/v1786049744/bentonvillek12org2/c4culwum8l5vrn0swbfx/AIGuidelinesforTeachers.pdf",
    },
    {
        "state": "Arkansas",
        "level": "state",
        "doc_type": "guidance",
        "title": "2026-2027 Student Guidelines for Using AI (Virtual Arkansas)",
        "url": "https://virtualarkansas.org/wp-content/uploads/2026/03/2026-2027-Virtual-Arkansas-Student-Guidelines-for-Using-AI.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 5.10 - Artificial Intelligence (Cutter Morning Star School District)",
        "url": "https://www.eaglesnest.dsc.k12.ar.us/media/website_pages/about-our-district/state-required-documents/documents/school-district-policies/written-policies/2025-2026/section-5-curriculum-25-26/5.10_ARTIFICIAL_INTELLIGENCE.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 3.58 - Licensed Personnel Use of Artificial Intelligence (Cutter Morning Star School District)",
        "url": "https://www.eaglesnest.dsc.k12.ar.us/media/website_pages/about-our-district/state-required-documents/documents/school-district-policies/written-policies/2025-2026/section-3-licensed-personnel-25-26/3.58-LICENSED-PERSONNEL-USE-OF-ARTIFICIAL-INTELLIGENCE.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 5.10 - Artificial Intelligence (Nemo Vista School District)",
        "url": "https://socs.nemo.k12.ar.us/vimages/shared/vnews/stories/55ca674221f96/5.10%E2%80%94ARTIFICIAL%20INTELLIGENCE.pdf",
    },
    {
        "state": "Arkansas",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 4.64 - Student Use of Artificial Intelligence (Nemo Vista School District)",
        "url": "https://socs.nemo.k12.ar.us/vimages/shared/vnews/stories/55ca674221f96/4.64%20--%20STUDENT%20USE%20OF%20ARTIFICIAL%20INTELLIGENCE.pdf",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (AI) (York School District One)",
        "url": "https://www.york.k12.sc.us/departments/instruction/artificial-intelligence-ai",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy IJNDC - Artificial Intelligence Responsible Use (York School District One)",
        "url": "https://go.boarddocs.com/sc/ysd1/Board.nsf/pfiles/DWMS25702289/$file/Policy%20IJNDC%20Artificial%20Intelligence%20Responsible%20Use%20(1).pdf",
    },
    {
        "state": "South Carolina",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Generative AI Guidelines 2026-2027 (Spartanburg School District Four)",
        "url": "https://resources.finalsite.net/images/v1785264369/spartanburg4org/qlobnuf6zi9wssexiduz/GenerativeAIGuidelines-SCSD4.pdf",
    },
    {
        "state": "Wyoming",
        "level": "state",
        "doc_type": "model_policy",
        "title": "Model Policy: K-12 Artificial Intelligence in Education Transparency Act (submitted to Wyoming Legislature interim committee, 2026)",
        "url": "https://wyoleg.gov/InterimCommittee/2026/SSR-2026082511-03_state_model_policy1.pdf",
    },
    {
        "state": "Kentucky",
        "level": "state",
        "doc_type": "resource_page",
        "title": "AI in Action Across Kentucky (Kentucky Department of Education)",
        "url": "https://www.education.ky.gov/districts/tech/Documents/AIKentucky.pdf",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy 0441 - Artificial Intelligence (Jefferson School District)",
        "url": "https://resources.finalsite.net/images/v1771450230/jeffersonschooldistrictcom/x6muxdfghnlfc3co6sa6/0441BPArtificialIntelligence-20250812_1.pdf",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "policy",
        "title": "Board Policy 0441 - Artificial Intelligence (Oxnard Union High School District)",
        "url": "https://resources.finalsite.net/images/v1784757762/oxnardunionorg/ivv6iy6zswvdigoxvtfg/BP-0441-Artificial-Intelligence.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 8636 - Artificial Intelligence (Elwood Union Free School District)",
        "url": "https://resources.finalsite.net/images/v1770651475/elwoodk12nyus/jtqqoi1yba5eqxahtxy0/8636_ARTIFICIAL_INTELLIGENCE.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 8636 - Artificial Intelligence (Edgemont Union Free School District)",
        "url": "https://go.boarddocs.com/ny/edgemont/Board.nsf/files/DRMNAQ5EBC7D/$file/8636%20-%20AI%20Policy.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "Policy 8636 - Artificial Intelligence, for update (Guilderland Central School District)",
        "url": "https://guilderlandschools.community.highbond.com/document/7f1b0b2e-ef81-4c74-95f6-329434803372/",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "PSJA ISD AI Guidebook (Pharr-San Juan-Alamo Independent School District)",
        "url": "https://www.psjaisd.us/academics/psja-isd-ai-guidebook",
    },
    {
        "state": "Louisiana",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy IFBGB - Employee and Student Acceptable Use Policy for Artificial Intelligence (Ascension Parish School Board)",
        "url": "https://go.boarddocs.com/la/apsb/Board.nsf/files/DS2SNZ7391F2/$file/IFBGB%20-%20EMPLOYEE%20AND%20STUDENT%20ACCEPTABLE%20USE%20POLICY%20FOR%20ARTIFICIAL%20INTELLIGENCE%20-%20NEW%20POLICY.pdf",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "policy",
        "title": "Administrative Regulation 0441 - Artificial Intelligence (Oxnard Union High School District)",
        "url": "https://resources.finalsite.net/images/v1784757802/oxnardunionorg/pdwqjiji7d4b5ze4cp8t/AR-0441-Artificial-Intelligence.pdf",
    },
    {
        "state": "California",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "Board Policy 0441 - Artificial Intelligence, draft (Carlsbad Unified School District)",
        "url": "https://go.boarddocs.com/ca/cusd/Board.nsf/files/DQ2VU58261B3/$file/01-21-26%20-%20Exhibit%20B%20-%20BP%200441%20Artificial%20Intelligence%20(Draft).pdf",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 815.1 - Artificial Intelligence (Pottsgrove School District)",
        "url": "https://resources.finalsite.net/images/v1733776523/pgsdorg/qpnjigouqpwzfr9wrggp/Policy8151ArtificialIntelligence.pdf",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "policy",
        "title": "Regulation GBEE-R2 - Staff Use of Artificial Intelligence (27J Schools)",
        "url": "https://www.sd27j.org/policy-details/~board/district-policies/post/staff-use-of-artificial-intelligence-ai-gbee-r2",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy IJNDA - Artificial Intelligence Instruction (27J Schools)",
        "url": "https://www.sd27j.org/policy-details/~board/district-policies/post/artificial-intelligence-instruction-ijnda",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "policy",
        "title": "Academic Honesty & AI (Poudre High School, Poudre School District)",
        "url": "https://phs.psdschools.org/our-school/academic-honesty-ai",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "position_statement",
        "title": "AI Shared Understandings (Academy District 20)",
        "url": "https://www.asd20.org/educational-technology/artificial-intelligence/",
    },
    {
        "state": "Colorado",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "AI Quick Start Guide (Academy District 20)",
        "url": "https://www.asd20.org/educational-technology/artificial-intelligence/ai-quick-start-guide/",
    },
    {
        "state": "Georgia",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence for Educators Guidance v1 (Georgia Professional Standards Commission)",
        "url": "https://www.gapsc.com/EducatorPreparation/Resources/Downloads/AI_for_Educators_Guidance_V1_June_2026.pdf",
    },
    {
        "state": "Georgia",
        "level": "state",
        "doc_type": "guidance",
        "title": "Ethical Considerations in the Appropriate Use of AI for Educators (Georgia Professional Standards Commission)",
        "url": "https://www.gapsc.com/Ethics/Downloads/GaPSC%20Ethical%20Considerations%20in%20the%20Appropriate%20Use%20of%20AI%20for%20Educators_6-16-25.pdf",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 7540.08 - Artificial Intelligence (AI) (Collier County Public Schools)",
        "url": "https://go.boarddocs.com/fl/collier/Board.nsf/files/DA6JZ84F8E5D/$file/po7540.08%20Artificial%20Intelligence%20(AI).pdf",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "CCPS Artificial Intelligence Handbook (Collier County Public Schools)",
        "url": "https://resources.finalsite.net/images/v1785250502/collierschoolscom/mvluynxmlqyr1drbmkiz/AIHandbook.pdf",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "Policy 7540.08 - Artificial Intelligence (AI), board pre-briefing draft (School District of Lee County)",
        "url": "https://go.boarddocs.com/fl/lee/Board.nsf/files/D8KUMR7C2B05/$file/7540.08%20-%C2%A0Artificial%20Intelligence%20(AI).pdf",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "Policy 7540.08 - Artificial Intelligence (AI), proposed (Highlands County School District)",
        "url": "https://go.boarddocs.com/fl/highlfl/Board.nsf/files/DFXK2W4FC3D6/$file/7540.08%20-%20Artificial%20Intelligence%20(AI).pdf",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "Policy 7540.08 - Artificial Intelligence (AI), proposed (Seminole County Public Schools)",
        "url": "https://scpsfl.community.highbond.com/document/b10aa7bb-ad8b-4455-9964-2510b61b47b8/",
    },
    {
        "state": "Florida",
        "level": "district",
        "doc_type": "guidance",
        "title": "Student Use of Artificial Intelligence in the Classroom: Guidelines (Brevard Public Schools)",
        "url": "https://agenda.brevardschools.org/content/files/artifact-2-ai-acceptable-use.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence in Celina ISD (Celina Independent School District)",
        "url": "https://www.celinaisd.com/our-departments/technology/ai-in-celina-isd",
    },
    {
        "state": "Texas",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Generative AI in Education (Plano Independent School District)",
        "url": "https://www.pisd.edu/departments-66/instructional-technology/technology-resources/generative-ai-in-education",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "draft_policy",
        "title": "New Policy - Artificial Intelligence, policy committee review (Richmond Public Schools)",
        "url": "https://go.boarddocs.com/vsba/richmond/Board.nsf/files/DS5Q2U673DEE/$file/NEW%20Policy%20-%20Artificial%20Intelligence.pdf",
    },
    {
        "state": "Virginia",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy II-GF - Use of Artificial Intelligence (Falls Church City Public Schools)",
        "url": "https://go.boarddocs.com/vsba/fccpsva/Board.nsf/files/DVBN8V5EBEE7/$file/II-GF%20-%20USE%20OF%20ARTIFICIAL%20INTELLIGENCE.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 2023F2 - Artificial Intelligence Classroom Protocol (La Conner School District)",
        "url": "https://go.boarddocs.com/wa/laconner/Board.nsf/files/DG3R4D6C279E/$file/Policy%202023F2-%20Form%20Artificial%20Intelligence%20Classroom%20Protocol.pdf",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "guidance",
        "title": "Your Guide to AI (Holliston Public Schools)",
        "url": "https://www.holliston.k12.ma.us/district-departments/technology/ai/ai-guidance",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "doc_type": "guidance",
        "title": "Guidance on the Use of Artificial Intelligence in BPS (Boston Public Schools)",
        "url": "https://bostonpublicschools.helpdocs.io/article/7nvt595hpb-guidance-on-the-use-of-artificial-intelligence-in-bps",
    },
    # --- Remaining states on the 2026 AI Index investment map ---
    {
        "state": "Alaska",
        "level": "state",
        "doc_type": "guidance",
        "title": "Alaska K-12 Artificial Intelligence Framework (Alaska Department of Education & Early Development)",
        "url": "https://education.alaska.gov/State_Board/october-2025/9.1_Alaska%20K12%20AI%20Framework_final_v2.pdf",
    },
    {
        "state": "Arizona",
        "level": "state",
        "doc_type": "guidance",
        "title": "Arizona Generative AI Guidance v26.01 (Arizona Institute for Education and the Economy / NAU)",
        "url": "https://in.nau.edu/college-education/wp-content/uploads/sites/359/2025/05/AZ-GenAI-Guidance-v26.01.pdf",
    },
    {
        "state": "Connecticut",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Connecticut Commission for Educational Technology)",
        "url": "https://portal.ct.gov/das/ctedtech/commission-for-educational-technology/initiatives/artificial-intelligence?language=en_US",
    },
    {
        "state": "Connecticut",
        "level": "state",
        "doc_type": "task_force_or_report",
        "title": "Policy Recommendations 2025 (Connecticut Commission for Educational Technology)",
        "url": "https://portal.ct.gov/das/-/media/das/ctedtech/publications/2025/cet_policy_recs-2025.pdf",
    },
    {
        "state": "District of Columbia",
        "level": "state",
        "doc_type": "model_policy",
        "title": "LEA AI Model Policy Booklet (Office of the State Superintendent of Education)",
        "url": "https://osse.dc.gov/sites/default/files/dc/sites/osse/page_content/attachments/LEA%20AI%20Model%20Policy%20Booklet%20Sept%202026.pdf",
    },
    {
        "state": "Hawaii",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Hawaii State Department of Education)",
        "url": "https://hawaiipublicschools.org/student-programs/artificial-intelligence/",
    },
    {
        "state": "Idaho",
        "level": "state",
        "doc_type": "guidance",
        "title": "Generative Artificial Intelligence in Education Framework (Idaho State Department of Education)",
        "url": "https://www.sde.idaho.gov/wp-content/uploads/2026/08/Generative-Artificial-Intelligence-in-Education-Framework.pdf",
    },
    {
        "state": "Illinois",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidance on Artificial Intelligence (Illinois State Board of Education)",
        "url": "https://www.isbe.net/Documents/AIGuidance.pdf",
    },
    {
        "state": "Illinois",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "CPS AI Guidebook (Chicago Public Schools)",
        "url": "https://www.cps.edu/globalassets/cps-pages/initiatives/ai-guidebook/cps-ai-guidebook.pdf",
    },
    {
        "state": "Illinois",
        "level": "district",
        "doc_type": "guidance",
        "title": "Generative AI (Naperville Community Unit School District 203)",
        "url": "https://www.naperville203.org/departments-services/learning-services/edtech/generative-ai",
    },
    {
        "state": "Indiana",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Digital Learning incl. AI (Indiana Department of Education)",
        "url": "https://www.in.gov/doe/educators/digital-learning/",
    },
    {
        "state": "Indiana",
        "level": "state",
        "doc_type": "guidance",
        "title": "Indiana AI Guidance (Indiana Department of Education; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Indiana/Indiana-AI-Guidance.pdf",
    },
    {
        "state": "Indiana",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI in CCS (Carmel Clay Schools)",
        "url": "https://www.ccs.k12.in.us/services/technology-data-solutions/ai-in-ccs",
    },
    {
        "state": "Iowa",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI Guidance (Iowa Department of Education)",
        "url": "https://educate.iowa.gov/media/9860/download",
    },
    {
        "state": "Iowa",
        "level": "district",
        "doc_type": "guidance",
        "title": "Generative AI Guidelines (Iowa City Community School District)",
        "url": "https://www.iowacityschools.org/academics-programs/curriculum-areas/instructional-technology/generative-ai-guidelines",
    },
    {
        "state": "Iowa",
        "level": "district",
        "doc_type": "policy",
        "title": "Regulation 6058R1 - Artificial Intelligence in the Education Environment (Iowa City Community School District)",
        "url": "https://www.iowacityschools.org/our-district/school-board/board-policies/board-policies-details/~board/board-policies/post/6058r1-artificial-intelligence-in-the-education-environment-regulation",
    },
    {
        "state": "Kansas",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance (Kansas City Kansas Public Schools)",
        "url": "https://www.kckschools.org/academics/artificial-intelligence-guidance",
    },
    {
        "state": "Maine",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Technology Guidance incl. AI Toolkit (Maine Department of Education)",
        "url": "https://www.maine.gov/doe/learning/technology/guidance",
    },
    {
        "state": "Maryland",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance (Maryland State Department of Education; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Maryland/MSDE-AI-Guidance-A.pdf",
    },
    {
        "state": "Maryland",
        "level": "state",
        "doc_type": "policy",
        "title": "Artificial Intelligence Policy (Maryland State Board of Education; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Maryland/MSDE-AI-Policy-A.pdf",
    },
    {
        "state": "Michigan",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Michigan Department of Education)",
        "url": "https://www.michigan.gov/mde/services/academic-standards/educational-technology/artificial-intelligence",
    },
    {
        "state": "Michigan",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI Integration Framework (Michigan Virtual; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Michigan/MichiganVirtual-AI-Integration-Framework.pdf",
    },
    {
        "state": "Michigan",
        "level": "district",
        "doc_type": "position_statement",
        "title": "AI Bill of Rights (Ann Arbor Public Schools)",
        "url": "https://www.ai4mi.org/resource/ann-arbor-public-schools-ai-bill-of-rights",
    },
    {
        "state": "Minnesota",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence in Education (Minnesota Department of Education; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Minnesota/MDE-AI-in-Education.pdf",
    },
    {
        "state": "Minnesota",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI (Minneapolis Public Schools)",
        "url": "https://www.mpschools.org/the-source/apps-software/ai",
    },
    {
        "state": "Missouri",
        "level": "state",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance for Local Education Agencies (Missouri DESE; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Missouri/DESE-AI-Guidance.pdf",
    },
    {
        "state": "Missouri",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "AI Handbook (Springfield Public Schools)",
        "url": "https://www.sps.org/students-families/resources/handbook/ai-handbook",
    },
    {
        "state": "Montana",
        "level": "state",
        "doc_type": "guidance",
        "title": "Montana Artificial Intelligence in K-12 Education Guidelines (Office of Public Instruction)",
        "url": "https://opi.mt.gov/Portals/182/Page%20Files/Homepage/Docs/Montana%20Artificial%20Intelligence%20in%20K12%20Education%20Guidelines.pdf?ver=2025-10-14-134920-167",
    },
    {
        "state": "Nebraska",
        "level": "district",
        "doc_type": "policy",
        "title": "AI Protocol (Lincoln Public Schools)",
        "url": "https://resources.finalsite.net/images/v1783953041/lincolnpsorg/gyydzjniwlvz7mtglsdk/AIProtocol.pdf",
    },
    {
        "state": "Nevada",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI in Schools (Nevada Department of Education)",
        "url": "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/uploads/15_ai_in_schools_42862dfb21.pdf",
    },
    {
        "state": "Nevada",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI - Artificial Intelligence (Washoe County School District)",
        "url": "https://www.washoeschools.net/directory/ai-artificial-intelligence",
    },
    {
        "state": "Nevada",
        "level": "district",
        "doc_type": "policy",
        "title": "Administrative Regulation 7212 - Artificial Intelligence and Digital Learning (Washoe County School District)",
        "url": "https://new.washoecountyschools.org/policyandregs/pdf_files/administrative_regulations/7212%20Reg%20-%20Artificial%20Intelligence%20and%20Digital%20Learning_Version%201.1_Final%20(1).pdf",
    },
    {
        "state": "New Hampshire",
        "level": "state",
        "doc_type": "guidance",
        "title": "PreK-12 Generative AI Guidance Framework for NH Schools (NH Learning Initiative)",
        "url": "https://nhlearninginitiative.org/wp-content/uploads/2025/06/NH-AI-Guidance-Framework-FINAL-DRAFT6.4.25.pdf",
    },
    {
        "state": "New Hampshire",
        "level": "district",
        "doc_type": "policy",
        "title": "Policy 766 - Use of Artificial Intelligence in Schools (Manchester School District)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/3235/Msd/34880b77-ca65-4a64-9ca3-788152082467/Instruction_766-Use-of-Artificial-Intelligence-in-Schools.pdf?disposition=inline",
    },
    {
        "state": "New Hampshire",
        "level": "district",
        "doc_type": "policy",
        "title": "Procedure 766-R - Responsible Implementation and Use of Artificial Intelligence in Schools (Manchester School District)",
        "url": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/3235/Msd/8737e36a-0837-4952-8e69-686d25f65d7d/Instruction_766-R-Procedure-for-the-Responsible-Implementation-and-Use-of-Artificial-Intelligence-in-Schools.pdf?disposition=inline",
    },
    {
        "state": "New Jersey",
        "level": "state",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence in Education (New Jersey Department of Education)",
        "url": "https://www.nj.gov/education/innovation/ai/",
    },
    {
        "state": "New Jersey",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI Implementation Plan 2026 (Cherry Hill Public Schools)",
        "url": "https://resources.finalsite.net/images/v1787864342/cherryhillk12njus/axsg9dqbhycqizds8vgw/AIImplementationPlan2026MasterUpdated-Parents82426.pdf",
    },
    {
        "state": "North Carolina",
        "level": "state",
        "doc_type": "resource_page",
        "title": "AI Resources (NC Department of Public Instruction)",
        "url": "https://www.dpi.nc.gov/districts-schools/districts-schools-support/digital-learning-school-connectivity/ai-resources",
    },
    {
        "state": "North Carolina",
        "level": "state",
        "doc_type": "guidance",
        "title": "Generative AI Implementation Recommendations and Considerations for PK-13 Public Schools (NC DPI; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/North%20Carolina/NCDPI-GenAI-Recommendations-livingdoc.pdf",
    },
    {
        "state": "North Carolina",
        "level": "district",
        "doc_type": "guidance",
        "title": "Generative AI Guidance 2025-26 (Charlotte-Mecklenburg Schools)",
        "url": "https://resources.finalsite.net/images/v1755644634/cmsk12ncus/c0hjknh9dsvia3ca0bic/CMSGenerativeAIGuidance2025-26Public.pdf",
    },
    {
        "state": "North Carolina",
        "level": "district",
        "doc_type": "policy",
        "title": "AI Policy Release (Charlotte-Mecklenburg Schools)",
        "url": "https://resources.finalsite.net/images/v1761743644/cmsk12ncus/cuzpa7rr3eyabailheow/AIPolicyRelease.pdf",
    },
    {
        "state": "North Carolina",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Charlotte-Mecklenburg Schools)",
        "url": "https://www.cmsk12.org/technology-services/artificial-intelligence",
    },
    {
        "state": "Ohio",
        "level": "state",
        "doc_type": "model_policy",
        "title": "AI Model Policy (Ohio Department of Education and Workforce)",
        "url": "https://education.ohio.gov/Topics/AI-in-Ohio-s-Education/Model-Policy",
    },
    {
        "state": "Ohio",
        "level": "state",
        "doc_type": "resource_page",
        "title": "AI in Ohio's Education (Ohio Department of Education and Workforce)",
        "url": "https://education.ohio.gov/Topics/AI-in-Ohio-s-Education",
    },
    {
        "state": "Ohio",
        "level": "district",
        "doc_type": "policy",
        "title": "Artificial Intelligence Policy (Hilliard City Schools)",
        "url": "https://www.hilliardschools.org/artificial-intelligence-policy/",
    },
    {
        "state": "Oregon",
        "level": "state",
        "doc_type": "guidance",
        "title": "Generative Artificial Intelligence (AI) for K-12 Schools (Oregon Department of Education)",
        "url": "https://www.oregon.gov/ode/educator-resources/teachingcontent/Pages/Generative-Artificial-Intelligence-(AI)-for-K-12-Schools.aspx",
    },
    {
        "state": "Oregon",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence in PPS (Portland Public Schools)",
        "url": "https://www.pps.net/departments/office-of-teaching-learning/artificial-intelligence-in-pps",
    },
    {
        "state": "Oregon",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "AI Guidebook (Portland Public Schools)",
        "url": "https://www.pps.net/departments/office-of-teaching-learning/artificial-intelligence-in-pps/ai-guidebook",
    },
    {
        "state": "Oregon",
        "level": "district",
        "doc_type": "guidance",
        "title": "Generative AI Responsible Use Guidelines (Beaverton School District)",
        "url": "https://www.beaverton.k12.or.us/departments/teaching-learning/curriculum-instruction-assessment/generative-ai-responsible-use-guidelines",
    },
    {
        "state": "Rhode Island",
        "level": "state",
        "doc_type": "guidance",
        "title": "Guidance on the Responsible Use of Artificial Intelligence in Schools (Rhode Island Department of Education)",
        "url": "https://ride.ri.gov/sites/g/files/xkgbur806/files/2025-12/RIDE%20AI%20Guidance%208.15.25.pdf",
    },
    {
        "state": "Rhode Island",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Barrington Public Schools)",
        "url": "https://barringtonschools.net/apps/pages/index.jsp?uREC_ID=628846&type=d&pREC_ID=1205172",
    },
    {
        "state": "Tennessee",
        "level": "state",
        "doc_type": "model_policy",
        "title": "Model Policy 4.214 - Artificial Intelligence (Tennessee School Boards Association; copy hosted by state-ai-policy-field-guide)",
        "url": "https://raw.githubusercontent.com/ai-education-research/state-ai-policy-field-guide/main/resources/Tennessee/TSBA-Model-Policy-4.214.pdf",
    },
    {
        "state": "Tennessee",
        "level": "district",
        "doc_type": "resource_page",
        "title": "Artificial Intelligence (Metro Nashville Public Schools)",
        "url": "https://www.mnps.org/departments/technology/artificial-intelligence",
    },
    {
        "state": "Tennessee",
        "level": "district",
        "doc_type": "policy",
        "title": "AI Procedure (Metro Nashville Public Schools)",
        "url": "https://mnpsutilities.mnps.org/Public/Procedures/Download/418",
    },
    {
        "state": "Utah",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI Framework (Utah State Board of Education)",
        "url": "https://schools.utah.gov/informationtechnology/artificialintelligence/_artificialintelligence/AIFramework.pdf",
    },
    {
        "state": "Utah",
        "level": "district",
        "doc_type": "guidebook_or_handbook",
        "title": "Canyons VIEW of Artificial Intelligence: A Guidebook (Canyons School District)",
        "url": "https://www.canyonsdistrict.org/wp-content/uploads/2023/09/Canyons-VIEW-of-Artificial-Intelligence-A-Guidebook.pdf",
    },
    {
        "state": "Utah",
        "level": "district",
        "doc_type": "resource_page",
        "title": "AI (Canyons School District)",
        "url": "https://www.canyonsdistrict.org/ai/",
    },
    {
        "state": "Vermont",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI Guidance for Education (Vermont Agency of Education)",
        "url": "https://education.vermont.gov/sites/aoe/files/documents/edu-aoe-ai-guidance-for-education.pdf",
    },
    {
        "state": "Wisconsin",
        "level": "state",
        "doc_type": "guidance",
        "title": "AI Guidance for Schools (Wisconsin Department of Public Instruction)",
        "url": "https://dpi.wi.gov/media/55067/download?inline",
    },
    {
        "state": "Wisconsin",
        "level": "district",
        "doc_type": "guidance",
        "title": "AI K-12 Guidelines (Appleton Area School District)",
        "url": "https://www.aasd.k12.wi.us/families/education-resources/ai-k-12-guidelines",
    },
    {
        # Google Docs plain-text export; the /edit link only returns a JS app shell.
        "state": "South Dakota",
        "level": "district",
        "doc_type": "guidance",
        "title": "Artificial Intelligence Guidance, May 2026 (Sioux Falls School District)",
        "url": "https://docs.google.com/document/d/13MuS7a5x0-85pPCGAhKsYQ-amOzIiEs6AYjbbXWj96I/export?format=txt",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def is_pdf(url: str, content_type: str) -> bool:
    return url.lower().endswith(".pdf") or "application/pdf" in content_type.lower()


def looks_unspaced(text: str) -> bool:
    words = text.split()
    if len(words) < 20:
        return False
    return sum(1 for w in words if len(w) > 25) / len(words) > 0.03


def extract_pdf_text(raw: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            # Tightly kerned PDFs merge words at the default tolerance.
            if looks_unspaced(page_text):
                page_text = page.extract_text(x_tolerance=1.5) or page_text
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_docx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in document.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)


BOILERPLATE_ID_CLASS = re.compile(r"(?:^|[-_\s])(?:nav|navbar|header|footer|menu|breadcrumbs?|sidebar|alert|skip)(?:$|[-_\s])", re.I)


def extract_html_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        tag.decompose()
    # Many district CMSs use <div id="header-wrapper"> etc. instead of semantic tags.
    boilerplate = [
        tag for tag in soup.find_all(True)
        if tag.name not in ("html", "body", "main", "article")
        and BOILERPLATE_ID_CLASS.search(" ".join([tag.get("id") or ""] + list(tag.get("class") or [])))
    ]
    for tag in boilerplate:
        if not tag.decomposed:
            tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n")
    return text


def repair_dropped_ligatures(rows: list[dict]) -> None:
    # Some PDFs export fi/ff/fl ligature glyphs as NUL ("Arti\x00cial"); pick the
    # ligature that yields the word most common elsewhere in the corpus.
    vocab = Counter(
        word.lower()
        for row in rows
        for word in re.findall(r"[A-Za-z]+", row["full_text"])
    )

    def fix(match: re.Match) -> str:
        word = match.group(0)
        candidates = [word.replace("\x00", lig) for lig in ("fi", "ff", "fl", "ffi", "ffl")]
        return max(candidates, key=lambda c: vocab[c.lower()])

    for row in rows:
        if "\x00" in row["full_text"]:
            row["full_text"] = re.sub(r"[A-Za-z]*\x00[A-Za-z\x00]*", fix, row["full_text"])
            row["char_count"] = len(row["full_text"])


def clean_text(text: str) -> str:
    # Keep the document's real line breaks (readable multi-line cells).
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    joined = "\n".join(lines)
    # Collapse letter-spaced cover titles ("A I G u i d e") back into words.
    joined = re.sub(
        r"(?<![A-Za-z])(?:[A-Za-z] ){2,}[A-Za-z](?![A-Za-z])",
        lambda m: m.group(0).replace(" ", ""),
        joined,
    )
    # Fullwidth commas/curly quotes so naive CSV viewers never mis-split full_text.
    joined = joined.replace(",", "\uff0c")
    return joined.replace('"', "\u201d")


def fetch_full_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if is_pdf(url, content_type):
        raw_text = extract_pdf_text(resp.content)
    elif url.lower().endswith(".docx") or "wordprocessingml.document" in content_type.lower():
        raw_text = extract_docx_text(resp.content)
    else:
        raw_text = extract_html_text(resp.content)
    return clean_text(raw_text)


def load_previous_rows(path: str) -> dict[str, dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return {
                row["source_url"]: row
                for row in csv.DictReader(f)
                if row.get("status", "").startswith("ok") and row.get("full_text")
            }
    except FileNotFoundError:
        return {}


def main() -> None:
    out_path = "k12_ai_policies.csv"
    singleline_path = "k12_ai_policies_singleline.csv"
    csv.field_size_limit(sys.maxsize)
    # Agency sites go down for maintenance; keep the last good copy rather than
    # dropping a document from the corpus.
    previous = load_previous_rows(out_path)
    rows = []
    for source in SOURCES:
        state = source["state"]
        level = source["level"]
        url = source["url"]
        retrieved = date.today().isoformat()
        print(f"Scraping {state} ({level}): {url}")
        try:
            full_text = fetch_full_text(url)
            status = "ok" if len(full_text) > 200 else "warning_short_text"
        except Exception as exc:
            print(f"  FAILED: {exc}")
            if url in previous:
                full_text = previous[url]["full_text"]
                retrieved = previous[url]["date_retrieved"]
                status = "ok_cached_previous_retrieval"
            else:
                full_text = ""
                status = f"error: {exc}"

        rows.append(
            {
                "state": state,
                "ai_private_investment_2025": format_investment(AI_INVESTMENT_2025[state]),
                "comparison_group": comparison_group(state),
                "level": level,
                "doc_type": source["doc_type"],
                "title": source["title"].replace(",", "\uff0c"),
                "source_url": url,
                "date_retrieved": retrieved,
                "status": status,
                "char_count": len(full_text),
                "full_text": full_text,
            }
        )
        print(f"  -> {len(full_text)} characters extracted ({status})")

    repair_dropped_ligatures(rows)
    rows.sort(key=lambda r: (
        GROUP_ORDER.index(r["comparison_group"]), r["state"], r["level"] != "state"
    ))

    fieldnames = [
        "state", "ai_private_investment_2025", "comparison_group", "level", "doc_type", "title", "source_url",
        "date_retrieved", "status", "char_count", "full_text",
    ]
    write_csv(out_path, rows, fieldnames)
    # Line-based CSV viewers (e.g. Rainbow CSV) need one record per physical line.
    flat_rows = [{**row, "full_text": re.sub(r"\s+", " ", row["full_text"]).strip()} for row in rows]
    write_csv(singleline_path, flat_rows, fieldnames)

    print(f"\nWrote {len(rows)} rows to {out_path} and {singleline_path}")


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    # BOM helps Excel detect UTF-8; QUOTE_ALL keeps every field unambiguous.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
