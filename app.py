import streamlit as st
import openai
import PyPDF2
import io

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
    st.error("⚠️ **API Key Not Found** - Please configure your OpenAI API key")
    st.stop()

openai.api_key = api_key

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

def preprocess_case(case_text):
    """
    Clean case text to remove meta-information that causes hallucinations.
    """
    meta_phrases = [
        "in honor of",
        "dedicated to",
        "this case was created",
        "written by",
        "authored by",
        "competition rules",
        "time limits",
        "scoring rubric",
        "judge instructions",
        "for educational purposes",
        "mock trial competition"
    ]
    
    lines = case_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_lower = line.lower()
        is_meta = any(phrase in line_lower for phrase in meta_phrases)
        
        if len(line.strip()) < 10:
            is_meta = True
        
        if not is_meta:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def smart_summarize_case(case_text):
    """
    Intelligently condense case while preserving ALL critical details.
    """
    if len(case_text) <= 18000:  # Increased from 15000
        return case_text
    
    summary_prompt = f"""Extract case content, preserving ALL critical details.

INCLUDE everything about:
- Charges/claims (exact wording)
- All parties and witnesses (full descriptions)
- Timeline of events (all dates, times, sequences)
- All evidence (detailed descriptions)
- All witness statements (preserve key quotes and testimony details)
- Disputed facts and contradictions
- Legal elements that must be proven
- Credibility issues

EXCLUDE only:
- Dedications, authorship
- Procedural instructions
- Judge/competition guidelines

CRITICAL: Keep MORE detail than usual. Preserve nuance, contradictions, and complexity.

Case Packet:
{case_text}

Provide detailed case content:"""

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You preserve ALL case details. Keep complexity, contradictions, and nuance. Remove only meta-information."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.2,
            max_tokens=5000  # Increased for more detail
        )
        return response.choices[0].message.content
    except:
        return case_text[:18000]

def estimate_cost(tokens):
    """Calculate estimated API cost"""
    return (tokens / 1000) * 0.00175

def call_openai(system_prompt, user_prompt, max_tokens=1800, temperature=0.3):
    """
    Make OpenAI API call.
    Increased max_tokens to 1800 for fuller analysis while staying under 2 cents.
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            presence_penalty=0.1,
            frequency_penalty=0.0
        )
        return response.choices[0].message.content, response.usage.total_tokens
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

# ==========================================
# HEADER
# ==========================================

st.title("⚖️ Mock Trial Case Analyzer")
st.markdown("**AI-Powered Case Analysis & Cross-Examination Practice**")
st.markdown("*Built by Vihaan Paka-Hegde - University High School*")
st.markdown("---")

# ==========================================
# SIDEBAR - MODE SELECTION
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
        st.info("Upload PDF or paste text for comprehensive AI analysis")
    else:
        st.info("Practice realistic witness examination with AI")

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
    
    # Process input
    if uploaded_file:
        with st.spinner("📄 Extracting text from PDF..."):
            case_text = extract_text_from_pdf(uploaded_file)
            if case_text:
                st.success(f"✅ Extracted {len(case_text):,} characters from PDF")
    else:
        case_text = case_text_input
    
    # Analysis options
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
    
    # Analyze button
    if st.button("🚀 Analyze Case", type="primary"):
        
        if not case_text or len(case_text) < 50:
            st.error("⚠️ Please provide case text (upload PDF or paste text)")
            st.stop()
        
        if analysis_type == "Witness Questions" and not witness_name_input:
            st.error("⚠️ Please enter witness name")
            st.stop()
        
        with st.spinner("🔍 Processing case packet..."):
            case_text_cleaned = preprocess_case(case_text)
            
            if len(case_text_cleaned) > 18000:
                st.info("📋 Processing lengthy case packet...")
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
        # Enhanced system prompt
        base_system = """You are an expert Mock Trial attorney and coach with deep experience analyzing complex cases.

ANALYSIS REQUIREMENTS:
1. Identify the MOST LEGALLY SIGNIFICANT facts - not just basic information
2. Focus on DISPUTED facts, CONTRADICTIONS, and CREDIBILITY issues
3. Analyze STRATEGIC implications - what facts help which side and why
4. Consider LEGAL ELEMENTS - what must be proven for each charge/claim
5. Highlight EVIDENTIARY issues - admissibility, weight, reliability
6. Note TIMELINE inconsistencies and witness credibility problems
7. Use exact quotes when referencing testimony or evidence

FORBIDDEN:
- Do not cite facts from dedications or case creation info
- Do not invent legal precedents
- Do not add facts not in the case
- Do not give basic/obvious information - go deeper

You provide comprehensive, strategic analysis for competitive mock trial preparation."""

        # IMPROVED PROMPTS - More specific, demanding deeper analysis
        prompts = {
            "Full Case Analysis": f"""Provide a COMPREHENSIVE strategic analysis of this case.

Your analysis must be thorough and competition-ready. Include:

**1. CASE OVERVIEW**
- Parties (plaintiff/defendant) and their relationship
- Charges/claims with specific legal elements
- Key dates and timeline of events

**2. CRITICAL FACTS (15-20 facts)**
Focus on facts that are:
- Legally significant (prove/disprove elements)
- Disputed or contradicted between witnesses
- Credibility indicators
- Strategic advantages for either side

For each critical fact:
- State the fact specifically
- Explain WHY it matters legally
- Note which side it helps/hurts
- Identify source (which witness/evidence)

**3. LEGAL ISSUES & ELEMENTS**
- What must be proven for prosecution/plaintiff to win?
- What are the key legal questions/disputes?
- What defenses are available?

**4. PROSECUTION/PLAINTIFF THEORY**
- Overall narrative and theme
- How they prove each element
- Their strongest evidence
- How they handle weaknesses

**5. DEFENSE THEORY**
- Overall narrative and theme
- How they create reasonable doubt / rebut claims
- Their strongest evidence
- How they handle weaknesses

**6. WITNESS ANALYSIS**
For each key witness:
- Role and importance
- Credibility strengths/weaknesses
- What they establish
- Contradictions or inconsistencies

**7. EVIDENCE ANALYSIS**
- Most important exhibits
- Admissibility issues
- How each side uses evidence
- Evidentiary gaps or problems

**8. STRATEGIC RECOMMENDATIONS**
- Key points for each side to emphasize
- Weaknesses to address
- Potential objections or challenges
- Areas for cross-examination focus

Be specific. Quote testimony. Cite evidence. Analyze deeply.

Case Content:
{case_text_processed}""",
            
            "Key Facts Only": f"""Identify the 20 MOST STRATEGICALLY IMPORTANT facts in this case.

REQUIREMENTS:
- Focus on DISPUTED facts and CONTRADICTIONS
- Prioritize facts related to LEGAL ELEMENTS that must be proven
- Include CREDIBILITY indicators (bias, inconsistency, implausibility)
- Note TIMELINE issues
- Highlight facts with EVIDENTIARY significance

For EACH fact provide:
1. The specific fact (with exact quote if from testimony)
2. WHY this fact is legally significant
3. Which side it helps (and why)
4. What it proves or undermines
5. Source (which witness/exhibit)

Format:
**FACT #1: [Specific fact with details]**
- Legal significance: [Why it matters for proving/disproving elements]
- Strategic value: [Which side benefits and how]
- Source: [Witness name or exhibit number]

Do NOT include basic background facts. Focus on facts that WIN or LOSE the case.

Case Content:
{case_text_processed}""",
            
            "Legal Issues": f"""Identify and analyze the KEY LEGAL ISSUES in this case.

For EACH legal issue provide:

**1. THE LEGAL QUESTION**
- State the specific legal issue clearly
- What legal standard or element is at stake?

**2. APPLICABLE LAW**
- What must be proven? (burden of proof, elements)
- What is the legal test or standard?

**3. FACTS SUPPORTING EACH SIDE**
- Prosecution/plaintiff evidence on this issue
- Defense evidence on this issue
- Which side has stronger position and why?

**4. STRATEGIC ANALYSIS**
- How should each side argue this issue?
- What evidence to emphasize?
- Potential weaknesses to address?

**5. EVIDENTIARY CONSIDERATIONS**
- What evidence is admissible?
- Any objections likely?
- Weight/credibility of evidence?

Focus on 4-6 major legal issues. Analyze thoroughly.

Case Content:
{case_text_processed}""",
            
            "Prosecution Arguments": f"""Develop 5 STRONG prosecution/plaintiff arguments with full strategic analysis.

For EACH argument provide:

**ARGUMENT #[X]: [Clear statement of argument]**

**Theory:** [How this fits into overall case theory]

**Legal Elements:** [Which elements this helps prove]

**Supporting Evidence:**
- Witness testimony (with specific quotes)
- Physical evidence (with exhibit details)
- Circumstantial evidence
- Expert testimony (if applicable)

**Why This Argument Works:**
- Logical reasoning
- Credibility factors
- Timeline support
- Corroboration

**Anticipated Defense Response:**
- How defense will attack this argument
- Defense evidence to counter

**Rebuttal Strategy:**
- How to respond to defense attacks
- Additional points to emphasize
- Impeachment opportunities

**Cross-Examination Focus:**
- Which defense witnesses to target
- What to establish on cross

Be specific. Quote testimony. Cite exhibits. Think strategically.

Case Content:
{case_text_processed}""",
            
            "Defense Arguments": f"""Develop 5 STRONG defense arguments with full strategic analysis.

For EACH argument provide:

**ARGUMENT #[X]: [Clear statement of argument]**

**Theory:** [How this fits into overall defense theory]

**Legal Elements:** [Which elements this challenges / reasonable doubt created]

**Supporting Evidence:**
- Witness testimony (with specific quotes)
- Physical evidence (with exhibit details)
- Lack of evidence / gaps in prosecution case
- Inconsistencies or contradictions

**Why This Argument Works:**
- Logical reasoning
- Credibility factors
- Alternative explanations
- Burden of proof considerations

**Anticipated Prosecution Response:**
- How prosecution will attack this argument
- Prosecution evidence to counter

**Rebuttal Strategy:**
- How to respond to prosecution attacks
- Additional points to emphasize
- Impeachment opportunities

**Cross-Examination Focus:**
- Which prosecution witnesses to target
- What to establish on cross

Be specific. Quote testimony. Cite exhibits. Think strategically.

Case Content:
{case_text_processed}""",
            
            "Witness Questions": f"""Generate STRATEGIC examination questions for witness: {witness_name_input}

**WITNESS ANALYSIS:**
First analyze this witness:
- Role in the case
- What they can establish
- Credibility strengths/weaknesses
- Key testimony points
- Potential impeachment

**DIRECT EXAMINATION (10-12 questions):**
Foundation → Key facts → Credibility building

For each question note:
- Purpose (what it establishes)
- Follow-up opportunities
- How it builds narrative

**CROSS EXAMINATION (10-12 questions):**
Control → Undermine → Impeach

For each question note:
- Strategic goal
- Expected answer
- Follow-up based on response
- Impeachment opportunities

**STRATEGIC NOTES:**
- Key points to establish
- Potential objections
- Redirect opportunities
- Witness vulnerabilities

Case Content:
{case_text_processed}""",
            
            "Opening Statement Ideas": f"""Draft COMPREHENSIVE opening statement frameworks for BOTH sides.

**PROSECUTION/PLAINTIFF OPENING:**

1. **Hook** (30-45 seconds)
   - Compelling opening line
   - Theme introduction
   - Emotional connection

2. **Charges/Claims** (1 minute)
   - What defendant is charged with
   - Legal elements explained simply
   - Burden of proof

3. **Story of the Case** (3-4 minutes)
   - Timeline of events
   - Key facts in narrative form
   - Use present tense for impact

4. **Evidence Preview** (2-3 minutes)
   - Witness by witness (what each establishes)
   - Key exhibits (what they prove)
   - How evidence connects to elements

5. **Theme & Closing** (30-45 seconds)
   - Reinforce theme
   - Final powerful line

**DEFENSE OPENING:**

1. **Hook** (30-45 seconds)
   - Counter-narrative opening
   - Defense theme
   - Presumption of innocence

2. **Response to Charges** (1 minute)
   - What prosecution must prove
   - Burden is on them
   - Reasonable doubt standard

3. **Defense Story** (3-4 minutes)
   - Alternative narrative
   - Highlighting weaknesses in prosecution case
   - Present tense, compelling story

4. **Evidence Preview** (2-3 minutes)
   - Defense witnesses (what they'll show)
   - Evidence supporting defense
   - Gaps in prosecution case

5. **Theme & Closing** (30-45 seconds)
   - Reinforce reasonable doubt
   - Final powerful line

For each section, provide:
- Specific language suggestions
- Key facts to mention
- Rhetorical techniques
- Tone and delivery notes

Case Content:
{case_text_processed}""",
            
            "Closing Statement Ideas": f"""Draft COMPREHENSIVE closing argument frameworks for BOTH sides.

**PROSECUTION/PLAINTIFF CLOSING:**

1. **Opening** (1 minute)
   - Powerful emotional hook
   - Theme reinforcement
   - Transition to argument

2. **Elements Proven** (4-5 minutes)
   - Element by element analysis
   - Evidence that proves each
   - Connect testimony to elements
   - Use "the evidence shows..."

3. **Credibility Analysis** (2-3 minutes)
   - Why prosecution witnesses are credible
   - Why defense witnesses are not
   - Contradictions in defense case

4. **Addressing Defense Arguments** (2 minutes)
   - Anticipate main defense points
   - Rebut with evidence
   - Show why defense doesn't create reasonable doubt

5. **Closing Appeal** (1 minute)
   - Emotional appeal
   - Justice requires conviction
   - Final powerful line

**DEFENSE CLOSING:**

1. **Opening** (1 minute)
   - Presumption of innocence reminder
   - Reasonable doubt standard
   - Theme reinforcement

2. **Reasonable Doubt** (4-5 minutes)
   - Element by element: not proven beyond reasonable doubt
   - Highlight gaps and inconsistencies
   - Alternative explanations
   - "The evidence does NOT show..."

3. **Credibility Analysis** (2-3 minutes)
   - Problems with prosecution witnesses
   - Defense witnesses are credible
   - Contradictions in prosecution case

4. **Addressing Prosecution Arguments** (2 minutes)
   - Anticipate main prosecution points
   - Show insufficient evidence
   - Emphasize burden of proof

5. **Closing Appeal** (1 minute)
   - Reasonable doubt exists
   - Must acquit / find for defendant
   - Final powerful line

For each section, provide:
- Specific language suggestions
- Key evidence to cite
- Rhetorical techniques
- Emotional appeals
- Delivery notes

Case Content:
{case_text_processed}"""
        }
        
        with st.spinner("🤔 Conducting deep analysis..."):
            # Use longer max_tokens for Full Analysis and other detailed requests
            if analysis_type in ["Full Case Analysis", "Key Facts Only", "Prosecution Arguments", "Defense Arguments"]:
                max_tokens_to_use = 1800
            else:
                max_tokens_to_use = 1400
            
            result, tokens = call_openai(
                base_system, 
                prompts[analysis_type],
                max_tokens=max_tokens_to_use,
                temperature=0.35  # Slightly higher for more natural writing
            )
            
            if result:
                cost = estimate_cost(tokens)
                st.session_state.total_cost += cost
                
                st.success("✅ Analysis Complete!")
                st.markdown("---")
                st.markdown("### 📊 Results")
                st.markdown(result)
                
                # Download button
                st.download_button(
                    "📥 Download Analysis",
                    data=result,
                    file_name=f"analysis_{analysis_type.replace(' ', '_').lower()}.txt",
                    mime="text/plain"
                )
                
                # Cost display
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
                    case_text_cleaned = preprocess_case(case_text)
                    if len(case_text_cleaned) > 10000:
                        case_text_processed = smart_summarize_case(case_text_cleaned)
                    else:
                        case_text_processed = case_text_cleaned
                
                st.session_state.case_text = case_text_processed
                st.session_state.witness_name = witness_name
                st.session_state.exam_type = exam_type
                st.session_state.cross_exam_mode = True
                st.session_state.conversation_history = []
                
                with st.spinner("🧠 AI preparing witness..."):
                    setup_prompt = f"""You are {witness_name} from this case.

CRITICAL: You are a WITNESS IN THE CASE, not anyone else.

Study YOUR witness statement in the case content below.

Rules:
1. Answer ONLY based on YOUR witness statement
2. Stay 100% consistent with facts in YOUR testimony
3. Do not invent facts
4. If asked something you don't know: "I don't recall"
5. For improper questions: "OBJECTION: [reason]"

Exam type: {exam_type}

Case Content:
{case_text_processed}

You are {witness_name}, a witness in this case."""
                    
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
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("📤 Ask Question") and user_question:
                with st.spinner("🤔 Witness responding..."):
                    recent_history = st.session_state.conversation_history[-4:]
                    conversation = "\n".join([
                        f"Q: {ex['question']}\nA: {ex['answer']}"
                        for ex in recent_history
                    ])
                    
                    full_prompt = f"""{st.session_state.witness_context}

Previous exchange:
{conversation}

New question: {user_question}

Respond as {st.session_state.witness_name} (a witness).
- If improper: "OBJECTION: [reason]"
- If proper: Answer based ONLY on your witness statement
- Do not invent facts"""
                    
                    system_msg = f"You are {st.session_state.witness_name}, a WITNESS in this case. Answer based ONLY on your testimony. Object to improper questions."
                    
                    answer, tokens = call_openai(
                        system_msg, 
                        full_prompt, 
                        max_tokens=150,
                        temperature=0.4
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
            if st.button("🔄 End & Restart"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session cost: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)
        
        with st.expander("💡 Examination Tips"):
            if "Cross" in st.session_state.exam_type:
                st.markdown("""
                **Cross-Examination:**
                - Leading questions (suggest the answer)
                - One fact per question
                - Control the witness
                
                **Example:** "You were 50 feet away, correct?" ✅
                """)
            else:
                st.markdown("""
                **Direct Examination:**
                - Open-ended questions
                - Let witness tell their story
                - No leading questions
                
                **Example:** "What did you observe?" ✅
                """)

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.caption("""
**About:** AI-powered mock trial preparation tool built to democratize access to case analysis.

**Disclaimer:** AI-generated analysis may contain errors. Always verify facts and apply your own legal reasoning.

*Python • Streamlit • OpenAI GPT-3.5*
""")