import streamlit as st
from openai import OpenAI
import PyPDF2
import io
import datetime
import random

# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Mock Trial Case Analyzer",
    page_icon="⚖️",
    layout="wide"
)

# ==========================================
# CUSTOM STYLING
# ==========================================

st.markdown("""
<style>
    .main {padding: 2rem;}
    .stButton>button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        font-size: 16px;
        padding: 0.5rem;
        border-radius: 5px;
        border: none;
    }
    .stButton>button:hover {background-color: #0052a3;}
    .cost-display {
        color: #666;
        font-size: 0.85rem;
        font-style: italic;
    }
    .feedback-section {
        background-color: #f0f8ff;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #0066cc;
        margin: 1rem 0;
    }
    .correct-answer {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .incorrect-answer {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #dc3545;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# API KEY SETUP
# ==========================================

def get_api_key():
    """Securely load API key from secrets or environment"""
    try:
        return st.secrets["OPENAI_API_KEY"]
    except:
        import os
        return os.getenv("OPENAI_API_KEY")

api_key = get_api_key()
if not api_key:
    st.error("⚠️ **API Key Not Found** - Please configure your OpenAI API key in Streamlit Cloud secrets")
    st.stop()

# Initialize OpenAI client
try:
    client = OpenAI(api_key=api_key)
except Exception as e:
    st.error(f"⚠️ **OpenAI Initialization Error:** {str(e)}")
    st.error("Make sure you have openai>=1.35.0 installed. Check your requirements.txt file.")
    st.stop()

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

def aggressive_preprocess(case_text):
    """
    Aggressively remove ALL meta-information before sending to AI.
    """
    meta_patterns = [
        "in honor of", "dedicated to", "in memory of", "this case honors",
        "written by", "authored by", "created by", "developed by",
        "mock trial competition", "competition rules", "tournament",
        "judge instructions", "scoring", "time limit", "points",
        "for educational purposes", "learning objectives",
        "case writer", "based on", "inspired by",
        "copyright", "all rights reserved", "©",
        "page ", "exhibit ", "stipulation"
    ]
    
    lines = case_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_lower = line.strip().lower()
        
        if len(line_lower) < 15:
            continue
        
        has_meta = any(pattern in line_lower for pattern in meta_patterns)
        if has_meta:
            continue
        
        if line.strip().isupper() and len(line.strip()) > 5:
            continue
        
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    while '\n\n\n' in cleaned_text:
        cleaned_text = cleaned_text.replace('\n\n\n', '\n\n')
    
    return cleaned_text.strip()

def extract_witness_statement(case_text, witness_name):
    """
    Extract ONLY the specific witness's statement from the case packet.
    """
    lines = case_text.split('\n')
    witness_statement = []
    capturing = False
    
    witness_variations = [
        witness_name.lower(),
        f"statement of {witness_name.lower()}",
        f"testimony of {witness_name.lower()}",
        f"witness: {witness_name.lower()}",
        f"direct examination of {witness_name.lower()}",
        f"cross examination of {witness_name.lower()}"
    ]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        if any(var in line_lower for var in witness_variations):
            capturing = True
            witness_statement.append(line)
            continue
        
        if capturing:
            stop_phrases = [
                "statement of", "testimony of", "witness:", 
                "direct examination of", "cross examination of",
                "exhibit", "stipulation", "charge", "verdict form"
            ]
            
            if any(phrase in line_lower for phrase in stop_phrases):
                if not any(var in line_lower for var in witness_variations):
                    break
            
            witness_statement.append(line)
    
    result = '\n'.join(witness_statement)
    
    if len(result) < 100:
        return case_text[:3000]
    
    return result[:3000]

def smart_summarize_case(case_text):
    """
    Use AI to condense while preserving ALL legal content.
    """
    if len(case_text) <= 16000:
        return case_text
    
    summary_prompt = f"""Extract ONLY legal case content from this document.

RULES:
1. INCLUDE all charges, parties, witnesses, dates, locations, events, evidence, testimony
2. PRESERVE exact names, numbers, quotes
3. KEEP all contradictions and disputed facts
4. EXCLUDE dedications, author info, competition rules, instructions

Output ONLY case facts. No preamble.

Document:
{case_text[:16000]}

Case content only:"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract case content only. Preserve all legal details. Remove meta-information."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.1,
            max_tokens=3500
        )
        return response.choices[0].message.content
    except Exception as e:
        return case_text[:16000]

def estimate_cost(tokens):
    """Calculate estimated API cost"""
    return (tokens / 1000) * 0.00175

def call_openai(system_prompt, user_prompt, max_tokens=2600, temperature=0.2):
    """
    Make OpenAI API call with enhanced analysis capabilities.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            presence_penalty=0.2,
            frequency_penalty=0.0
        )
        
        finish_reason = response.choices[0].finish_reason
        content = response.choices[0].message.content
        
        if finish_reason == "length":
            content += "\n\n---\n⚠️ *Analysis truncated. Try a more specific analysis type for complete results.*"
        
        return content, response.usage.total_tokens
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None, 0

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================

if 'cross_exam_mode' not in st.session_state:
    st.session_state.cross_exam_mode = False
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'case_text' not in st.session_state:
    st.session_state.case_text = ""
if 'witness_name' not in st.session_state:
    st.session_state.witness_name = ""
if 'total_cost' not in st.session_state:
    st.session_state.total_cost = 0.0
if 'exam_type' not in st.session_state:
    st.session_state.exam_type = ""
if 'objection_mode' not in st.session_state:
    st.session_state.objection_mode = False
if 'objection_history' not in st.session_state:
    st.session_state.objection_history = []
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'objection_case_text' not in st.session_state:
    st.session_state.objection_case_text = ""
if 'objection_witness' not in st.session_state:
    st.session_state.objection_witness = ""
if 'saved_objection_exam_type' not in st.session_state:
    st.session_state.saved_objection_exam_type = ""
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'question_count' not in st.session_state:
    st.session_state.question_count = 0
if 'witness_statement' not in st.session_state:
    st.session_state.witness_statement = ""

# ==========================================
# HEADER
# ==========================================

st.title("⚖️ Mock Trial Case Analyzer")
st.markdown("**AI-Powered Case Analysis & Cross-Examination Practice**")
st.markdown("*Built by Vihaan Paka-Hegde - University High School*")
st.markdown("---")

# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:
    st.header("🎯 Mode Selection")
    
    mode = st.radio(
        "Choose your tool:",
        ["Case Analysis", "Cross-Examination Simulator", "Objection Practice"],
        help="Case Analysis: Get AI insights\nCross-Exam: Practice questioning\nObjection Practice: Learn when to object"
    )
    
    st.markdown("---")
    st.markdown("**💡 Tips**")
    if mode == "Case Analysis":
        st.info("The AI analyzes ONLY facts explicitly stated in your case packet. Cross-Examination Simulator and Objection Practice modes are still being developed")
    elif mode == "Cross-Examination Simulator":
        st.info("AI simulates a witness based strictly on their testimony.")
    else:
        st.info("Practice objecting to improper questions. Mix of proper and improper questions.")

# ==========================================
# MODE 1: CASE ANALYSIS (ENHANCED)
# ==========================================

if mode == "Case Analysis":
    
    st.subheader("📝 Case Input")
    
    uploaded_file = st.file_uploader(
        "Upload Case Packet (PDF)",
        type=['pdf'],
        help="Upload your case packet as PDF"
    )
    
    st.markdown("**OR paste text directly:**")
    case_text_input = st.text_area(
        "Case packet text:",
        height=200,
        placeholder="Paste case text here..."
    )
    
    if uploaded_file:
        with st.spinner("📄 Extracting text from PDF..."):
            case_text = extract_text_from_pdf(uploaded_file)
            if case_text:
                st.success(f"✅ Extracted {len(case_text):,} characters")
    else:
        case_text = case_text_input
    
    st.subheader("🔍 Analysis Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        analysis_type = st.selectbox(
            "Analysis type:",
            [
                "Full Case Analysis",
                "Key Facts Only",
                "Legal Issues",
                "Prosecution Arguments",
                "Defense Arguments",
                "Witness Questions",
                "Opening Statement Ideas",
                "Closing Statement Ideas"
            ]
        )
    
    with col2:
        witness_name_input = ""
        if analysis_type == "Witness Questions":
            witness_name_input = st.text_input("Witness name:", placeholder="Enter name...")
    
    if st.button("🚀 Analyze Case", type="primary"):
        
        if not case_text or len(case_text) < 50:
            st.error("⚠️ Please provide case text")
            st.stop()
        
        if analysis_type == "Witness Questions" and not witness_name_input:
            st.error("⚠️ Please enter witness name")
            st.stop()
        
        with st.spinner("🔍 Processing case packet..."):
            case_text_cleaned = aggressive_preprocess(case_text)
            
            if len(case_text_cleaned) > 16000:
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
        # ENHANCED SYSTEM PROMPT - Championship Level
        base_system = """You are a championship-winning Mock Trial coach with 20+ years of experience. You've coached teams to National Championships. You analyze cases with unprecedented depth and strategic insight.

ABSOLUTE RULES:
1. ONLY STATE FACTS EXPLICITLY WRITTEN IN THE CASE PACKET
2. NEVER INVENT OR ASSUME ANYTHING NOT IN THE CASE
3. DISTINGUISH META-INFO FROM CASE CONTENT
4. WHEN UNCERTAIN: State "This is not specified in the case packet"
5. DEPTH OVER BREADTH - Go deep into implications, not surface-level

ANALYTICAL APPROACH:
- Think like a championship attorney analyzing every angle
- Identify subtle connections between facts that others miss
- Recognize psychological and emotional dimensions
- Anticipate opposing counsel's strategies
- Find the "hidden" case within the case
- Analyze credibility with forensic precision
- Identify theme opportunities in unexpected places

STYLISTIC GUIDELINES:
- Use powerful, visceral language that creates mental images
- Create narrative themes that resonate emotionally
- Develop case theories that tell compelling stories
- Frame facts through psychological lenses
- Highlight human motivations and emotions
- Use metaphors and analogies that illuminate meaning
- Create "moments" that win cases

Your analysis must be 100% grounded in the case packet, but analyzed with championship-level depth and sophistication."""

        # ENHANCED PROMPTS - Deeper Analysis
        prompts = {
            "Full Case Analysis": f"""Conduct a COMPREHENSIVE championship-level analysis. Go DEEP, not surface-level.

**1. CASE OVERVIEW & NARRATIVE ARCHITECTURE**
- Parties, charges, key dates
- **CENTRAL CONFLICT**: What is this case REALLY about? (human level, not just legal)
- **NARRATIVE THEME**: The one sentence that captures the emotional core
- **CASE TAGLINE**: Memorable 3-5 word phrase
- **STORY ARC**: Beginning, rising tension, climax, resolution
- **COMPETING NARRATIVES**: How each side frames the same events differently

**2. CRITICAL FACTS - DEEP ANALYSIS (20-25 facts)**
For each fact, provide:
- **The fact** (with exact quote and source)
- **Surface meaning**: What it says
- **Deeper meaning**: What it REALLY means (implications, subtext)
- **Legal significance**: Which elements it proves/disproves
- **Psychological dimension**: What it reveals about motivations, character, truthfulness
- **Strategic value**: How to weaponize this (specific techniques)
- **Weakness potential**: How opposition attacks this
- **Emotional resonance**: How jurors will FEEL about this
- **Catchphrase**: How to frame this memorably

Prioritize: Timeline contradictions, motive evidence, bias indicators, impossible claims, corroboration failures, damning admissions

**3. LEGAL ARCHITECTURE**
- **Elements breakdown** (each element with detailed analysis)
- **Burden of proof** (what it REALLY means practically)
- **Proof matrix**: Rate each element for each side (Strong/Moderate/Weak/Fatal)
- **Win conditions**: Specific facts that determine victory
- **Achilles heels**: The one thing that destroys each side's case

**4. PROSECUTION/PLAINTIFF THEORY - CHAMPIONSHIP DEPTH**
- **Psychological narrative**: Why defendant did this (motive, means, opportunity)
- **Theme statement**: One powerful sentence (repeat 3+ times in trial)
- **Emotional arc**: How to structure the story for maximum impact
- **5-7 strategic arguments** (not just facts, but ARGUMENTS):
  * Title the argument (make it memorable)
  * Evidence chain (quote-by-quote building)
  * Why this CONNECTS with jurors (human psychology)
  * Anticipated defense response + counter-response
  * Delivery notes (tone, pacing, emphasis)
- **Witness strategy**: For each witness
  * Their role in narrative
  * Credibility deep-dive (3+ strengths, 3+ weaknesses)
  * How to present them (tone, approach, humanization)
  * Key testimony with exact quotes
  * Psychological profile
- **Power phrases** (10-15 memorable lines based on case facts)
- **Turning points**: The 3-5 moments that will win the case
- **Vulnerability management**: How to handle the 3 biggest weaknesses

**5. DEFENSE THEORY - CHAMPIONSHIP DEPTH**
- **Counter-narrative**: Alternative psychological explanation
- **Theme statement**: One powerful sentence (reasonable doubt)
- **Emotional arc**: How to structure doubt for maximum impact
- **5-7 strategic arguments**:
  * Title the argument
  * Evidence chain showing reasonable doubt
  * Why this CONNECTS with jurors
  * Anticipated prosecution response + counter-response
  * Delivery notes
- **Witness strategy**: For each defense witness
  * Role in creating doubt
  * Credibility deep-dive
  * Presentation approach
  * Key testimony with quotes
  * Psychological profile
- **Reasonable doubt themes** (5-7 specific angles)
- **Prosecution weakness exploitation** (detailed attack plan for their 3 biggest problems)
- **Power phrases** (10-15 lines emphasizing doubt)

**6. WITNESS-BY-WITNESS FORENSIC ANALYSIS**
For EACH key witness:
- **Testimony summary** (what they claim with quotes)
- **Credibility assessment** (rate 1-10 with detailed justification)
- **Bias analysis**: Motive to lie? Relationship to parties?
- **Consistency check**: Internal contradictions? Contradicts others?
- **Plausibility analysis**: Does their story make sense? Human nature test?
- **Memory issues**: Claims to remember impossible details? Convenient gaps?
- **Demeanor prediction**: How will they come across? Confident? Nervous? Defensive?
- **Direct exam strategy** (8-10 specific questions)
- **Cross exam strategy** (8-10 specific questions + impeachment plan)
- **Character in 5 words**: Memorable description
- **Hidden value**: What they reveal beyond their direct testimony

**7. EVIDENCE & EXHIBITS - FORENSIC ANALYSIS**
- Each key exhibit with:
  * What it shows (surface level)
  * What it PROVES (deeper implications)
  * Authentication issues
  * How each side spins it
  * Timeline corroboration/contradiction
  * Scientific/expert analysis if applicable
- **Timeline reconstruction**: Minute-by-minute when possible
- **Physical impossibilities**: What the evidence shows CANNOT be true
- **Missing evidence**: What should exist but doesn't (significance?)
- **Demonstrative opportunities**: How to visually present evidence for impact

**8. STRATEGIC BATTLEPLAN**
- **Opening statement hooks** (5 different approaches):
  * Emotional/visceral
  * Dramatic fact
  * Rhetorical question
  * Vivid scene recreation
  * Moral imperative
- **Closing themes** (3 comprehensive approaches with full structure)
- **Cross-examination targets**: Top 5 witnesses to destroy + specific attack plans
- **"Eureka moments"**: The 3-5 facts that create breakthroughs when properly presented
- **Zingers & memorable lines** (15-20 one-liners for key moments - quote-based)
- **Objection strategy**: When to object, when to let it go
- **Jury psychology**: What this jury will care about most
- **Win conditions summary**: If you accomplish X, Y, Z - you win
- **Loss prevention**: The 3 things that will lose this case if not addressed

**9. CASE THEORY SUMMARY**
- **Prosecution in one paragraph**: Their best possible case
- **Defense in one paragraph**: Their best possible case
- **Likely outcome prediction**: Who wins and why (based on evidence strength)
- **Wild card factors**: Unpredictable elements that could swing the case

===CASE PACKET===
{case_text_processed}
===END===

Provide championship-winning depth. Think strategically, psychologically, and emotionally. Find angles others miss.""",

            "Key Facts Only": f"""Extract 25 STRATEGICALLY CRITICAL facts with championship-level analysis.

For EACH fact:

**FACT #X: [Dramatic, specific statement of fact]**
- **Quote**: "[Exact quote from case]"
- **Source**: [Witness/Exhibit]
- **Surface meaning**: [What it literally says]
- **Deeper implications**: [What this REALLY means - read between lines]
- **Legal significance**: [Which elements proven/disproven + strength]
- **Psychological dimension**: [What this reveals about motive, credibility, character]
- **Strategic weaponization**: [Exactly how to use this to win]
- **Weakness**: [How opposition attacks this]
- **Emotional impact**: [How jurors FEEL about this]
- **Power phrase**: [Memorable 5-10 word summary for argument]
- **Connection to other facts**: [What other facts corroborate/contradict]

PRIORITIZE facts that:
- Create reasonable doubt or eliminate it
- Reveal motive, means, opportunity
- Show impossibility or certainty
- Demonstrate bias or credibility
- Contradict other testimony
- Have powerful emotional impact
- Constitute admissions or denials
- Establish timeline
- Show consciousness of guilt

===CASE PACKET===
{case_text_processed}
===END===

Go deep. Find the facts that WIN cases, not just describe them.""",

            "Legal Issues": f"""Identify and deeply analyze 5-7 key legal issues.

For each issue:

**ISSUE #X: [Clear legal question]**

**Elements & Standards**:
- Specific elements requiring proof
- Burden of proof (beyond reasonable doubt / preponderance)
- What this means PRACTICALLY for each side

**Proof Analysis**:
- **Prosecution/Plaintiff proof**: 
  * Specific evidence (quote-by-quote)
  * Strength rating (Strong/Solid/Moderate/Weak/Fatal)
  * Why this meets/doesn't meet burden
- **Defense counter-proof**:
  * Specific evidence creating doubt
  * Strength rating
  * Why this creates reasonable doubt / rebuts claim

**Strategic Battle**:
- **Prosecution approach**: How to argue this wins
- **Defense approach**: How to argue this fails / creates doubt
- **Key disputed facts**: What facts determine this element
- **Credibility issues**: Whose testimony matters most
- **Likely ruling**: Judge's likely view of evidence strength

**Argument Framing**:
- **Prosecution catchphrase**: How to frame this for plaintiff
- **Defense catchphrase**: How to frame this for defense

**Winning this issue**:
- If prosecution wins this: [Impact on case]
- If defense wins this: [Impact on case]
- **Critical**: Is this THE issue that determines the case?

===CASE PACKET===
{case_text_processed}
===END===

Analyze with championship depth.""",

            "Prosecution Arguments": f"""Develop 7 CHAMPIONSHIP-CALIBER prosecution arguments.

For EACH argument:

**ARGUMENT #X: [Compelling 3-6 word title]**

**One-Sentence Theme**: [Powerful statement to repeat]

**Narrative Framing**: [2-3 sentences: How does this fit the story? Why does it matter humanly?]

**Evidence Foundation** (build piece by piece):
1. Witness testimony: "[Quote]" - [Witness] → Establishes [fact]
2. Corroborating evidence: [Exhibit/other witness] → Confirms [fact]
3. Additional support: [More evidence] → Strengthens [conclusion]
**Strength rating**: [Strong/Solid/Moderate] and why

**Psychological Dimension**:
- What this reveals about defendant's state of mind
- Why jurors will find this compelling
- Emotional connection to justice

**Legal Impact**:
- Which elements this proves
- How strongly (percentage estimate of proof)
- What this accomplishes legally

**Power Phrases** (5-7 memorable lines for this argument):
1. "[Catchphrase based on case facts]"
2. "[Rhetorical question]"
3. "[Repetition for emphasis]"
4. "[Contrast: Not X, but Y]"
5. "[Vivid imagery]"

**Defense Counter-Strategy**:
- How defense WILL attack: [Specific approach]
- Their best evidence against this: [What they'll use]

**Prosecution Rebuttal Plan**:
- Response to defense attack: [Specific counter]
- Impeachment opportunities: [Witnesses to undermine]
- Reinforcement: [How to strengthen in rebuttal]

**Delivery Strategy**:
- **Opening**: How to introduce this argument
- **Pacing**: When to slow down, when to speed up
- **Emphasis**: Which phrases to stress
- **Silence**: Where to pause for effect
- **Exhibits**: When to show evidence
- **Closing climax**: How to end this argument powerfully

**Championship Edge**:
- Hidden strength others miss: [Subtle advantage]
- How to make this UNFORGETTABLE: [Specific technique]

===CASE PACKET===
{case_text_processed}
===END===

Make each argument a championship winner.""",

            "Defense Arguments": f"""Develop 7 CHAMPIONSHIP-CALIBER defense arguments creating reasonable doubt.

For EACH argument:

**ARGUMENT #X: [Compelling 3-6 word title emphasizing doubt]**

**One-Sentence Theme**: [Powerful reasonable doubt statement]

**Doubt Narrative**: [2-3 sentences: How does this create doubt? Why should jurors hesitate?]

**Evidence for Doubt** (build piece by piece):
1. Defense evidence: "[Quote]" - [Witness/Exhibit] → Shows [alternative/gap]
2. Prosecution weakness: [What they CAN'T prove] → Creates [doubt]
3. Contradiction: [Conflicting evidence] → Undermines [prosecution claim]
**Doubt strength**: [Strong/Solid/Moderate] and why

**Reasonable Doubt Dimensions**:
- Alternative explanation that makes sense
- Gaps in prosecution case
- Human nature considerations
- Why "beyond reasonable doubt" not met

**Burden Emphasis**:
- What prosecution MUST prove
- What they FAILED to prove
- Why this gap matters

**Power Phrases** (5-7 doubt-emphasizing lines):
1. "[Doubt catchphrase from case]"
2. "[Question exposing weakness]"
3. "[Alternative possibility]"
4. "[Burden reminder: They must prove X, they didn't]"
5. "[Presumption of innocence emphasis]"

**Prosecution Counter-Strategy**:
- How prosecution WILL respond: [Specific]
- Their best counter-evidence: [What they'll use]

**Defense Rebuttal Plan**:
- Response to prosecution: [Specific counter]
- Reinforcement of doubt: [How to strengthen]
- Impeachment opportunities: [Prosecution witnesses to undermine]

**Delivery Strategy**:
- **Opening**: How to frame this doubt argument
- **Tone**: Measured, reasonable, not desperate
- **Emphasis**: Burden of proof reminders
- **Silence**: Pauses to let doubt sink in
- **Evidence**: When to highlight gaps
- **Closing**: How to leave doubt lingering

**Championship Edge**:
- Hidden doubt others miss: [Subtle reasonable doubt]
- How to make doubt UNDENIABLE: [Technique]

===CASE PACKET===
{case_text_processed}
===END===

Create reasonable doubt that wins acquittals.""",

            "Witness Questions": f"""Generate CHAMPIONSHIP-LEVEL strategic examination for: {witness_name_input}

**COMPREHENSIVE WITNESS ANALYSIS**

**Profile**:
- Role: [What they know and why they matter]
- Credibility: [Rate 1-10 with detailed analysis]
- Bias/motive: [Any reason to lie or slant?]
- Demeanor prediction: [How they'll come across]
- Psychological profile: [Confident? Nervous? Defensive? Deceptive?]
- **5-word characterization**: [Memorable description]

**Testimony Deep-Dive**:
- What they claim (exact quotes)
- Strengths in their story
- Weaknesses/contradictions
- Impossible/implausible elements
- What they're hiding/not saying

**DIRECT EXAMINATION (15 strategic questions)**

Build this structure:
1. **Foundation** (3 questions): Who they are, why they know
2. **Timeline** (2-3 questions): When/where foundation
3. **Key facts** (7-8 questions): Building narrative systematically
4. **Emotional moment** (1-2 questions): Humanizing connection
5. **Credibility building** (2 questions): Why they're trustworthy

For each question provide:
- The question (open-ended, non-leading)
- **Purpose**: What this establishes
- **Expected answer**: What they should say
- **Follow-up opportunity**: Where to go next
- **Delivery note**: Tone, pacing
- **"Money moment"**: Which questions are most important

**CROSS-EXAMINATION (15 strategic questions)**

Build this attack:
1. **Control establishment** (2-3 questions): Non-threatening setup
2. **Commitment** (2-3 questions): Lock them into positions
3. **Impeachment** (7-8 questions): Systematic destruction
4. **Final blow** (2-3 questions): Devastating finale

For each question provide:
- The question (leading, one fact)
- **Strategic goal**: What you're accomplishing
- **Expected answer**: Likely response
- **If they resist**: Follow-up if they don't cooperate
- **Impeachment trigger**: How this sets up destruction
- **Delivery note**: Tone (aggressive? Calm?)

**IMPEACHMENT STRATEGY**:
- **Top 3 impeachment targets**: Specific contradictions
- **Prior inconsistent statements**: What they said before vs. now
- **Bias exploitation**: How to highlight their motive to lie
- **Plausibility attack**: Pointing out impossible elements

**POWER MOVES**:
- Best "gotcha" questions (3-5)
- When to use silence (after which questions)
- When to show exhibits (timing)
- Tone shifts (when to get aggressive vs. stay calm)
- **Killer question**: The one question that destroys them

**REDIRECT EXAMINATION (if needed)**:
- 3-5 questions to rehabilitate if this is your witness
- How to handle if they're damaged on cross

===CASE PACKET===
{case_text_processed}
===END===

Championship-level examination strategy.""",

            "Opening Statement Ideas": f"""Draft CHAMPIONSHIP-LEVEL opening frameworks for BOTH sides.

**PROSECUTION/PLAINTIFF OPENING** (7-9 minutes)

**1. HOOK (45-60 seconds)** - Choose best approach:

**Option A: Visceral/Emotional Opening**
- [Create vivid mental image of key moment]
- [Use present tense, sensory details]
- [2-3 powerful sentences]

**Option B: Dramatic Question**
- [Pose question that frames entire case]
- [Make them think about answer]
- [2-3 questions building]

**Option C: Powerful Quote**
- "[Quote from case that captures everything]"
- [Explain why this matters]
- [Connect to theme]

**Option D: Silence Opening**
- [Start with 3-second pause]
- [Then powerful statement]
- [Explain significance]

**2. THEME STATEMENT** (repeat 3+ times in opening)
- [ONE powerful sentence that captures case]
- [Make it emotional, not just factual]

**3. WHAT THIS CASE IS ABOUT** (1 minute)
- Charges explained (simple terms)
- What prosecution will prove
- Why it matters (not just legally, humanly)

**4. THE STORY** (4-5 minutes - present tense, chronological)

Create emotional arc:
- **Beginning**: [Set the scene - before the incident]
- **Rising tension**: [Events leading up]
- **The moment**: [The critical incident - slow down here]
- **Aftermath**: [Consequences, impact]

Key techniques:
- Use PRESENT TENSE throughout
- Sensory details (what people saw/heard/felt)
- Emotional beats (how people reacted)
- Quote key witnesses
- Show defendant's actions/state of mind
- Build to emotional climax

**Repetition device**: [Phrase to repeat 2-3 times in story for emphasis]

**5. THE EVIDENCE** (2-3 minutes)
- Witness by witness (brief - who they are, what they'll say, why credible)
- Key exhibits (what they prove)
- Frame each as piece of puzzle

**6. PREVIEW OF DEFENSE** (30 seconds)
- "Defense will tell you [X]..."
- "But the evidence shows [Y]..."
- Pre-empt their best argument

**7. CLOSING POWER STATEMENT** (30 seconds)
- Return to theme
- Emotional call
- Powerful final 1-2 sentences

**CHAMPIONSHIP TECHNIQUES TO USE**:
- Rule of three (group things in threes)
- Contrast ("not X, but Y")
- Present tense for immediacy
- Strategic silence (pause before/after key points)
- Vary pacing (slow for important, faster for transitions)
- Eye contact on emotional moments
- Physical positioning (step closer for key points)

**15-20 POWER PHRASES** to choose from:
[Generate 15-20 memorable lines based on case facts]

---

**DEFENSE OPENING** (7-9 minutes)

**1. HOOK** (45-60 seconds) - Choose best approach:

**Option A: Presumption of Innocence**
- [Powerful reminder of bedrock principle]
- [Why this matters in THIS case]
- [2-3 sentences]

**Option B: Prosecution's Burden**
- [What they MUST prove]
- [How high the bar is]
- [Why they won't clear it]

**Option C: Alternative Frame**
- [Different way to see same events]
- [Question their narrative]
- [Introduce doubt immediately]

**Option D: Empathy Opening**
- [Humanize defendant]
- [This is a person, not just a case]
- [Create identification]

**2. THEME STATEMENT** (reasonable doubt focus)
- [ONE powerful sentence about doubt]
- [Repeat 3+ times]

**3. BURDEN & STANDARD** (1 minute)
- Beyond reasonable doubt explained (what it MEANS)
- Presumption of innocence (starts innocent, stays innocent unless...)
- Prosecution's burden (they must prove, we prove nothing)

**4. DEFENSE STORY** (4-5 minutes)

Two approaches - choose best:

**Approach A: Alternative Narrative**
- [Tell different story of same events]
- [Present tense, emotional]
- [Show reasonable alternative]

**Approach B: Systematic Doubt Creation**
- [Go through prosecution case]
- [Point out gaps/problems one by one]
- [Build cumulative doubt]

Key techniques:
- Reasonable, not desperate tone
- Point out missing evidence
- Highlight contradictions
- Show alternative explanations
- Question motivations
- Emphasize burden throughout

**Repetition device**: [Phrase like "They can't prove..." or "Reasonable doubt exists when..." repeated 2-3 times]

**5. WHAT PROSECUTION MUST PROVE** (2 minutes)
- Element by element
- For each: "They must prove X beyond reasonable doubt... but..."
- Show gaps in their proof

**6. DEFENSE EVIDENCE** (if presenting)
- Defense witnesses (who and what they'll show)
- Evidence supporting defense
- Frame as creating reasonable doubt

**7. CLOSING POWER STATEMENT** (30 seconds)
- Return to presumption of innocence
- Reasonable doubt exists
- Must acquit
- Powerful final sentence

**CHAMPIONSHIP TECHNIQUES**:
- Calm, measured tone (confidence, not desperation)
- Frequent burden reminders
- Use "reasonable person" standard
- Connect with jurors ("You know that...")
- Respect for prosecution (don't attack, just show weaknesses)
- Strategic silence on their weak points

**15-20 POWER PHRASES** for defense:
[Generate 15-20 reasonable doubt lines from case]

===CASE PACKET===
{case_text_processed}
===END===

Championship openings that win from the start.""",

            "Closing Statement Ideas": f"""Draft CHAMPIONSHIP-LEVEL closing argument frameworks for BOTH sides.

**PROSECUTION/PLAINTIFF CLOSING** (12-15 minutes)

**STRUCTURE**:

**1. OPENING HOOK** (1-2 minutes)
- **Return to opening theme**: "[Theme statement]"
- **Emotional reconnection**: Remind why this matters
- **What we said we'd prove**: "In opening, I told you we'd prove X, Y, Z..."
- **What we DID prove**: "And we did. Here's how..."

**2. THE STORY - RETOLD** (2-3 minutes)
- Reconstruct events with PROVEN facts
- Use PRESENT TENSE
- Quote key witnesses
- Show exhibits
- Make it VIVID and EMOTIONAL
- Build to climax moment
- Show impact/harm

**3. ELEMENTS PROVEN** (5-7 minutes) - CORE OF CLOSING

For EACH element:

**ELEMENT #1: [State element]**

**What we must prove**: [Explain in simple terms]

**How we proved it**:
- Witness 1: "[Quote from testimony]" - Proves [aspect]
- Witness 2: "[Quote]" - Corroborates and adds [aspect]
- Exhibit X: [What it shows] - Confirms [aspect]
- [Any additional proof]

**Why this is beyond reasonable doubt**:
- [Multiple witnesses agree]
- [Physical evidence confirms]
- [Defendant's own words/actions]
- [No reasonable alternative explanation]

**Power phrase**: "[Memorable summary]"

**After each element**: "That's PROVEN. Beyond reasonable doubt. Check."

[Repeat for ALL elements]

**4. CREDIBILITY** (2-3 minutes)

**Why our witnesses are credible**:
- [Specific credibility factors]
- No motive to lie
- Corroboration from multiple sources
- Consistent with physical evidence
- Human and honest
- [Quote powerful testimony]

**Why defense witnesses are NOT credible**:
- [Specific problems]
- Bias/motive
- Contradictions
- Implausible claims
- Contradicted by physical evidence

**5. ADDRESSING DEFENSE** (2 minutes)

"Defense told you [X]..."
"But that's not reasonable doubt, that's [Y]..."

For their 3 best arguments:
- State it fairly
- Show why it fails
- Use evidence to dismantle
- Return to burden met

**6. REASONABLE DOUBT** (1 minute)
- "Reasonable doubt is not ANY doubt..."
- "It's not a imagined doubt..."
- "It's a doubt based on REASON and EVIDENCE..."
- "And here, there IS NO reasonable doubt because..."

**7. THE STAKES** (1-2 minutes)
- Why this matters
- Impact on victim/community
- Justice requires action
- Accountability necessary
- [Emotional appeal - measured, not manipulative]

**8. FINAL APPEAL** (1 minute)
- Return to opening theme one last time
- Summarize in 2-3 sentences
- Call to action
- **MIC DROP MOMENT**: [Powerful final sentence that rings in ears]

**CHAMPIONSHIP TECHNIQUES**:
- Repetition (theme/phrases repeated 5+ times)
- Rule of three
- Build to crescendo
- Strategic silence (after powerful points)
- Vary pacing (slow on key evidence)
- Use hands to count elements
- Step closer for emotional moments
- Vocal variation (louder for key points)

**25-30 POWER PHRASES** for prosecution closing:
[Generate 25-30 memorable lines from case]

---

**DEFENSE CLOSING** (12-15 minutes)

**STRUCTURE**:

**1. OPENING** (1-2 minutes)
- **Presumption of innocence reminder**: Still innocent unless...
- **Theme return**: "[Reasonable doubt theme]"
- **What this case is REALLY about**: Not emotions, but evidence and burden
- **What prosecution MUST do**: Prove every element beyond reasonable doubt

**2. BEYOND REASONABLE DOUBT** (1 minute)
- Explain what it REALLY means
- How HIGH this bar is
- Why it exists (protects us all)
- "Prosecution must prove X, Y, Z..."
- "If they fail on ANY element, you MUST acquit..."

**3. ELEMENT-BY-ELEMENT REASONABLE DOUBT** (5-7 minutes) - CORE

For EACH element:

**ELEMENT #1: [State element]**

**What they must prove**: [Explain clearly]

**Why they DIDN'T prove it beyond reasonable doubt**:
- **Gap 1**: [What evidence is missing]
- **Contradiction 1**: [Witness inconsistency]
- **Alternative explanation**: [Reasonable different interpretation]
- **Credibility problem**: [Why witness not believable]
- [Physical evidence doesn't support]

**Specific reasonable doubts**:
1. [Specific doubt with evidence]
2. [Another specific doubt]
3. [Another]

**Power phrase**: "[Memorable reasonable doubt summary]"

**After each element**: "That's not proof beyond reasonable doubt. That's reasonable doubt. Period."

[Repeat for ALL elements - show doubt in EACH]

**4. CREDIBILITY** (2-3 minutes)

**Problems with prosecution witnesses**:
- [Specific witness 1]: [Bias, contradiction, implausibility]
- [Specific witness 2]: [Problems with their testimony]
- [Quote contradictions]
- [Show motive to lie/exaggerate]

**Defense witnesses ARE credible**:
- [No motive to lie]
- [Consistent]
- [Corroborated]
- [Makes sense]

**5. PROSECUTION'S CASE - SYSTEMATIC DECONSTRUCTION** (2-3 minutes)

"Let's look at what prosecution DIDN'T prove..."

- Missing evidence (what should exist but doesn't)
- Timeline problems (what doesn't add up)
- Contradictions (prosecution witnesses contradicting each other)
- Alternative explanations (other ways to interpret evidence)
- Burden failures (where they fall short)

"When you add all this up, that's not proof. That's REASONABLE DOUBT."

**6. PRE-EMPTING PROSECUTION REBUTTAL** (1 minute)
- "Prosecution will stand up and say [X]..."
- "Don't be distracted..."
- "The burden is still on THEM..."
- "Reasonable doubt STILL exists..."

**7. THE STAKES** (1 minute)
- Why presumption of innocence matters
- Protection for all of us
- Can't convict on speculation/emotion
- Must have proof
- Reasonable doubt protects the innocent

**8. FINAL APPEAL** (1 minute)
- **Return to theme**: "[Reasonable doubt statement]"
- **Burden reminder**: "They must prove. They didn't."
- **Your duty**: "When reasonable doubt exists, you MUST acquit."
- **Final sentence**: [Powerful statement about reasonable doubt / innocence]

**CHAMPIONSHIP TECHNIQUES**:
- Calm, reasonable tone (not desperate)
- Frequent burden reminders (every 2-3 minutes)
- Use "reasonable person" language
- Connect with jurors directly ("You know...")
- Count off doubts (use fingers)
- Strategic silence on prosecution's weak points
- Measured emotion (indignation at burden failure, not anger)

**25-30 POWER PHRASES** for defense closing:
[Generate 25-30 reasonable doubt lines from case]

**REBUTTAL CONSIDERATIONS** (if applicable):
- What prosecution will say in rebuttal
- Pre-emptive responses
- Final burden reminders

===CASE PACKET===
{case_text_processed}
===END===

Championship closings that win verdicts."""
        }
        
        with st.spinner("🤔 Conducting deep championship-level analysis..."):
            # INCREASED TOKEN LIMITS for deeper analysis (using 0.015 budget)
            if analysis_type == "Full Case Analysis":
                max_tokens_to_use = 3500  # Increased from 2600
            elif analysis_type in ["Key Facts Only", "Prosecution Arguments", "Defense Arguments"]:
                max_tokens_to_use = 3200  # Increased from 2600
            elif analysis_type in ["Opening Statement Ideas", "Closing Statement Ideas"]:
                max_tokens_to_use = 3800  # Increased from 2400
            elif analysis_type == "Legal Issues":
                max_tokens_to_use = 2800
            else:
                max_tokens_to_use = 2400
            
            result, tokens = call_openai(
                base_system, 
                prompts[analysis_type],
                max_tokens=max_tokens_to_use,
                temperature=0.15  # Lowered for better accuracy
            )
            
            if result:
                cost = estimate_cost(tokens)
                st.session_state.total_cost += cost
                
                st.success("✅ Championship-Level Analysis Complete!")
                st.markdown("---")
                st.markdown("### 📊 Results")
                st.markdown(result)
                
                st.download_button(
                    "📥 Download Analysis",
                    data=result,
                    file_name=f"analysis_{analysis_type.replace(' ', '_').lower()}.txt",
                    mime="text/plain"
                )
                
                st.markdown(f'<p class="cost-display">Analysis cost: ${cost:.4f} (Championship depth analysis)</p>', unsafe_allow_html=True)

# ==========================================
# MODE 2: CROSS-EXAMINATION SIMULATOR (FIXED BUTTON ERROR)
# ==========================================

elif mode == "Cross-Examination Simulator":
    
    st.subheader("🎭 Cross-Examination Practice")
    
    if not st.session_state.cross_exam_mode:
        
        st.markdown("**Step 1: Upload case packet**")
        uploaded_file = st.file_uploader(
            "Upload Case PDF",
            type=['pdf'],
            key="crossexam_upload"
        )
        
        case_text_input = st.text_area(
            "Or paste case text:",
            height=150,
            key="crossexam_text"
        )
        
        if uploaded_file:
            case_text = extract_text_from_pdf(uploaded_file)
        else:
            case_text = case_text_input
        
        st.markdown("**Step 2: Enter witness name**")
        witness_name = st.text_input(
            "Witness to question:",
            placeholder="e.g., Alex Martinez",
            key="witness_input"
        )
        
        st.markdown("**Step 3: Choose your role**")
        exam_type = st.radio(
            "Are you conducting:",
            ["Cross-Examination (opposing witness)", "Direct Examination (your witness)"]
        )
        
        if st.button("🎬 Start Simulation", type="primary"):
            if not case_text or len(case_text) < 50:
                st.error("⚠️ Please provide case text")
            elif not witness_name:
                st.error("⚠️ Please enter witness name")
            else:
                with st.spinner("🔍 Processing case..."):
                    case_text_cleaned = aggressive_preprocess(case_text)
                    if len(case_text_cleaned) > 12000:
                        case_text_processed = smart_summarize_case(case_text_cleaned)
                    else:
                        case_text_processed = case_text_cleaned
                
                st.session_state.case_text = case_text_processed
                st.session_state.witness_name = witness_name
                st.session_state.exam_type = exam_type
                st.session_state.cross_exam_mode = True
                st.session_state.conversation_history = []
                
                with st.spinner("🧠 Preparing witness..."):
                    setup_prompt = f"""You are {witness_name}, a WITNESS in this case.

RULES:
1. Answer ONLY based on {witness_name}'s witness statement
2. Stay 100% consistent
3. If unknown: "I don't know" or "I don't recall"
4. For improper questions: "OBJECTION: [reason]"
5. Do NOT invent facts

Exam type: {exam_type}

===CASE===
{case_text_processed}
===END===

You are {witness_name}."""
                    
                    st.session_state.witness_context = setup_prompt
                
                st.rerun()
    
    else:
        st.success(f"🎭 **Simulating: {st.session_state.witness_name}**")
        
        st.markdown("### 💬 Examination Transcript")
        
        for i, exchange in enumerate(st.session_state.conversation_history):
            st.markdown(f"**Q{i+1}:** {exchange['question']}")
            if "OBJECTION" in exchange['answer']:
                st.error(f"⚖️ {exchange['answer']}")
            else:
                st.info(f"**A:** {exchange['answer']}")
        
        st.markdown("---")
        user_question = st.text_input(
            "Your question:",
            placeholder="Ask your question...",
            key=f"question_{len(st.session_state.conversation_history)}"
        )
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("📤 Ask Question", key="ask_question_btn") and user_question:
                with st.spinner("🤔 Witness responding..."):
                    recent_history = st.session_state.conversation_history[-3:]
                    conversation = "\n".join([
                        f"Q: {ex['question']}\nA: {ex['answer']}"
                        for ex in recent_history
                    ])
                    
                    full_prompt = f"""{st.session_state.witness_context}

Previous:
{conversation}

New question: {user_question}

Respond as {st.session_state.witness_name}."""
                    
                    system_msg = f"You are {st.session_state.witness_name}, a witness. Answer ONLY based on testimony."
                    
                    answer, tokens = call_openai(
                        system_msg, 
                        full_prompt, 
                        max_tokens=180,
                        temperature=0.3
                    )
                    
                    if answer:
                        cost = estimate_cost(tokens)
                        st.session_state.total_cost += cost
                        
                        st.session_state.conversation_history.append({
                            'question': user_question,
                            'answer': answer
                        })
                        st.rerun()
        
        with col2:
            if len(st.session_state.conversation_history) >= 3:
                if st.button("📋 Get Feedback", key="get_feedback_btn"):
                    with st.spinner("🎓 Analyzing..."):
                        questions_only = [ex['question'] for ex in st.session_state.conversation_history]
                        
                        feedback_prompt = f"""Provide feedback on this {st.session_state.exam_type.split()[0]} examination.

TRANSCRIPT:
{chr(10).join([f"Q{i+1}: {q}" for i, q in enumerate(questions_only)])}

Provide: overall assessment, strengths, improvements, question-by-question notes, rules followed/violated, championship tips, suggested questions."""

                        feedback, tokens = call_openai(
                            "You are an expert mock trial coach.",
                            feedback_prompt,
                            max_tokens=1200,
                            temperature=0.3
                        )
                        
                        if feedback:
                            cost = estimate_cost(tokens)
                            st.session_state.total_cost += cost
                            
                            st.markdown('<div class="feedback-section">', unsafe_allow_html=True)
                            st.markdown("## 🎓 Coach Feedback")
                            st.markdown(feedback)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.download_button(
                                "📥 Download Feedback",
                                data=feedback,
                                file_name=f"feedback_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                mime="text/plain",
                                key="download_feedback"
                            )
                            
                            st.markdown(f'<p class="cost-display">Feedback: ${cost:.4f}</p>', unsafe_allow_html=True)
            else:
                if st.button("📋 Get Feedback", key="get_feedback_disabled_btn", disabled=True):
                    pass
                st.caption("Ask at least 3 questions first")
        
        with col3:
            if st.button("🔄 End", key="end_exam_btn"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# MODE 3: OBJECTION PRACTICE (COMPLETELY FIXED WITH PROPER RULES)
# ==========================================

else:  # Objection Practice
    
    st.subheader("⚖️ Objection Practice")
    st.markdown("Learn when to object by practicing with realistic examination questions based on witness testimony.")
    
    if not st.session_state.objection_mode:
        
        st.markdown("**Step 1: Upload case packet**")
        uploaded_file = st.file_uploader(
            "Upload Case PDF",
            type=['pdf'],
            key="objection_upload"
        )
        
        case_text_input = st.text_area(
            "Or paste case text:",
            height=150,
            key="objection_text_input"
        )
        
        if uploaded_file:
            case_text = extract_text_from_pdf(uploaded_file)
        else:
            case_text = case_text_input
        
        st.markdown("**Step 2: Enter witness name**")
        witness_name = st.text_input(
            "Witness name:",
            placeholder="e.g., Alex Martinez",
            key="objection_witness_input"
        )
        
        st.markdown("**Step 3: Choose examination type**")
        exam_type_input = st.radio(
            "Type of examination:",
            ["Direct Examination", "Cross-Examination"],
            key="exam_type_radio"
        )
        
        if st.button("🎯 Start Objection Practice", type="primary"):
            if not case_text or len(case_text) < 50:
                st.error("⚠️ Please provide case text")
            elif not witness_name:
                st.error("⚠️ Please enter witness name")
            else:
                with st.spinner("🔍 Extracting witness statement..."):
                    case_text_cleaned = aggressive_preprocess(case_text)
                    witness_statement = extract_witness_statement(case_text_cleaned, witness_name)
                
                st.session_state.objection_case_text = case_text_cleaned
                st.session_state.witness_statement = witness_statement
                st.session_state.objection_witness = witness_name
                st.session_state.saved_objection_exam_type = exam_type_input
                st.session_state.objection_mode = True
                st.session_state.objection_history = []
                st.session_state.current_question = None
                st.session_state.show_result = False
                st.session_state.question_count = 0
                
                st.rerun()
    
    else:
        st.success(f"🎯 **Practicing Objections - {st.session_state.saved_objection_exam_type} of {st.session_state.objection_witness}**")
        
        # Display score
        if len(st.session_state.objection_history) > 0:
            correct = sum(1 for item in st.session_state.objection_history if item['correct'])
            total = len(st.session_state.objection_history)
            percentage = (correct / total * 100) if total > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Questions Practiced", total)
            with col2:
                st.metric("Correct", correct)
            with col3:
                st.metric("Accuracy", f"{percentage:.0f}%")
            
            st.markdown("---")
        
        # Generate new question if needed
        if st.session_state.current_question is None and not st.session_state.show_result:
            with st.spinner("🤔 Generating practice question..."):
                st.session_state.question_count += 1
                should_be_proper = random.choice([True, False])
                
                # RESEARCH-BASED OBJECTION RULES
                if st.session_state.saved_objection_exam_type == "Direct Examination":
                    if should_be_proper:
                        rule_instruction = """GENERATE A PROPER DIRECT EXAMINATION QUESTION:

DIRECT EXAMINATION RULES (proper questions):
✅ Open-ended questions that don't suggest answers
✅ Who/What/Where/When/How questions
✅ "Describe...", "Explain...", "Tell us about..."
✅ Allow witness to tell their story in their own words
✅ Non-leading questions

EXAMPLES OF PROPER DIRECT QUESTIONS:
- "What did you observe?"
- "Where were you at that time?"
- "Describe what happened next."
- "How did you react?"
- "What did you hear?"
- "Tell us what you saw."

DO NOT USE: "correct?", "didn't you?", "isn't it true that...", or any phrasing that suggests the answer.

Generate an open-ended question that lets the witness tell their story."""
                    else:
                        rule_instruction = """GENERATE AN IMPROPER DIRECT EXAMINATION QUESTION:

LEADING QUESTIONS ARE IMPROPER ON DIRECT EXAMINATION.

Leading = Suggests the answer = IMPROPER on DIRECT

EXAMPLES OF IMPROPER/LEADING QUESTIONS ON DIRECT:
- "You were at the store, correct?" ← LEADING (suggests "yes")
- "You saw the defendant, didn't you?" ← LEADING
- "Isn't it true that you heard a noise?" ← LEADING
- "You felt scared, right?" ← LEADING
- "It was 3pm when this happened, wasn't it?" ← LEADING

ANY question that:
- Ends with "correct?", "right?", "didn't you?", "weren't you?"
- Starts with "Isn't it true that..."
- Suggests the answer you want
= LEADING = IMPROPER ON DIRECT

Generate a leading question (one that suggests the answer). This will be IMPROPER."""
                else:  # Cross-Examination
                    if should_be_proper:
                        rule_instruction = """GENERATE A PROPER CROSS-EXAMINATION QUESTION:

CROSS-EXAMINATION RULES (proper questions):
✅ Leading questions that suggest answers
✅ Control the witness
✅ Yes/no questions
✅ Questions ending in: "correct?", "right?", "didn't you?", "weren't you?"
✅ Questions starting with: "Isn't it true that...", "You [statement], correct?"
✅ One fact per question

EXAMPLES OF PROPER CROSS QUESTIONS:
- "You were 100 feet away, correct?"
- "You didn't see the defendant's face, did you?"
- "You told police you weren't sure, didn't you?"
- "Isn't it true that you were facing the other direction?"
- "You dislike the defendant, don't you?"
- "You never mentioned this detail to anyone before today, correct?"

These are LEADING questions = PROPER on CROSS

Generate a leading question (one that suggests the answer and controls the witness)."""
                    else:
                        rule_instruction = """GENERATE AN IMPROPER CROSS-EXAMINATION QUESTION:

OPEN-ENDED QUESTIONS ARE IMPROPER ON CROSS-EXAMINATION.

Open-ended = Doesn't lead = Allows witness to explain = IMPROPER on CROSS

EXAMPLES OF IMPROPER/OPEN-ENDED QUESTIONS ON CROSS:
- "What did you see?" ← OPEN-ENDED (not leading)
- "Why did you go there?" ← OPEN-ENDED
- "Describe what happened." ← OPEN-ENDED
- "How did you feel?" ← OPEN-ENDED
- "Explain your actions." ← OPEN-ENDED
- "Tell us about that day." ← OPEN-ENDED

ANY question that:
- Starts with What/Why/How/Describe/Explain/Tell
- Allows witness to give lengthy answer
- Doesn't control or suggest the answer
= OPEN-ENDED = IMPROPER ON CROSS

Also improper: Compound questions, argumentative questions

Generate an open-ended question. This will be IMPROPER."""

                question_prompt = f"""You are an expert mock trial judge generating practice questions.

{rule_instruction}

WITNESS: {st.session_state.objection_witness}

WITNESS STATEMENT (use ONLY these facts - don't invent):
{st.session_state.witness_statement}

Based on facts from the witness statement above, generate ONE question.

Output format (EXACT):
QUESTION: [Your question here]
RULING: {"PROPER" if should_be_proper else "IMPROPER"}
REASON: {("[Explain why this open-ended/non-leading question is proper for Direct Examination]" if should_be_proper and st.session_state.saved_objection_exam_type == "Direct Examination" else "[Explain why this leading question is improper for Direct Examination - it suggests the answer]" if not should_be_proper and st.session_state.saved_objection_exam_type == "Direct Examination" else "[Explain why this leading question is proper for Cross-Examination - it controls the witness]" if should_be_proper else "[Explain why this open-ended question is improper for Cross-Examination - it doesn't lead]")}
EXPLANATION: [Brief explanation of the rule]

Generate ONE question based ONLY on facts from witness statement."""

                system_msg = f"""You are an expert mock trial judge who DEEPLY understands examination rules.

FUNDAMENTAL RULES YOU KNOW:

**DIRECT EXAMINATION:**
- PROPER: Open-ended, non-leading questions (What/Where/When/How/Describe)
- IMPROPER: Leading questions (suggests answer, "correct?", "didn't you?", "isn't it true")

**CROSS-EXAMINATION:**
- PROPER: Leading questions (suggests answer, "correct?", "didn't you?", "isn't it true")
- IMPROPER: Open-ended questions (What/Why/How/Describe/Explain)

CRITICAL: "You were X, correct?" = LEADING
- IMPROPER on Direct Examination
- PROPER on Cross-Examination

"Isn't it true that..." = LEADING
- IMPROPER on Direct
- PROPER on Cross

Generate questions using ONLY facts from witness statement. Never invent facts."""
                
                response, tokens = call_openai(
                    system_msg,
                    question_prompt,
                    max_tokens=400,
                    temperature=0.6
                )
                
                if response:
                    cost = estimate_cost(tokens)
                    st.session_state.total_cost += cost
                    st.session_state.current_question = response
                    st.rerun()
        
        # Display current question and handle responses
        if st.session_state.current_question and not st.session_state.show_result:
            lines = st.session_state.current_question.split('\n')
            question_text = ""
            ruling = ""
            reason = ""
            explanation = ""
            
            for line in lines:
                if "QUESTION:" in line:
                    question_text = line.split("QUESTION:")[-1].strip()
                    question_text = question_text.replace("Attorney asks:", "").strip()
                    question_text = question_text.strip('"').strip("'").strip()
                elif "RULING:" in line:
                    ruling = line.replace("RULING:", "").strip().upper()
                elif "REASON:" in line:
                    reason = line.replace("REASON:", "").strip()
                elif "EXPLANATION:" in line:
                    explanation = line.replace("EXPLANATION:", "").strip()
            
            if "PROPER" in ruling:
                ruling = "PROPER"
            elif "IMPROPER" in ruling:
                ruling = "IMPROPER"
            
            st.markdown("### 📝 Practice Question")
            st.markdown(f"**Attorney asks {st.session_state.objection_witness}:**")
            st.markdown(f"### \"{question_text}\"")
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ No Objection (Proper)", use_container_width=True, key="btn_proper"):
                    user_answer = "PROPER"
                    correct = (user_answer == ruling)
                    
                    st.session_state.objection_history.append({
                        'question': question_text,
                        'user_answer': user_answer,
                        'correct_answer': ruling,
                        'correct': correct,
                        'reason': reason,
                        'explanation': explanation
                    })
                    
                    st.session_state.show_result = True
                    st.rerun()
            
            with col2:
                if st.button("🚫 OBJECTION! (Improper)", use_container_width=True, key="btn_improper"):
                    user_answer = "IMPROPER"
                    correct = (user_answer == ruling)
                    
                    st.session_state.objection_history.append({
                        'question': question_text,
                        'user_answer': user_answer,
                        'correct_answer': ruling,
                        'correct': correct,
                        'reason': reason,
                        'explanation': explanation
                    })
                    
                    st.session_state.show_result = True
                    st.rerun()
        
        # Show result
        if st.session_state.show_result and len(st.session_state.objection_history) > 0:
            last_item = st.session_state.objection_history[-1]
            
            if last_item['correct']:
                st.markdown('<div class="correct-answer">', unsafe_allow_html=True)
                st.markdown("### ✅ Correct!")
                if last_item['correct_answer'] == "PROPER":
                    st.markdown(f"**This question is PROPER for {st.session_state.saved_objection_exam_type}.**")
                else:
                    st.markdown(f"**Objection sustained! This question is IMPROPER for {st.session_state.saved_objection_exam_type}.**")
                st.markdown(f"**Reason:** {last_item['reason']}")
                st.markdown(f"**Rule:** {last_item['explanation']}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="incorrect-answer">', unsafe_allow_html=True)
                st.markdown("### ❌ Incorrect")
                if last_item['correct_answer'] == "PROPER":
                    st.markdown(f"**Objection overruled. This question is PROPER for {st.session_state.saved_objection_exam_type}.**")
                else:
                    st.markdown(f"**You should have objected! This question is IMPROPER for {st.session_state.saved_objection_exam_type}.**")
                st.markdown(f"**Reason:** {last_item['reason']}")
                st.markdown(f"**Rule:** {last_item['explanation']}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button("➡️ Next Question", key="btn_next"):
                st.session_state.current_question = None
                st.session_state.show_result = False
                st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns([3, 1])
        
        with col2:
            if st.button("🏁 End Practice"):
                st.session_state.objection_mode = False
                st.session_state.objection_history = []
                st.session_state.current_question = None
                st.session_state.show_result = False
                st.session_state.question_count = 0
                st.rerun()
        
        # Show history
        if len(st.session_state.objection_history) > 0:
            with st.expander("📊 Practice History"):
                for i, item in enumerate(st.session_state.objection_history):
                    status = "✅" if item['correct'] else "❌"
                    st.markdown(f"**{status} Q{i+1}:** {item['question']}")
                    st.markdown(f"- Your answer: {item['user_answer']}")
                    st.markdown(f"- Correct answer: {item['correct_answer']}")
                    st.markdown(f"- {item['reason']}")
                    st.markdown("---")
        
        st.markdown(f'<p class="cost-display">Session cost: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)
        
        # Rules reference
        with st.expander("📖 Objection Rules Reference"):
            if st.session_state.saved_objection_exam_type == "Direct Examination":
                st.markdown("""
**DIRECT EXAMINATION RULES:**

✅ **PROPER Questions:**
- Open-ended questions
- What/Where/When/How/Describe/Explain
- "What did you see?"
- "Describe what happened."
- Lets witness tell story in their words

❌ **IMPROPER Questions (OBJECTION!):**
- Leading questions (suggest the answer)
- "You were there, correct?" ← LEADING
- "Isn't it true that..." ← LEADING
- "You saw X, didn't you?" ← LEADING
- Questions ending in "correct?", "right?", "didn't you?"

**Key Rule:** On Direct, you CANNOT lead your own witness.
""")
            else:
                st.markdown("""
**CROSS-EXAMINATION RULES:**

✅ **PROPER Questions:**
- Leading questions (suggest the answer)
- "You were there, correct?" ← LEADING = PROPER
- "Isn't it true that..." ← LEADING = PROPER
- "You didn't see X, did you?" ← LEADING = PROPER
- Questions that control the witness
- Yes/no questions

❌ **IMPROPER Questions (OBJECTION!):**
- Open-ended questions
- "What did you see?" ← NOT LEADING
- "Why did you do that?" ← NOT LEADING
- "Describe what happened." ← NOT LEADING
- Allows witness to explain freely

**Key Rule:** On Cross, you MUST lead and control the witness.
""")

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.caption("""
**About:** Championship-level AI-powered mock trial preparation tool.

**Disclaimer:** AI-generated analysis may contain errors. Always verify information.

*Python • Streamlit • OpenAI GPT-3.5 • Built by Vihaan Paka-Hegde*
""")