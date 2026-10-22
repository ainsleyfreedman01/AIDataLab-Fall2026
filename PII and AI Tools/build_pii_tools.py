"""Build the PII-definition and approved-AI-tool tables from the Privacy Passages PDFs.

Outputs (written next to this script):
  pii_and_tools_by_document.csv  one row per CSV row (205), PII items + tools by status
  pii_spectrum_by_organization.csv  one row per district / state, its documents merged
  pii_category_summary.csv       how many districts / state docs count each item as PII
  ai_tool_summary.csv            how many districts / state docs approve, restrict, or block each tool
  evidence.csv                   the quote behind every coded PII item and tool

PII items are found with patterns that only search text near PII / confidential /
"do not enter" language, then corrected by hand (PII_EXCLUDE / PII_ADD below).
Tool statuses were coded by hand from every passage that names a tool (TOOLS below).
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

HERE = Path(__file__).parent
REPO = HERE.parent
PASSAGES = REPO / "Privacy Passages"
csv.field_size_limit(10**9)

# ---------------------------------------------------------------- PII categories
# Text within ~450 characters after (150 before) one of these anchors is searched.
ANCHOR = re.compile(
    r"\bPII\b|\bPPI\b|\bPIT\b|personally[- ]identif|personal(ly)? (data|information|info|details|identif)"
    r"|identif(y|ying|iable|ied) (student )?(information|data|details)|sensitive (personal |student )?(data|information)"
    r"|confidential (student |district |employee )?(data|information|records)|protected (data|information|records)"
    r"|private (data|information)|student (data|information|identifiers)|prohibited information"
    r"|(do not|don.t|never|should not|must not|shall not|not to|avoid|prohibited from|refrain from) (\w+ ){0,3}"
    r"(enter|input|inputting|entering|share|sharing|upload|uploading|include|put|paste|disclos|submit|store|type)", re.I)

# key: (label, pattern)
CATS = {
    "name": ("Names", r"(?<![Uu]ser)(?<!file)(?<!district)(?<!tool)(?<!school)(?<!LEA)\s(student|full|first|last|real)?\s?names?\b(?! of (the )?(tool|district|LEA|school|AI|platform|app))|\bNames,"),
    "home_address": ("Home address", r"\b(home|physical|mailing|street|personal) address(es)?\b|(?<!email )(?<!e-mail )\baddresses\b|\bAddresses\b|(?<!email )(?<!IP )\baddress\b(?=\s*[,;)]|\s+or\s|\s+and\s|\s+of\s+(employee|student))"),
    "phone_contact": ("Phone number / contact info", r"(?<!smart )phone numbers?|telephone|contact (info|details|information)"),
    "email_address": ("Email address", r"e-?mail address|electronic mail address|\bemail,"),
    "date_of_birth": ("Date / place of birth", r"date of birth|birth ?dates?|birthdays?|\bDOB\b|place of birth"),
    "ssn": ("Social Security number", r"social security|\bSSNs?\b"),
    "id_numbers": ("Student / staff ID numbers", r"(?<!facial )\bIDs?\b|identification numbers?|ID numbers?|student numbers?|unique (student|staff) identifier"),
    "drivers_license": ("Driver's license number", r"driver.?s licen[sc]e|passport number"),
    "grades_performance": ("Grades / test scores / performance data", r"\b[Gg]rades\b(?!\s*(\d|K\b|PK|pre|[–-]))(?!\s+band)|test scores?|assessment (data|results|scores|information)|[Aa]ssessment scores|exam information|academic (records?|information|performance)|student performance|performance data|progress data|report cards?|\bGPA\b|transcripts|\bassessments\b(?=\s*[,)]|,? etc)"),
    "attendance": ("Attendance", r"attendance(?! enforcement)"),
    "discipline_behavior": ("Discipline / behavior records", r"disciplin(e|ary) (records?|information|details|history|data)|discipline,|behavio(u)?r(al)? (records?|reports?|data|incidents?|information|history)|behavior incidents"),
    "iep_504_disability": ("IEP / 504 / disability information", r"\bIEPs?\b|individuali[sz]ed education(al)? (program|plan)s?|\b504\b|disabilit\w+ (status|designation|information|details|diagnosis)|disability/|disability-related|special education (information|records?|status|data)|specific accommodations|disability diagnosis"),
    "health_medical": ("Health / medical information", r"health (information|records?|data|conditions?|details|insurance)|health/medical|medical (records?|information|histor\w*|data)|\bMedical,|mental health information|therapy notes|allergy|\bPHI\b"),
    "photos_images": ("Photos / images / likeness", r"(?i:photos?\b|photographs?|pictures|facial images?|faces/photos|likeness)|[Ii]mages,|[Ii]mages or|image, voice"),
    "audio_video": ("Audio / video / voice recordings", r"voice (recordings?|clips?)|voiceprints?|\baudio\b|\bvideos?\b|recordings? of|[Rr]ecordings\b(?= of| or|,)"),
    "biometrics": ("Biometric data", r"biometric|fingerprints?|facial (scans?|recognition)"),
    "race_ethnicity_demographics": ("Race / ethnicity / demographics", r"\brace\b|ethnic"),
    "religion": ("Religion", r"religio"),
    "gender_sexual_orientation": ("Sex / gender / sexual orientation", r"gender|sexual orientation|\bsex\b"),
    "citizenship_immigration": ("Citizenship / immigration / national origin", r"national origin|(?<!digital )(?<!Digital )citizenship|immigration"),
    "family_others_info": ("Family members' / others' information", r"family (members?|information|data|details|income)|names of family|parents?.?(/guardian)?.? names|mother.?s maiden|[Pp]arent/[Gg]uardian [Ii]nformation|friends.? information"),
    "financial": ("Financial information", r"financial (info|information|data)|other financial|credit card|bank (account|details)|free (and|or) reduced|family income"),
    "location": ("Location / geographic identifiers", r"geographic|geolocation|location data|\bcity\b|school of attendance|zip code"),
    "credentials_online_ids": ("Passwords / credentials / device & online identifiers", r"IP address|device identif|machine or device|usernames|passwords|password,|login credentials|digital identifiers|metadata|online activity"),
    "student_work": ("Student work", r"(?<![Gg]rading )(?<!assess )student work(?! in progress)|writing samples?|student-generated content|identifiable student work"),
    "employee_records": ("Employee / personnel records & evaluations", r"personnel (records|information|files|data)|confidential personnel|personnel confidentiality|employee (records|evaluations?|performance|information|data)|evaluation data|teacher observations?|staff evaluations?|employee performance|confidential employee"),
    "education_records": ("Education records (general)", r"education(al)? records?|student records?|pupil records?|cumulative (file|record)"),
    "indirect_identifiers": ("Indirect / combinable identifiers", r"indirect(ly)? identif|linked or linkable|alone or in combination|could (reasonably )?be combined|when combined|combined with other|combination of other"),
    "english_learner": ("English learner (ESOL/ELL) status", r"\bESOL\b|English learner|\bELL\b"),
}
CASE_SENSITIVE = {"photos_images"}
PATTERNS = {k: re.compile(p) if k in CASE_SENSITIVE else re.compile(p, re.I) for k, (_, p) in CATS.items()}

# Pattern hits that a manual read showed are not PII definitions. Each one is written
# to pii_rejected_matches.csv with its reason and the quote that was rejected.
PII_EXCLUDE = {
    ("Oklahoma_AI_Guidance", "name"): "'Names' refers to names of AI tools, not people",
    ("Massachusetts_AI_Guidance", "home_address"): "'addresses' is a verb (the guidance addresses AI's impact)",
    ("Arizona_GenAI_Guidance", "email_address"): "email mentioned as a prompt-injection channel, not as personal data",
    ("Illinois_AI_Guidance", "email_address"): "email listed as a record type under FOIA, not as personal data",
    ("Hempfield_Policy_815_1_AI", "grades_performance"): "about who assigns grades (teachers, not AI)",
    ("Illinois_AI_Guidance", "grades_performance"): "'grade level' in a tool review, not grade records",
    ("Louisiana_AI_Guidance", "grades_performance"): "teacher assessment data under a law on employee evaluations (coded as employee records instead)",
    ("NewMexico_AI_Guidance", "grades_performance"): "'Middle Grades' is a grade band heading",
    ("Oklahoma_AI_Guidance", "grades_performance"): "says AI must not issue grades; not about grade data",
    ("Oxnard_UHSD_AR_0441_AI", "grades_performance"): "says final grades need human judgment; not about grade data",
    ("Philadelphia_GenAI_Guidelines", "grades_performance"): "describes a tool that grades student work; not about grade data",
    ("UnionCounty_KY_Digital_Classrooms_AI", "grades_performance"): "describes AI analyzing performance as a benefit, not as protected data",
    ("West_Virginia_AI_Guidance", "grades_performance"): "describes AI analyzing performance under a vendor MOU, not as a PII definition",
    ("Oregon_GenAI_K12_Guidance", "attendance"): "'school of attendance' is a location identifier (coded as location instead)",
    ("Charleston_Generative_AI_Web_Page", "discipline_behavior"): "discipline listed as a high-stakes decision AI must not make",
    ("DC_OSSE_LEA_AI_Model_Policy", "iep_504_disability"): "heading for an IEP-drafting use case, not a PII list",
    ("Massachusetts_AI_Guidance", "iep_504_disability"): "Section 504 named in a list of applicable laws",
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "iep_504_disability"): "IEP goals named as a use case, not as protected data",
    ("Oregon_GenAI_K12_Guidance", "iep_504_disability"): "IEPs named as high-stakes translation needing review",
    ("Missouri_AI_Guidance", "health_medical"): "HIPAA named as a compliance concern; no health data named",
    ("FCPS_AI_Staff_Guidance", "photos_images"): "about who owns student images (intellectual property), not privacy",
    ("Grant_Parish_Employee_AUP_AI_Addendum", "photos_images"): "about storing personal pictures on district computers",
    ("Louisiana_AI_Guidance", "photos_images"): "'images' in the definition of generative AI",
    ("Springfield_MO_SPS_AI_Handbook", "audio_video"): "about deepfakes (creating fake recordings), not protected data",
    ("Montana_AI_K12_Guidelines", "citizenship_immigration"): "'digital-citizenship' policies",
    ("ABC_USD_AI_Guide", "credentials_online_ids"): "teachers monitor students' online activity; not about protected data",
    ("DC_OSSE_LEA_AI_Model_Policy", "credentials_online_ids"): "rule against surveilling online activity; not a PII definition",
    ("Maine_DOE_Technology_Guidance", "credentials_online_ids"): "general password-strength advice",
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "credentials_online_ids"): "passwords as an access-control measure",
    ("Portland_PS_AI_Guidebook", "credentials_online_ids"): "don't share account passwords with colleagues; not about AI inputs",
    ("Broward_Powered_by_AI_Website", "student_work"): "parents may ask how a tool uses student work; not named as protected data",
    ("Hudson_City_SD_AI_Policy_8636", "student_work"): "student work named as something a district may allow AI to analyze",
    ("OCPS_AI_Guidance_Hub", "student_work"): "teachers review student work; not named as protected data",
    ("Washington_OSPI_AI_Guidance", "student_work"): "student work must not contain PII; the work itself is not named as PII",
    ("EBR_AI_Web_Page", "employee_records"): "employee evaluations named as a task AI must not do",
    ("Campbell_County_SD1_Technology_Policy_7100", "education_records"): "'Student Records' is a policy title in a cross-reference",
    ("Cutter_Morning_Star_AI_Policy_3_58", "education_records"): "AI may help manage student records; not a PII definition",
    ("Elwood_UFSD_Policy_8636_AI", "education_records"): "'Student Records' is a policy title in a cross-reference list",
    ("Hudson_City_SD_AI_Policy_8636", "education_records"): "'Student Records' is a policy title in a cross-reference list",
    ("Lodi_USD_AI_Board_Policy", "education_records"): "'Student records' is a statute title in a legal-reference list",
    ("Oxnard_UHSD_BP0441_AI", "education_records"): "'Student records' is a statute title in a legal-reference list",
}
PII_ADD = [
    ("Oklahoma_AI_Guidance", "race_ethnicity_demographics",
     "High Risk (Red) — All tools collecting sensitive information like student demographics or PII."),
    ("SMUHSD_AI_Guidance_Page", "race_ethnicity_demographics",
     "This includes student and staff contact information, demographic information and rosters."),
]

# ---------------------------------------------------------------- AI tools
# (doc, tool, status, scope / notes). status: approved | conditional | not_approved | mentioned
#   approved      the document says the tool is approved, adopted, licensed, provided or recommended
#   conditional   allowed only with stated limits (e.g. no PII, personal accounts, pending contract)
#   not_approved  blocked, not approved, or described as not secure for district data
#   mentioned     named only as an example (age limits, how chatbots work, etc.)
TOOLS = [
    ("27J_Staff_AI_Regulation_GBEE_R2", "ChatGPT", "mentioned", "listed as an AI program covered by the no-PII rule"),
    ("27J_Staff_AI_Regulation_GBEE_R2", "Google Gemini", "mentioned", "listed as an AI program covered by the no-PII rule"),
    ("27J_Staff_AI_Regulation_GBEE_R2", "Claude", "mentioned", "listed as an AI program covered by the no-PII rule"),
    ("27J_Staff_AI_Regulation_GBEE_R2", "Microsoft Copilot", "mentioned", "listed as an AI program covered by the no-PII rule"),
    ("27J_Staff_AI_Regulation_GBEE_R2", "Apple Intelligence", "mentioned", "listed as an AI program covered by the no-PII rule"),
    ("ABC_USD_AI_Guide", "Google Gemini", "approved", "curated list reviewed for privacy; users 13+"),
    ("ASD20_AI_Quick_Start_Guide", "MagicSchool", "approved", "district-recommended; students all grades via teacher rooms"),
    ("ASD20_AI_Quick_Start_Guide", "Google Gemini", "approved", "high school students, district enterprise version"),
    ("ASD20_AI_Quick_Start_Guide", "ChatGPT", "not_approved", "blocked for students"),
    ("ASD20_AI_Quick_Start_Guide", "Microsoft Copilot", "not_approved", "not approved for students"),
    ("Bellevue_SD_AI_Handbook", "Microsoft Copilot", "approved", "only tool approved for personal/confidential data"),
    ("Bellevue_SD_AI_Handbook", "MagicSchool", "approved", "approved tool"),
    ("Bellevue_SD_AI_Handbook", "Colleague AI", "approved", "approved tool"),
    ("BenHill_AI_Approved_Tools_Policy", "Canva", "approved", "education license only"),
    ("BenHill_AI_Approved_Tools_Policy", "Google Gemini", "approved", "education license only"),
    ("Bixby_Board_Policy_3142_AI", "ChatGPT", "not_approved", "example of an open, unvetted system; no student identifiers"),
    ("Broward_Powered_by_AI_Website", "Microsoft Copilot", "approved", "enterprise data protection"),
    ("Broward_Powered_by_AI_Website", "MagicSchool", "approved", "includes MagicStudent; student-facing"),
    ("Broward_Powered_by_AI_Website", "ChatGPT", "not_approved", "open public tool; not approved for student-facing use"),
    ("Broward_Powered_by_AI_Website", "Google Gemini", "not_approved", "open 'Google AI features'; not approved for student-facing use"),
    ("Cambridge_PS_GenAI_Guidance", "SchoolAI", "approved", "all students"),
    ("Cambridge_PS_GenAI_Guidance", "Canva", "approved", "students 13+"),
    ("Cambridge_PS_GenAI_Guidance", "MagicSchool", "approved", "students 13+; no PII even in paid version"),
    ("Cambridge_PS_GenAI_Guidance", "Google Gemini", "approved", "high school (CRLS) students"),
    ("Cambridge_PS_GenAI_Guidance", "ChatGPT", "not_approved", "not approved for students; no PII even with ChatGPT Plus"),
    ("Cambridge_PS_GenAI_Guidance", "Microsoft Copilot", "not_approved", "not approved for students"),
    ("CCPS_AI_Handbook", "Microsoft Copilot", "approved", "district standard GenAI platform; students grades 9-12"),
    ("CherryCreek_AI_Guidance", "Microsoft Copilot", "approved", "Copilot Chat described as a secure district tool"),
    ("CherryCreek_AI_Guidance", "Google Gemini", "approved", "described as a secure district tool"),
    ("Christina_SD_GenAI_Classroom_Page", "MagicSchool", "approved", "listed under the district's 'Favorite AI Tools' (recommendation)"),
    ("CMS_Generative_AI_Guidance", "Microsoft Copilot", "approved", "Copilot with Microsoft 365 = secure closed system"),
    ("CMS_Generative_AI_Guidance", "ChatGPT", "not_approved", "free/public version described as not secure"),
    ("CMS_Generative_AI_Guidance", "Claude", "not_approved", "free/public version described as not secure"),
    ("CPS_Chicago_AI_Guidebook", "Microsoft Copilot", "approved", "district enterprise product with data agreement"),
    ("CPS_Chicago_AI_Guidebook", "Google Gemini", "approved", "district enterprise product"),
    ("CPS_Chicago_AI_Guidebook", "NotebookLM", "approved", "district enterprise product"),
    ("CPS_Chicago_AI_Guidebook", "ChatGPT", "mentioned", "age-access table only"),
    ("CPS_Chicago_AI_Guidebook", "Claude", "mentioned", "age-access table only"),
    ("CPS_Chicago_AI_Guidebook", "Perplexity", "mentioned", "age-access table only"),
    ("CPS_Chicago_AI_Guidebook", "Adobe Express / Firefly", "mentioned", "age-access table only"),
    ("CPS_Chicago_AI_Guidebook", "Canva", "mentioned", "age-access table only"),
    ("Daviess_County_AI_Resource_Page", "SchoolAI", "approved", "contracted provider"),
    ("Daviess_County_AI_Resource_Page", "Google Gemini", "approved", "adults only for now"),
    ("Daviess_County_AI_Resource_Page", "MagicSchool", "approved", "high schools, via terms of service; teacher-provided link"),
    ("Daviess_County_AI_Resource_Page", "Brisk", "approved", "high schools, via terms of service; teacher-provided link"),
    ("Delaware_Generative_AI_Guidance", "ChatGPT", "mentioned", "example of an underlying model"),
    ("Delaware_Generative_AI_Guidance", "Google Gemini", "mentioned", "example of an underlying model"),
    ("Guilderland_Policy_8636_AI", "ChatGPT", "mentioned", "age / account requirements note"),
    ("Houston_ISD_AI_Guidebook", "ChatGPT", "approved", "ChatGPT Edu inside the HISD domain"),
    ("Houston_ISD_AI_Guidebook", "ChatGPT", "not_approved", "personal/consumer ChatGPT not to be used with student data"),
    ("Houston_ISD_AI_Guidebook", "Microsoft Copilot", "approved", "Microsoft 365 Copilot / Copilot Chat"),
    ("Houston_ISD_AI_Guidebook", "Google Gemini", "approved", "staff; students 8th grade+ with parental consent"),
    ("Houston_ISD_AI_Guidebook", "Amira Learning", "approved", "AI tool allowed for students below 8th grade"),
    ("Houston_ISD_AI_Guidebook", "Microsoft Reading Coach", "approved", "AI tool allowed for students below 8th grade"),
    ("Illinois_AI_Guidance", "Microsoft Teams live captions", "approved", "state guidance's sample tool review"),
    ("Illinois_AI_Guidance", "Snap&Read Universal", "approved", "state guidance's sample tool review"),
    ("Illinois_AI_Guidance", "Co:Writer Universal", "approved", "state guidance's sample tool review"),
    ("Illinois_AI_Guidance", "Read&Write (Texthelp)", "approved", "state guidance's sample tool review"),
    ("Illinois_AI_Guidance", "TalkingPoints", "approved", "state guidance's sample tool review"),
    ("Illinois_AI_Guidance", "Khanmigo", "conditional", "sample review: prefer district partnership"),
    ("Illinois_AI_Guidance", "MagicSchool", "conditional", "sample review: teacher-facing by default; students only with data addendum"),
    ("Illinois_AI_Guidance", "Google Gemini", "conditional", "sample review: Workspace for Education edition"),
    ("Illinois_AI_Guidance", "Microsoft Copilot", "conditional", "sample review: enterprise data protection"),
    ("Illinois_AI_Guidance", "ChatGPT", "not_approved", "sample review: consumer individual accounts"),
    ("Illinois_AI_Guidance", "Google Gemini", "not_approved", "sample review: consumer personal accounts"),
    ("Illinois_AI_Guidance", "Otter.ai", "not_approved", "sample review: meeting transcription for IEP/discipline"),
    ("Illinois_AI_Guidance", "ChatGPT", "mentioned", "ChatGPT Enterprise/Edu example; 'ChatGPT for Teachers' listed as a free tool in lesson examples"),
    ("Illinois_AI_Guidance", "Wayground (Quizizz)", "mentioned", "example student tool; use district rostering"),
    ("LBUSD_AI_Web_Page", "ChatGPT", "mentioned", "not suitable for students under 13"),
    ("LBUSD_AI_Web_Page", "Google Gemini", "mentioned", "not suitable for students under 13"),
    ("Louisiana_AI_Guidance", "ChatGPT", "mentioned", "age requirements example"),
    ("Maryland_MSDE_AI_Policy", "Microsoft Copilot", "approved", "state agency staff: Copilot in Teams with Maryland.gov account"),
    ("Maryland_MSDE_AI_Policy", "Google Gemini", "approved", "state agency staff: Gemini in Google Meet with Maryland.gov account"),
    ("Maryland_MSDE_AI_Policy", "Otter.ai", "not_approved", "meeting-note tools not permitted"),
    ("Maryland_MSDE_AI_Policy", "Fireflies.ai", "not_approved", "meeting-note tools not permitted"),
    ("Maryland_MSDE_AI_Policy", "Fathom", "not_approved", "meeting-note tools not permitted"),
    ("Maryland_MSDE_AI_Policy", "tl;dv", "not_approved", "meeting-note tools not permitted"),
    ("Maryland_MSDE_AI_Policy", "Notion AI", "not_approved", "tools embedded in programs like Notion not permitted"),
    ("Minneapolis_AI_Web_Page", "ChatGPT", "not_approved", "blocked; does not meet MPS privacy standards"),
    ("Missouri_AI_Guidance", "ChatGPT", "mentioned", "example of a larger, more reputable tool"),
    ("Missouri_AI_Guidance", "Microsoft Copilot", "mentioned", "example of a larger, more reputable tool"),
    ("Missouri_AI_Guidance", "Google Gemini", "mentioned", "example of a larger, more reputable tool"),
    ("Mustang_PS_AI_Web_Page", "Google Gemini", "approved", "approved AI tool list"),
    ("Mustang_PS_AI_Web_Page", "Lexia Core5", "approved", "approved AI tool list"),
    ("Newton_AI_Guidelines", "Brisk", "approved", "covered by a signed DPA; may receive PII"),
    ("Newton_AI_Guidelines", "ChatGPT", "conditional", "staff may use if no PII is shared (no DPA)"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "ChatGPT", "mentioned", "age limits example"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Microsoft Copilot", "mentioned", "age limits example"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Perplexity", "mentioned", "age limits example"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Google Gemini", "mentioned", "only frontier model with an education version"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Khanmigo", "mentioned", "built-for-education example; still needs vetting"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "SchoolAI", "mentioned", "built-for-education example; still needs vetting"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "MagicSchool", "mentioned", "built-for-education example; still needs vetting"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Skillstruck", "mentioned", "built-for-education example; still needs vetting"),
    ("NorthCarolina_NCDPI_GenAI_Recommendations", "Brisk", "mentioned", "built-for-education example; still needs vetting"),
    ("OCPS_AI_Guidance_Hub", "Google Gemini", "approved", "Gemini youth experience for students under 18"),
    ("Oregon_GenAI_K12_Guidance", "ChatGPT", "mentioned", "privacy-policy and oversharing example"),
    ("Owasso_PS_AI_Guiding_Philosophy", "Google Gemini", "approved", "Workspace for Education Plus version; students and staff"),
    ("Philadelphia_GenAI_Guidelines", "Google Gemini", "approved", "executed contract; staff and students"),
    ("Philadelphia_GenAI_Guidelines", "Adobe Express / Firefly", "approved", "executed contract; staff and students"),
    ("Philadelphia_GenAI_Guidelines", "ChatGPT", "mentioned", "age requirements example"),
    ("Philadelphia_GenAI_Guidelines", "Microsoft Copilot", "mentioned", "age requirements example"),
    ("Portland_PPS_AI_Web_Page", "Google Gemini", "approved", "recommended for staff privacy"),
    ("Portland_PPS_AI_Web_Page", "Adobe Express / Firefly", "approved", "staff only"),
    ("Portland_PPS_AI_Web_Page", "Canva", "approved", "staff only"),
    ("Portland_PPS_AI_Web_Page", "Kami", "approved", "staff only"),
    ("Portland_PPS_AI_Web_Page", "Screencastify", "approved", "staff only"),
    ("Portland_PS_AI_Guidebook", "Google Gemini", "approved", "district-approved tool"),
    ("PSJA_AI_Guidebook", "ChatGPT", "conditional", "personal premium accounts (ChatGPT Plus) allowed with no PII"),
    ("PSJA_AI_Guidebook", "Google Gemini", "conditional", "personal premium accounts (Gemini Advanced) allowed with no PII"),
    ("RhodeIsland_AI_Guidance", "Khanmigo", "mentioned", "'walled garden' example"),
    ("RhodeIsland_AI_Guidance", "DreamBox Learning", "mentioned", "'walled garden' example"),
    ("RhodeIsland_AI_Guidance", "ChatGPT", "mentioned", "age requirements example"),
    ("Spartanburg_4_Generative_AI_Guidelines", "MagicSchool", "approved", "the only AI platform students may use"),
    ("Springfield_MO_SPS_AI_Handbook", "ChatGPT", "not_approved", "public tool; never enter PII"),
    ("Stillwater_AI_Tools_Page", "Google Gemini", "approved", "staff and students grades 6-12"),
    ("Stillwater_AI_Tools_Page", "NotebookLM", "approved", "staff and students grades 6-12"),
    ("Stillwater_AI_Tools_Page", "Adobe Express / Firefly", "approved", "AI features in district-approved Adobe tools"),
    ("Stillwater_AI_Tools_Page", "Canvas (embedded AI)", "approved", "AI features in district-approved curriculum tools"),
    ("Stillwater_AI_Tools_Page", "Google Classroom (embedded AI)", "approved", "AI features in district-approved curriculum tools"),
    ("Tacoma_AI_Web_Page", "Microsoft Copilot", "approved", "district tool described on the district AI page"),
    ("Tacoma_AI_Web_Page", "Colleague AI", "approved", "district tool described on the district AI page"),
    ("Vermont_AI_Guidance_for_Education", "Google Gemini", "mentioned", "Gemini for Education example"),
    ("West_Virginia_AI_Guidance", "ChatGPT", "mentioned", "parental permission example"),
]
TOOL_ALIAS = {
    "ChatGPT": r"chat ?gpt|chaptgpt|chatgtp", "Google Gemini": r"gemini|google (artificial intelligence|ai)",
    "Microsoft Copilot": r"copilot", "MagicSchool": r"magic ?school", "SchoolAI": r"school ?ai\b",
    "Brisk": r"brisk", "Khanmigo": r"khanmigo", "Claude": r"claude", "Perplexity": r"perplexity",
    "NotebookLM": r"notebook ?lm", "Canva": r"canva\b", "Adobe Express / Firefly": r"adobe|firefly",
    "Colleague AI": r"colleague ai", "Kami": r"\bkami\b", "Screencastify": r"screencastify",
    "Lexia Core5": r"lexia", "Amira Learning": r"amira", "Microsoft Reading Coach": r"reading coach",
    "Snap&Read Universal": r"snap ?& ?read", "Co:Writer Universal": r"co:writer", "Read&Write (Texthelp)": r"read ?& ?write",
    "TalkingPoints": r"talkingpoints", "Microsoft Teams live captions": r"live captions", "Otter.ai": r"otter",
    "Fireflies.ai": r"fireflies", "Fathom": r"fathom", "tl;dv": r"tl;dv", "Notion AI": r"notion",
    "Apple Intelligence": r"apple ai", "DreamBox Learning": r"dreambox", "Skillstruck": r"skillstruck",
    "Wayground (Quizizz)": r"wayground", "Canvas (embedded AI)": r"\bcanvas\b", "Google Classroom (embedded AI)": r"google classroom",
}

# ---------------------------------------------------------------- helpers
def flat_text(pdf_path):
    """Return the PDF text on one line, plus where each passage starts.

    Every passage in these PDFs is a heading line followed by a "Source: <page or
    section>" line, so each match can be traced back to the passage it sits in.
    """
    with pdfplumber.open(pdf_path) as pdf:
        t = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    lines = t.split("\n")
    flat = re.sub(r"\s*\n\s*", " ", t)
    passages, pos = [], 0
    for i, line in enumerate(lines):
        if line.startswith("Source:"):
            pos = flat.find("Source:", pos)
            passages.append((pos, lines[i - 1].strip() if i else "", line[len("Source:"):].strip()))
            pos += 1
    return flat, passages


def locate(passages, pos):
    """'<page or section> (passage: <heading>)' for the passage containing pos."""
    # a passage's heading sits just before its "Source:" line, so it belongs to that passage
    owner = [p for p in passages if p[0] - len(p[1]) - 2 <= pos]
    p = owner[-1] if owner else (passages[0] if passages else None)
    return f"{p[2]} (passage: {p[1]})" if p else ""


def snippet(text, start, end, before=110, after=70):
    a, b = max(0, start - before), min(len(text), end + after)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


def find_pii(text):
    zones = []
    for m in ANCHOR.finditer(text):
        a, b = max(0, m.start() - 150), min(len(text), m.end() + 450)
        if zones and a <= zones[-1][1]:
            zones[-1][1] = b
        else:
            zones.append([a, b])
    # Keep every category hit; for the evidence quote prefer a hit that sits in a list
    # ("name, address, phone") over a first passing use of the word.
    hits = defaultdict(list)
    for a, b in zones:
        for k, pat in PATTERNS.items():
            hits[k].extend(pat.finditer(text, a, b))
    in_list = lambda m: re.search(r"[,•:(]\s*$", text[max(0, m.start() - 4):m.start()]) or \
        re.match(r"\s*[,;)]", text[m.end():m.end() + 3])
    best = {k: next((m for m in ms if in_list(m)), ms[0]) for k, ms in hits.items() if ms}
    return {k: (snippet(text, *m.span()), m.start()) for k, m in best.items()}


# Where the first list-like hit is still not the passage that justifies the code.
EVIDENCE_OVERRIDE = {
    ("Illinois_AI_Guidance", "name"): r"student names, IDs",
    ("Illinois_AI_Guidance", "discipline_behavior"): r"discipline details",
}


ORG_FIX = {
    "Artificial Intelligence Handbook for Seattle Public Schools": "Seattle Public Schools",
    "Christina School District Technology Hub": "Christina School District",
    "Jackson Public Schools Educational Technology": "Jackson Public Schools",
    "Los Angeles Unified School District Policy Bulletin": "Los Angeles Unified School District",
}


def org_name(title):
    name = _org_name(title)
    return ORG_FIX.get(name, name)


def _org_name(title):
    title = title.replace("，", ",")
    parens = [p for p in re.findall(r"\(([^()]*)\)", title) if p.strip() not in {"AI", "Artificial Intelligence"}]
    if not parens:
        return re.sub(r"\s*(Artificial Intelligence|AI).*$", "", title).strip() or title
    return parens[-1].split(",")[-1].strip()


# ---------------------------------------------------------------- build
def main():
    log = list(csv.DictReader(open(PASSAGES / "Privacy_Passages_Log.csv", encoding="utf-8-sig")))
    src = list(csv.DictReader(open(REPO / "k12_ai_policies_singleline.csv", encoding="utf-8-sig")))
    tools_by_doc = defaultdict(list)
    for doc, tool, status, note in TOOLS:
        tools_by_doc[doc].append((tool, status, note))

    doc_rows, evidence, rejected = [], [], []
    for row, s in zip(log, src):
        pdf = row["output_pdf"]
        doc = pdf.replace("_Privacy_Passages.pdf", "")
        text, passages = flat_text(PASSAGES / pdf) if pdf else ("", [])
        org = org_name(row["title"]) if row["level"] == "district" else f"{row['state']} (state level)"
        found = find_pii(text) if text else {}
        pii, how = {}, {}
        for k, (q, pos) in found.items():
            if (doc, k) in PII_EXCLUDE:
                rejected.append({"csv_row": row["csv_row"], "organization": org, "pdf_file": pdf,
                                 "pii_item": CATS[k][0], "reason_rejected": PII_EXCLUDE[(doc, k)],
                                 "location": locate(passages, pos), "rejected_quote": q})
            else:
                pii[k], how[k] = (q, pos), "pattern match, confirmed by reading"
        for d, k, q in PII_ADD:
            if d == doc:
                pos = text.find(q[:40])
                pii[k], how[k] = (snippet(text, pos, pos + len(q)), pos), "added by hand (no pattern for this wording)"
        for (d, k), pat in EVIDENCE_OVERRIDE.items():
            if d == doc and k in pii:
                m = re.search(pat, text)
                pii[k] = (snippet(text, m.start(), m.end()), m.start())
                how[k] += "; quote chosen by hand (first match was a passing use)"
        uses_pii = bool(re.search(r"\bPII\b|personally[- ]identif", text, re.I))
        mentions = bool(ANCHOR.search(text))
        n = len(pii)
        tier = ("no PDF (no privacy passages)" if not pdf else
                "detailed list (8+ items)" if n >= 8 else "moderate list (4-7 items)" if n >= 4 else
                "brief list (1-3 items)" if n else "general mention only" if mentions else "privacy passages, but no personal-data language")
        tl = tools_by_doc.get(doc, [])
        by = lambda st: "; ".join(f"{t} ({note})" for t, x, note in tl if x == st)
        out = {
            "csv_row": row["csv_row"], "state": row["state"], "level": row["level"],
            # state-level documents come from many bodies (DOE, boards, universities), so they are grouped by state
            "organization": org,
            "doc_type": row["doc_type"], "title": row["title"],
            "comparison_group": s["comparison_group"], "ai_private_investment_2025": s["ai_private_investment_2025"],
            "pdf_file": pdf, "uses_term_PII": "yes" if uses_pii else "no", "pii_definition_level": tier,
            "pii_item_count": n, "pii_items": "; ".join(CATS[k][0] for k in CATS if k in pii),
            "approved_tools": by("approved"), "conditional_tools": by("conditional"),
            "not_approved_tools": by("not_approved"), "mentioned_only_tools": by("mentioned"),
        }
        out.update({f"pii_{k}": int(k in pii) for k in CATS})
        doc_rows.append(out)
        for k in CATS:
            if k in pii:
                evidence.append({"csv_row": row["csv_row"], "organization": org, "level": row["level"],
                                 "pdf_file": pdf, "type": "PII item", "item": CATS[k][0], "status": "",
                                 "how_decided": how[k], "location": locate(passages, pii[k][1]),
                                 "quote": pii[k][0]})
        for tool, status, note in tl:
            m = re.search(TOOL_ALIAS[tool], text, re.I)
            evidence.append({"csv_row": row["csv_row"], "organization": org, "level": row["level"],
                             "pdf_file": pdf, "type": "AI tool", "item": tool, "status": f"{status}: {note}",
                             "how_decided": "coded by hand from the passage",
                             "location": locate(passages, m.start()) if m else "",
                             "quote": snippet(text, m.start(), m.end()) if m else ""})

    write(HERE / "pii_and_tools_by_document.csv", doc_rows)
    write(HERE / "evidence.csv", evidence)
    write(HERE / "pii_rejected_matches.csv", rejected)

    # PII summary: count organizations (a district with two documents counts once)
    n_dist = len({r["organization"] for r in doc_rows if r["level"] == "district" and r["pdf_file"]})
    pii_sum = []
    for k, (label, _) in CATS.items():
        hits = [r for r in doc_rows if r[f"pii_{k}"]]
        dist = sorted({r["organization"] for r in hits if r["level"] == "district"})
        state = sorted({r["organization"] for r in hits if r["level"] == "state"})
        pii_sum.append({"pii_item": label, "districts": len(dist),
                        "pct_of_districts_with_privacy_pdf": round(100 * len(dist) / n_dist, 1),
                        "states_state_level": len(state), "district_list": "; ".join(dist),
                        "state_list": "; ".join(s.replace(" (state level)", "") for s in state)})
    pii_sum.sort(key=lambda r: (-r["districts"], -r["states_state_level"]))
    write(HERE / "pii_category_summary.csv", pii_sum)

    # Spectrum: one row per district / state, merging its documents (union of PII items and tools)
    orgs = defaultdict(list)
    for r in doc_rows:
        if r["pdf_file"]:
            orgs[(r["level"], r["state"], r["organization"])].append(r)
    spectrum = []
    for (lv, st, org), rs in orgs.items():
        items = [k for k in CATS if any(r[f"pii_{k}"] for r in rs)]
        merge = lambda col: "; ".join(dict.fromkeys(x for r in rs for x in r[col].split("; ") if x))
        rec = {"organization": org, "level": lv, "state": st, "comparison_group": rs[0]["comparison_group"],
               "documents": len(rs), "uses_term_PII": "yes" if any(r["uses_term_PII"] == "yes" for r in rs) else "no",
               "pii_item_count": len(items), "pii_items": "; ".join(CATS[k][0] for k in items),
               "approved_tools": merge("approved_tools"), "conditional_tools": merge("conditional_tools"),
               "not_approved_tools": merge("not_approved_tools")}
        rec.update({f"pii_{k}": int(k in items) for k in CATS})
        spectrum.append(rec)
    spectrum.sort(key=lambda r: (r["level"], -r["pii_item_count"], r["organization"]))
    write(HERE / "pii_spectrum_by_organization.csv", spectrum)

    level = {r["pdf_file"].replace("_Privacy_Passages.pdf", ""): (r["level"], r["organization"]) for r in doc_rows}
    agg = defaultdict(lambda: defaultdict(set))
    for doc, tool, status, _ in TOOLS:
        lv, org = level[doc]
        agg[tool][(lv, status)].add(org)
    tool_sum = []
    for tool, d in agg.items():
        rec = {"tool": tool}
        for lv in ("district", "state"):
            for st in ("approved", "conditional", "not_approved", "mentioned"):
                rec[f"{lv}_{st}"] = len(d[(lv, st)])
        rec["districts_approving"] = "; ".join(sorted(d[("district", "approved")]))
        rec["districts_conditional"] = "; ".join(sorted(d[("district", "conditional")]))
        rec["districts_not_approving"] = "; ".join(sorted(d[("district", "not_approved")]))
        rec["states_any_status"] = "; ".join(sorted({o.replace(" (state level)", "") for (lv, _), os in d.items()
                                                     if lv == "state" for o in os}))
        tool_sum.append(rec)
    tool_sum.sort(key=lambda r: (-r["district_approved"], -r["state_approved"], r["tool"]))
    write(HERE / "ai_tool_summary.csv", tool_sum)
    print(f"{len(doc_rows)} documents, {len(evidence)} evidence rows, "
          f"{len(pii_sum)} PII items, {len(tool_sum)} tools")


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
