import streamlit as st
from openai import OpenAI
import PyPDF2
import io
import datetime

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

def smart_summarize_case(case_text):
    """
    Use AI to condense while preserving ALL legal content.
    FIXED: max_tokens reduced to 3800 (under 4096 limit)
    """
    if len(case_text) <= 18000:
        return case_text
    
    summary_prompt = f"""Extract ONLY legal case content from this document.

RULES:
1. INCLUDE all charges, parties, witnesses, dates, locations, events, evidence, testimony
2. PRESERVE exact names, numbers, quotes
3. KEEP all contradictions and disputed facts
4. EXCLUDE dedications, author info, competition rules, instructions

Output ONLY case facts. No preamble.

Document:
{case_text[:18000]}

Case content only:"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract case content only. Preserve all legal details. Remove meta-information."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.1,
            max_tokens=3800  # FIXED: Was 6000, now 3800 (under 4096 limit)
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Summarization skipped: {str(e)}")
        return case_text[:18000]

def estimate_cost(tokens):
    """Calculate estimated API cost"""
    return (tokens / 1000) * 0.00175

def call_openai(system_prompt, user_prompt, max_tokens=2600, temperature=0.2):
    """
    Make OpenAI API call with enhanced analysis capabilities.
    Increased max_tokens to 2600 for richer analysis while staying under 1.5 cents
    Reduced temperature to 0.2 for even more accuracy
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
        ["Case Analysis", "Cross-Examination Simulator"],
        help="Case Analysis: Get AI insights\nCross-Exam: Practice questioning"
    )
    
    st.markdown("---")
    st.markdown("**💡 Tips**")
    if mode == "Case Analysis":
        st.info("The AI analyzes ONLY facts explicitly stated in your case packet. Upload PDF or paste text.")
    else:
        st.info("AI simulates a witness based strictly on their testimony in the case.")

# ==========================================
# MODE 1: CASE ANALYSIS
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
        
        with st.spinner("🔍 Processing and cleaning case packet..."):
            case_text_cleaned = aggressive_preprocess(case_text)
            
            if len(case_text_cleaned) > 18000:
                st.info("📋 Condensing lengthy case while preserving all facts...")
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
        # ENHANCED SYSTEM PROMPT with mock trial competition knowledge
        base_system = """You are an expert Mock Trial coach who has studied national championship performances. You analyze ONLY what is explicitly written in the case packet.

ABSOLUTE RULES:
1. ONLY STATE FACTS EXPLICITLY WRITTEN IN THE CASE PACKET
2. NEVER INVENT OR ASSUME
3. DISTINGUISH META-INFO FROM CASE CONTENT
4. WHEN UNCERTAIN: State "This is not specified in the case packet"
5. ACCURACY OVER COMPLETENESS

STYLISTIC GUIDELINES (inspired by championship mock trial performances):
- Use powerful, memorable phrasing for key points
- Create narrative themes that tie facts together
- Identify "story arcs" within the case
- Suggest compelling metaphors that fit the case facts
- Highlight emotional resonance of key facts
- Frame arguments with rhetorical techniques (rule of three, contrasts, repetition)

Your analysis must be 100% grounded in the case packet provided, but presented with championship-level strategic insight."""

        # ENHANCED PROMPTS with better catchphrase and strategic depth
        prompts = {
            "Full Case Analysis": f"""Analyze this case using ONLY information explicitly stated below. Provide championship-level strategic insights.

PROVIDE:

**1. CASE OVERVIEW & THEME**
- Parties and charges
- Key dates and locations  
- **NARRATIVE THEME**: What's the compelling story here? (1-2 sentence theme that ties everything together)
- **CASE TAGLINE**: A memorable phrase that captures this case (like "Justice delayed is justice denied" or "Actions speak louder than words")

**2. CRITICAL FACTS (18-20 facts)**
For each fact:
- State the fact with exact details and quotes
- Legal significance (which elements it proves/disproves)
- Strategic value (which side benefits and why)
- Source (witness name or exhibit number)
- **Emotional impact**: How this fact resonates with jurors
- **Catchphrase opportunity**: Memorable way to frame this fact in argument

**3. LEGAL ELEMENTS & BURDEN**
- What must be proven beyond reasonable doubt / by preponderance?
- Each element broken down
- Strength of evidence for each element (Strong/Moderate/Weak for each side)

**4. PROSECUTION/PLAINTIFF STRATEGY**
- **Core Theory** (what happened and why)
- **Theme Statement** (one powerful sentence)
- 3 strongest arguments with supporting evidence
- How to overcome weaknesses
- **Power Phrases**: 3-5 memorable phrases to use in closing

**5. DEFENSE STRATEGY**
- **Core Theory** (alternative narrative)
- **Theme Statement** (one powerful sentence)
- 3 strongest arguments with supporting evidence  
- How to exploit prosecution weaknesses
- **Power Phrases**: 3-5 memorable phrases to use in closing

**6. WITNESS-BY-WITNESS BREAKDOWN**
For each key witness:
- Role and what they establish
- Credibility assessment (Strong/Moderate/Weak and why)
- Key testimony with exact quotes
- Contradictions or inconsistencies
- **Examination strategy**: What to emphasize or attack
- **Memorable characterization**: One-phrase description of this witness

**7. EVIDENCE & EXHIBITS**
- Each key exhibit and what it proves
- Corroboration or contradiction patterns
- Timeline reconstruction from evidence
- **Visual/demonstrative opportunities**: What evidence could be displayed dramatically

**8. STRATEGIC ROADMAP**
- **Opening hook ideas**: 3 different powerful opening approaches
- **Closing themes**: 2-3 alternative closing themes
- **"Ah-ha" moments**: Facts that could create breakthroughs
- **Zingers**: 5-7 powerful one-liners for key moments (based on case facts)
- **Vulnerabilities**: What each side must address
- **Winning moments**: Where can each side create impact?

===CASE PACKET===
{case_text_processed}
===END===

Analyze deeply. Be strategic. Be memorable. Use only case facts.""",

            "Key Facts Only": f"""Extract 20 most legally significant facts. Make each fact MEMORABLE and STRATEGIC.

For EACH fact (numbered 1-20):

**FACT #X: [Specific fact with dramatic phrasing]**
- **Quote**: "[Exact quote from case]"
- **Source**: [Witness name or exhibit]
- **Legal significance**: [Which element this proves/disproves]
- **Strategic value**: [Which side benefits and how to weaponize this]
- **Power phrase**: [How to frame this fact memorably in argument]
- **Juror appeal**: [Why this fact matters emotionally/logically to jurors]

PRIORITIZE:
- Disputed facts with contradictions
- Timeline inconsistencies
- Credibility indicators
- "Smoking gun" evidence
- Facts that create reasonable doubt
- Facts with emotional resonance

Do not invent facts. Quote case directly.

===CASE PACKET===
{case_text_processed}
===END===

20 strategic facts with championship-level framing.""",

            "Legal Issues": f"""Identify key legal issues with championship-level depth.

For each issue:

**ISSUE #X: [Legal question]**
- **Elements to prove**: [Specific requirements]
- **Burden of proof**: [Standard and what it means practically]
- **Prosecution/Plaintiff evidence**: [Specific facts with strength assessment]
- **Defense evidence**: [Specific facts with strength assessment]
- **Battleground**: [Why this issue is contested]
- **Winning approach**: [How each side should argue this]
- **Catchphrase**: [Memorable way to frame this issue]

Focus on disputed elements where the case will be won or lost.

===CASE PACKET===
{case_text_processed}
===END===

Strategic legal analysis.""",

            "Prosecution Arguments": f"""Develop 5 championship-caliber prosecution arguments.

For each argument:

**ARGUMENT #X: [Compelling argument title]**

**Theme statement**: [One powerful sentence capturing this argument]

**Evidence chain**:
- Witness testimony: "[Direct quote]" - [Witness]
- Physical evidence: [Specific exhibit with details]
- Corroborating facts: [Additional support]
- **Strength**: [Rate as Strong/Solid/Moderate]

**Why this wins**:
- Logical reasoning path
- Emotional appeal to jurors
- How it proves legal elements
- Corroboration from multiple sources

**Power phrases** (3-5 memorable lines for this argument):
1. [Catchphrase based on case facts]
2. [Rhetorical question based on evidence]
3. [Repetition for emphasis technique]
4. [Contrast phrase: "Not X, but Y"]
5. [Call-to-action conclusion]

**Defense counter & response**:
- How defense will attack: [Specific counter]
- Prosecution rebuttal: [How to neutralize]
- Impeachment opportunities: [Weak defense witnesses to target]

**Closing moment**: [How to dramatically culminate this argument in closing]

All evidence must be from case. Make it championship-worthy.

===CASE PACKET===
{case_text_processed}
===END===

5 powerful prosecution arguments.""",

            "Defense Arguments": f"""Develop 5 championship-caliber defense arguments.

For each argument:

**ARGUMENT #X: [Compelling argument title]**

**Theme statement**: [One powerful sentence capturing this argument]

**Evidence chain**:
- Witness testimony: "[Direct quote]" - [Witness]
- Physical evidence: [Specific exhibit with details]
- Gaps in prosecution case: [What they cannot prove]
- Contradictions: [Specific inconsistencies]
- **Strength**: [Rate as Strong/Solid/Moderate]

**Why this creates reasonable doubt**:
- Logical reasoning path
- Emotional appeal to jurors
- How it undermines prosecution elements
- Alternative explanations

**Power phrases** (3-5 memorable lines for this argument):
1. [Catchphrase based on case facts]
2. [Rhetorical question exposing prosecution weakness]
3. [Reasonable doubt emphasis]
4. [Contrast: "Prosecution wants you to believe X, but the evidence shows Y"]
5. [Innocence presumption reminder]

**Prosecution counter & response**:
- How prosecution will attack: [Specific counter]
- Defense rebuttal: [How to neutralize]
- Impeachment opportunities: [Weak prosecution witnesses to target]

**Closing moment**: [How to dramatically culminate this argument in closing]

All evidence must be from case. Make it championship-worthy.

===CASE PACKET===
{case_text_processed}
===END===

5 powerful defense arguments.""",

            "Witness Questions": f"""Generate championship-level examination questions for: {witness_name_input}

FIRST: Verify {witness_name_input} is a WITNESS in this case.

**WITNESS PROFILE**
- Role and significance in case
- Key testimony they provide
- Credibility assessment (Strong/Moderate/Weak and why)
- Bias or motivation
- **One-line characterization**: [Memorable description]

**DIRECT EXAMINATION (12 strategic questions)**

Foundation (2-3 questions):
1. [Establishing who they are]
2. [Establishing their knowledge/presence]

Key facts (6-7 questions building narrative):
3. [Open-ended question establishing crucial fact]
4. [Follow-up for detail]
[Continue strategic progression...]

Credibility building (2-3 questions):
[Questions that make witness seem honest/reliable]

For each question:
- **Purpose**: [What this establishes]
- **Follow-up opportunity**: [Where to go next based on answer]
- **Emotional moment**: [Questions that create juror connection]

**CROSS-EXAMINATION (12 strategic questions)**

Control & commitment (2-3 questions):
1. [Leading question establishing undisputed fact]
2. [Build foundation for attack]

Impeachment/Undermine (7-8 questions):
3. [Leading question exposing contradiction]
4. [Follow-up pinning them down]
[Continue strategic attack...]

Final blow (2-3 questions):
[Devastating final questions]

For each question:
- **Strategic goal**: [What you're accomplishing]
- **Expected answer**: [What they'll likely say]
- **Impeachment setup**: [How this sets up attack]
- **If they resist**: [Follow-up if they don't answer as expected]

**POWER MOVES**
- Best impeachment opportunities
- Zingers (dramatic questions for effect)
- Silence moments (when to pause for impact)
- Exhibits to use during examination

If {witness_name_input} is NOT a witness:
State: "{witness_name_input} is not identified as a witness in this case packet."

===CASE PACKET===
{case_text_processed}
===END===

Championship-level examination strategy.""",

            "Opening Statement Ideas": f"""Draft championship-level opening statement frameworks.

**PROSECUTION/PLAINTIFF OPENING:**

1. **Hook (30-45 seconds)** - 3 alternative openings:
   - **Dramatic quote approach**: [Powerful quote from case]
   - **Rhetorical question approach**: [Question that frames case]
   - **Vivid scene approach**: [Describe key moment dramatically]

2. **Theme Statement** (1 sentence that will be repeated):
   - [Memorable theme based on case facts]

3. **The Story** (3-4 minutes in present tense):
   - [Chronological narrative with emotional beats]
   - **Key moments to emphasize**: [3-4 dramatic facts]
   - **Power phrases to use**: [5-7 memorable lines]
   - **Repetition device**: [Phrase to repeat throughout]

4. **What We Will Prove** (2 minutes):
   - Element by element preview
   - Evidence that proves each (without arguing)
   - Witness by witness: what each will show

5. **Closing Line** (powerful final statement):
   - [3 alternative closing lines to choose from]

**DEFENSE OPENING:**

1. **Hook (30-45 seconds)** - 3 alternative openings:
   - **Presumption of innocence approach**: [Frame burden powerfully]
   - **Prosecution weakness approach**: [What they cannot prove]
   - **Alternative narrative approach**: [Different story opening]

2. **Theme Statement** (1 sentence for reasonable doubt):
   - [Memorable theme based on case facts]

3. **The Defense Story** (3-4 minutes):
   - [Alternative narrative or weakness exposition]
   - **Reasonable doubt moments**: [Facts creating doubt]
   - **Power phrases**: [5-7 memorable lines]
   - **Repetition device**: [Phrase to repeat]

4. **What Prosecution Must Prove** (2 minutes):
   - Elements they cannot meet
   - Burden of proof emphasis
   - Gaps in their case

5. **Closing Line** (powerful final statement):
   - [3 alternative closing lines emphasizing reasonable doubt]

**CHAMPIONSHIP TECHNIQUES TO USE:**
- Rule of three (listing things in threes)
- Present tense for immediacy
- Rhetorical questions for engagement
- Contrast phrases ("Not X, but Y")
- Repetition for emphasis
- Silence/pause for dramatic moments

All based on case facts only.

===CASE PACKET===
{case_text_processed}
===END===

Championship-level opening strategies.""",

            "Closing Statement Ideas": f"""Draft championship-level closing argument frameworks.

**PROSECUTION/PLAINTIFF CLOSING:**

1. **Opening Hook** (powerful 30 seconds):
   - [3 alternative opening approaches]
   - Return to opening theme
   - Emotional connection to case

2. **"Here's What Happened"** (2 minutes):
   - Reconstruct events with evidence
   - Use present tense
   - Dramatic retelling with power phrases

3. **Elements Proven** (4-5 minutes - CORE):
   - **Element 1**: [Evidence proving it]
     - Witness quotes supporting
     - Exhibits confirming
     - **Power phrase**: [Memorable line]
   - [Continue for each element]
   - **After each element**: "Check. Proven. Beyond reasonable doubt."

4. **Credibility** (2-3 minutes):
   - Why our witnesses are credible (specific reasons)
   - Why defense witnesses are not (contradictions)
   - **Catchphrases**: [Memorable characterizations]

5. **Addressing Defense** (2 minutes):
   - Anticipate their main arguments
   - Dismantle with evidence
   - **Powerful rebuttals**: [Specific counter-phrases]

6. **The Stakes** (1 minute):
   - Why this matters
   - Justice requires action
   - Emotional appeal

7. **Final Appeal** (30-45 seconds):
   - Return to theme
   - Call to action
   - **Mic drop moment**: [Devastating final line]

**DEFENSE CLOSING:**

1. **Opening Hook** (powerful 30 seconds):
   - [3 alternative opening approaches]
   - Presumption of innocence reminder
   - Reasonable doubt theme

2. **"Here's What Really Happened" / "Here's What They Cannot Prove"** (2 minutes):
   - Alternative narrative OR
   - Systematic dismantling of prosecution case
   - Emotional tone: righteous defense

3. **Reasonable Doubt** (4-5 minutes - CORE):
   - **Element 1**: [Why not proven beyond reasonable doubt]
     - Gaps in evidence
     - Contradictions
     - Alternative explanations
     - **Power phrase**: [Memorable line]
   - [Continue for each element]
   - **After each element**: "That's not proof. That's reasonable doubt."

4. **Credibility** (2-3 minutes):
   - Problems with prosecution witnesses (specific)
   - Defense witnesses are credible (specific reasons)
   - **Catchphrases**: [Memorable characterizations]

5. **Addressing Prosecution** (2 minutes):
   - Anticipate their closing
   - Pre-emptively dismantle
   - Burden of proof emphasis
   - **Powerful rebuttals**: [Specific counter-phrases]

6. **The Stakes** (1 minute):
   - Presumption of innocence is cornerstone of justice
   - Reasonable doubt protects us all
   - Cannot convict on speculation

7. **Final Appeal** (30-45 seconds):
   - Return to reasonable doubt theme
   - Acquittal is only just verdict
   - **Mic drop moment**: [Powerful final line]

**CHAMPIONSHIP TECHNIQUES:**
- Repetition (repeat key phrases 3 times)
- Rule of three
- Rhetorical questions
- Silence for emphasis
- Vary pacing (slow for important moments)
- Contrast phrases
- Callback to opening
- Use "you" to address jurors directly

**POWER PHRASES BANK** (10-15 memorable lines from case facts):
1. [Catchphrase based on key fact]
2. [Rhetorical question]
3. [Contrast phrase]
[Continue with case-specific phrases]

All based on case facts only.

===CASE PACKET===
{case_text_processed}
===END===

Championship-level closing strategies."""
        }
        
        with st.spinner("🤔 Conducting championship-level analysis (20-30 seconds)..."):
            if analysis_type in ["Full Case Analysis", "Key Facts Only", "Prosecution Arguments", "Defense Arguments"]:
                max_tokens_to_use = 2600  # Increased for richer analysis
            elif analysis_type in ["Opening Statement Ideas", "Closing Statement Ideas"]:
                max_tokens_to_use = 2400
            else:
                max_tokens_to_use = 2000
            
            result, tokens = call_openai(
                base_system, 
                prompts[analysis_type],
                max_tokens=max_tokens_to_use,
                temperature=0.2  # Lower for accuracy
            )
            
            if result:
                cost = estimate_cost(tokens)
                st.session_state.total_cost += cost
                
                st.success("✅ Analysis Complete!")
                st.markdown("---")
                st.markdown("### 📊 Results")
                st.markdown(result)
                
                st.download_button(
                    "📥 Download Analysis",
                    data=result,
                    file_name=f"analysis_{analysis_type.replace(' ', '_').lower()}.txt",
                    mime="text/plain"
                )
                
                st.markdown(f'<p class="cost-display">Analysis cost: ${cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# MODE 2: CROSS-EXAMINATION SIMULATOR
# ==========================================

else:
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
                
                with st.spinner("🧠 Preparing witness simulation..."):
                    setup_prompt = f"""You are simulating {witness_name}, a WITNESS in this mock trial case.

CRITICAL RULES:
1. You are a WITNESS - not a judge, not a case creator
2. Answer ONLY based on {witness_name}'s witness statement
3. Stay 100% consistent with testimony
4. If asked about something unknown: "I don't know" or "I don't recall"
5. For improper questions: "OBJECTION: [specific reason]"
6. Do NOT invent facts

Examination type: {exam_type}

===CASE CONTENT===
{case_text_processed}
===END===

You are {witness_name}. Respond only based on what {witness_name} testified to above."""
                    
                    st.session_state.witness_context = setup_prompt
                
                st.rerun()
    
    else:
        st.success(f"🎭 **Simulating: {st.session_state.witness_name}** ({st.session_state.exam_type})")
        
        st.markdown("### 💬 Examination Transcript")
        
        for i, exchange in enumerate(st.session_state.conversation_history):
            st.markdown(f"**Q{i+1} (You):** {exchange['question']}")
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
            if st.button("📤 Ask Question") and user_question:
                with st.spinner("🤔 Witness responding..."):
                    recent_history = st.session_state.conversation_history[-3:]
                    conversation = "\n".join([
                        f"Q: {ex['question']}\nA: {ex['answer']}"
                        for ex in recent_history
                    ])
                    
                    full_prompt = f"""{st.session_state.witness_context}

Previous questions:
{conversation}

New question: {user_question}

Respond as {st.session_state.witness_name}:
- If improper: "OBJECTION: [specific reason]"
- If proper: Answer based ONLY on testimony
- Do NOT invent facts"""
                    
                    system_msg = f"You are {st.session_state.witness_name}, a witness. Answer ONLY based on testimony. Do not invent information. Object to improper questions."
                    
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
            # NEW FEATURE: Get Feedback Button
            if st.button("📋 Get Feedback") and len(st.session_state.conversation_history) >= 3:
                with st.spinner("🎓 Analyzing your examination..."):
                    # Create feedback prompt
                    questions_only = [ex['question'] for ex in st.session_state.conversation_history]
                    
                    feedback_prompt = f"""You are a championship mock trial coach providing feedback on this {st.session_state.exam_type.split()[0]} examination.

EXAMINATION TRANSCRIPT:
{chr(10).join([f"Q{i+1}: {q}" for i, q in enumerate(questions_only)])}

PROVIDE DETAILED FEEDBACK:

**OVERALL ASSESSMENT** (1-2 sentences on performance level)

**STRENGTHS** (2-3 specific things done well):
- [What worked and why]

**AREAS FOR IMPROVEMENT** (3-4 specific issues):
1. [Issue with example question]
   - Why this is problematic
   - How to fix it
   - Better alternative question

**QUESTION-BY-QUESTION NOTES** (for key questions):
- Q[number]: [Specific feedback]
  - [What could be improved]
  - [Suggested rewrite]

**{"CROSS-EXAMINATION" if "Cross" in st.session_state.exam_type else "DIRECT EXAMINATION"} PRINCIPLES VIOLATED OR FOLLOWED**:
- [Specific rules and how questions aligned/violated them]

**CHAMPIONSHIP-LEVEL TIPS**:
- [2-3 advanced techniques to incorporate]
- [Strategic improvements for this specific witness]

**SUGGESTED QUESTIONS TO ADD** (3-5 questions you should have asked):
1. [Better question with explanation of why]
2. [Another strong question]

Be specific. Use actual questions from transcript. Give actionable advice."""

                    system_msg = "You are an expert mock trial coach who has coached championship teams. Provide constructive, specific, actionable feedback."
                    
                    feedback, tokens = call_openai(
                        system_msg,
                        feedback_prompt,
                        max_tokens=1200,
                        temperature=0.3
                    )
                    
                    if feedback:
                        cost = estimate_cost(tokens)
                        st.session_state.total_cost += cost
                        
                        # Display feedback in special section
                        st.markdown('<div class="feedback-section">', unsafe_allow_html=True)
                        st.markdown("## 🎓 Championship Coach Feedback")
                        st.markdown(feedback)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Download feedback option
                        st.download_button(
                            "📥 Download Feedback",
                            data=feedback,
                            file_name=f"examination_feedback_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            key="download_feedback"
                        )
                        
                        st.markdown(f'<p class="cost-display">Feedback cost: ${cost:.4f}</p>', unsafe_allow_html=True)
            
            elif st.button("📋 Get Feedback") and len(st.session_state.conversation_history) < 3:
                st.warning("⚠️ Ask at least 3 questions before requesting feedback")
        
        with col3:
            if st.button("🔄 End"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session cost: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)
        
        with st.expander("💡 Examination Tips"):
            if "Cross" in st.session_state.exam_type:
                st.markdown("""
                **Cross-Examination Rules:**
                - Use leading questions (suggest the answer)
                - One fact per question
                - Control the witness
                - Never ask "why" or open-ended questions
                - Build foundation before impeachment
                
                **Championship Techniques:**
                - Use short, punchy questions
                - Commit witness to facts before attack
                - Save best impeachment for end
                - Use silence after damaging answers
                
                ✅ **Good**: "You were 50 feet away, correct?"
                ✅ **Good**: "You never told police about this, did you?"
                ❌ **Bad**: "How far away were you?"
                ❌ **Bad**: "Can you explain what happened?"
                """)
            else:
                st.markdown("""
                **Direct Examination Rules:**
                - Use open-ended questions
                - Let witness tell their story
                - No leading questions
                - Build narrative chronologically
                - Establish credibility first
                
                **Championship Techniques:**
                - Start with who/what/where foundation
                - Ask for specific details that matter
                - Slow down for key moments
                - End on strong note
                
                ✅ **Good**: "What did you observe?"
                ✅ **Good**: "Describe what happened next."
                ❌ **Bad**: "You saw the defendant, didn't you?"
                ❌ **Bad**: "It was raining that night, correct?"
                """)

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.caption("""
**About:** Championship-level AI-powered mock trial preparation tool. The AI analyzes only facts explicitly stated in your case packet and provides strategic insights inspired by national championship performances.

**Disclaimer:** AI-generated analysis may contain errors. Always verify information and use your own legal reasoning. This tool is for educational purposes only.

*Python • Streamlit • OpenAI GPT-3.5 • Built by Vihaan Paka-Hegde, University High School*
""")