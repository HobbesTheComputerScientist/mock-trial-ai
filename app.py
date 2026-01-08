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

def smart_summarize_case(case_text):
    """
    Use AI to condense while preserving ALL legal content.
    COMPLETELY FIXED: Uses 3500 max_tokens (well under 4096 limit)
    """
    # If already short enough, return as-is (NO API CALL = NO ERROR)
    if len(case_text) <= 16000:
        return case_text
    
    # Only summarize if truly necessary
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
            max_tokens=3500  # FIXED: Was 6000, now 3500 (safely under 4096)
        )
        return response.choices[0].message.content
    except Exception as e:
        # If summarization fails, just truncate (NO ERROR MESSAGE)
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
if 'objection_exam_type' not in st.session_state:
    st.session_state.objection_exam_type = ""

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
        st.info("The AI analyzes ONLY facts explicitly stated in your case packet.")
    elif mode == "Cross-Examination Simulator":
        st.info("AI simulates a witness based strictly on their testimony.")
    else:
        st.info("Practice objecting to improper questions. AI will explain rulings.")

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
        
        with st.spinner("🔍 Processing case packet..."):
            case_text_cleaned = aggressive_preprocess(case_text)
            
            # FIXED: Increased threshold to 16000 to avoid unnecessary summarization
            if len(case_text_cleaned) > 16000:
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
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

        prompts = {
            "Full Case Analysis": f"""Analyze this case using ONLY information explicitly stated below.

**1. CASE OVERVIEW & THEME**
- Parties, charges, key dates
- **NARRATIVE THEME**: Compelling story (1-2 sentences)
- **CASE TAGLINE**: Memorable phrase

**2. CRITICAL FACTS (18-20 facts)**
For each: fact with quotes, legal significance, strategic value, source, emotional impact, catchphrase opportunity

**3. LEGAL ELEMENTS & BURDEN**
- What must be proven
- Strength assessment for each element

**4. PROSECUTION/PLAINTIFF STRATEGY**
- Core theory, theme statement
- 3 strongest arguments with evidence
- Power phrases (3-5 memorable lines)

**5. DEFENSE STRATEGY**
- Core theory, theme statement
- 3 strongest arguments with evidence
- Power phrases (3-5 memorable lines)

**6. WITNESS BREAKDOWN**
For each: role, credibility assessment, key testimony with quotes, contradictions, examination strategy, memorable characterization

**7. EVIDENCE & EXHIBITS**
- Key exhibits and what they prove
- Timeline reconstruction
- Visual opportunities

**8. STRATEGIC ROADMAP**
- Opening hook ideas (3 approaches)
- Closing themes (2-3 alternatives)
- Zingers (5-7 powerful one-liners from case facts)
- Winning moments

===CASE PACKET===
{case_text_processed}
===END===

Championship-level analysis using only case facts.""",

            "Key Facts Only": f"""Extract 20 most legally significant facts.

**FACT #X: [Dramatic phrasing]**
- Quote: "[Exact quote]"
- Source: [Witness/exhibit]
- Legal significance
- Strategic value
- Power phrase
- Juror appeal

Prioritize: disputed facts, contradictions, timeline issues, credibility indicators, smoking guns, emotional resonance.

===CASE PACKET===
{case_text_processed}
===END===

20 strategic facts.""",

            "Legal Issues": f"""Identify key legal issues.

**ISSUE #X:**
- Elements to prove
- Burden of proof
- Evidence for each side with strength
- Battleground analysis
- Winning approach
- Catchphrase

===CASE PACKET===
{case_text_processed}
===END===""",

            "Prosecution Arguments": f"""Develop 5 championship prosecution arguments.

**ARGUMENT #X: [Title]**
- Theme statement
- Evidence chain with quotes
- Why this wins
- Power phrases (3-5 lines)
- Defense counter & response
- Closing moment

===CASE PACKET===
{case_text_processed}
===END===""",

            "Defense Arguments": f"""Develop 5 championship defense arguments.

**ARGUMENT #X: [Title]**
- Theme statement
- Evidence chain with quotes
- Why this creates reasonable doubt
- Power phrases (3-5 lines)
- Prosecution counter & response
- Closing moment

===CASE PACKET===
{case_text_processed}
===END===""",

            "Witness Questions": f"""Generate championship examination questions for: {witness_name_input}

**WITNESS PROFILE**
- Role, credibility, bias, one-line characterization

**DIRECT EXAMINATION (12 questions)**
- Foundation (2-3)
- Key facts (6-7)
- Credibility building (2-3)
[For each: purpose, follow-up, emotional moment]

**CROSS-EXAMINATION (12 questions)**
- Control & commitment (2-3)
- Impeachment (7-8)
- Final blow (2-3)
[For each: goal, expected answer, impeachment setup, resistance plan]

**POWER MOVES**
- Impeachment opportunities
- Zingers
- Silence moments
- Exhibits to use

If {witness_name_input} is NOT a witness: State so.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Opening Statement Ideas": f"""Draft championship opening frameworks.

**PROSECUTION/PLAINTIFF:**
1. Hook (3 alternatives: dramatic quote, rhetorical question, vivid scene)
2. Theme statement (1 sentence to repeat)
3. Story (chronological with emotional beats, power phrases, repetition device)
4. What we will prove (element by element)
5. Closing line (3 alternatives)

**DEFENSE:**
1. Hook (3 alternatives)
2. Theme statement (reasonable doubt)
3. Defense story
4. What prosecution must prove
5. Closing line (3 alternatives)

Championship techniques: rule of three, present tense, rhetorical questions, contrasts, repetition, silence.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Closing Statement Ideas": f"""Draft championship closing frameworks.

**PROSECUTION/PLAINTIFF:**
1. Opening hook (3 alternatives, return to theme)
2. "Here's what happened" (dramatic retelling)
3. Elements proven (each with evidence, power phrases)
4. Credibility (why ours are credible, theirs aren't)
5. Addressing defense (anticipate and dismantle)
6. The stakes (why this matters)
7. Final appeal (mic drop moment)

**DEFENSE:**
1. Opening hook (presumption of innocence)
2. "Here's what they cannot prove"
3. Reasonable doubt (each element, why not proven)
4. Credibility (their problems, our credibility)
5. Addressing prosecution (pre-emptive dismantling)
6. The stakes (innocence protection)
7. Final appeal (powerful final line)

Championship techniques, power phrases bank (10-15 from case).

===CASE PACKET===
{case_text_processed}
===END==="""
        }
        
        with st.spinner("🤔 Conducting championship-level analysis..."):
            if analysis_type in ["Full Case Analysis", "Key Facts Only", "Prosecution Arguments", "Defense Arguments"]:
                max_tokens_to_use = 2600
            elif analysis_type in ["Opening Statement Ideas", "Closing Statement Ideas"]:
                max_tokens_to_use = 2400
            else:
                max_tokens_to_use = 2000
            
            result, tokens = call_openai(
                base_system, 
                prompts[analysis_type],
                max_tokens=max_tokens_to_use,
                temperature=0.2
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
                
                st.markdown(f'<p class="cost-display">Cost: ${cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# MODE 2: CROSS-EXAMINATION SIMULATOR
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
            if st.button("📤 Ask Question") and user_question:
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

Respond as {st.session_state.witness_name}:
- If improper: "OBJECTION: [reason]"
- If proper: Answer based ONLY on testimony"""
                    
                    system_msg = f"You are {st.session_state.witness_name}, a witness. Answer ONLY based on testimony. Object to improper questions."
                    
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
            if st.button("📋 Get Feedback") and len(st.session_state.conversation_history) >= 3:
                with st.spinner("🎓 Analyzing..."):
                    questions_only = [ex['question'] for ex in st.session_state.conversation_history]
                    
                    feedback_prompt = f"""You are a championship mock trial coach. Provide feedback on this {st.session_state.exam_type.split()[0]} examination.

TRANSCRIPT:
{chr(10).join([f"Q{i+1}: {q}" for i, q in enumerate(questions_only)])}

PROVIDE:
**OVERALL ASSESSMENT**
**STRENGTHS** (2-3 specific)
**AREAS FOR IMPROVEMENT** (3-4 with examples and fixes)
**QUESTION-BY-QUESTION NOTES**
**RULES FOLLOWED/VIOLATED**
**CHAMPIONSHIP TIPS**
**SUGGESTED QUESTIONS TO ADD** (3-5)

Be specific, actionable."""

                    feedback, tokens = call_openai(
                        "You are an expert mock trial coach. Provide constructive feedback.",
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
            
            elif st.button("📋 Get Feedback") and len(st.session_state.conversation_history) < 3:
                st.warning("⚠️ Ask at least 3 questions first")
        
        with col3:
            if st.button("🔄 End"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# MODE 3: OBJECTION PRACTICE (NEW)
# ==========================================

else:  # Objection Practice
    
    st.subheader("⚖️ Objection Practice")
    st.markdown("Learn when to object by practicing with realistic examination questions.")
    
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
        exam_type = st.radio(
            "Type of examination:",
            ["Direct Examination", "Cross-Examination"],
            key="objection_exam_type"
        )
        
        if st.button("🎯 Start Objection Practice", type="primary"):
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
                
                st.session_state.objection_case_text = case_text_processed
                st.session_state.objection_witness = witness_name
                st.session_state.objection_exam_type = exam_type
                st.session_state.objection_mode = True
                st.session_state.objection_history = []
                st.session_state.current_question = None
                
                st.rerun()
    
    else:
        st.success(f"🎯 **Practicing Objections - {st.session_state.objection_exam_type} of {st.session_state.objection_witness}**")
        
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
        
        # Generate or display current question
        if st.session_state.current_question is None:
            with st.spinner("🤔 Generating practice question..."):
                question_prompt = f"""You are generating a mock trial examination question for objection practice.

Witness: {st.session_state.objection_witness}
Examination type: {st.session_state.objection_exam_type}

Case context:
{st.session_state.objection_case_text[:3000]}

Generate ONE realistic examination question that is either:
- Proper (no objection needed), OR
- Improper (objection should be made)

For {st.session_state.objection_exam_type}:
{"- Improper questions: leading, assumes facts not in evidence, compound, argumentative" if st.session_state.objection_exam_type == "Direct Examination" else "- Improper questions: non-leading, compound, argumentative, asked and answered, speculation"}

Output format:
QUESTION: [the actual question]
RULING: [PROPER or IMPROPER]
REASON: [If improper, what objection applies. If proper, why it's acceptable]
EXPLANATION: [Brief explanation of why this is proper/improper for this examination type]

Generate a realistic question based on the case."""

                system_msg = "You are a mock trial judge creating practice questions. Generate realistic, educational questions."
                
                response, tokens = call_openai(
                    system_msg,
                    question_prompt,
                    max_tokens=300,
                    temperature=0.7
                )
                
                if response:
                    cost = estimate_cost(tokens)
                    st.session_state.total_cost += cost
                    st.session_state.current_question = response
                    st.rerun()
        
        # Display current question
        if st.session_state.current_question:
            # Parse the response
            lines = st.session_state.current_question.split('\n')
            question_text = ""
            ruling = ""
            reason = ""
            explanation = ""
            
            for line in lines:
                if line.startswith("QUESTION:"):
                    question_text = line.replace("QUESTION:", "").strip()
                elif line.startswith("RULING:"):
                    ruling = line.replace("RULING:", "").strip()
                elif line.startswith("REASON:"):
                    reason = line.replace("REASON:", "").strip()
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
            
            st.markdown("### 📝 Practice Question")
            st.markdown(f"**Attorney asks:** \"{question_text}\"")
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ No Objection (Proper Question)", use_container_width=True):
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
                    
                    if correct:
                        st.markdown('<div class="correct-answer">', unsafe_allow_html=True)
                        st.markdown("### ✅ Correct!")
                        st.markdown(f"**This question is PROPER.**")
                        st.markdown(f"**Why:** {reason}")
                        st.markdown(f"**Explanation:** {explanation}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="incorrect-answer">', unsafe_allow_html=True)
                        st.markdown("### ❌ Incorrect")
                        st.markdown(f"**This question is IMPROPER.**")
                        st.markdown(f"**Objection:** {reason}")
                        st.markdown(f"**Explanation:** {explanation}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.session_state.current_question = None
                    
                    if st.button("➡️ Next Question"):
                        st.rerun()
            
            with col2:
                if st.button("🚫 OBJECTION! (Improper Question)", use_container_width=True):
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
                    
                    if correct:
                        st.markdown('<div class="correct-answer">', unsafe_allow_html=True)
                        st.markdown("### ✅ Correct!")
                        st.markdown(f"**Objection sustained!**")
                        st.markdown(f"**Objection:** {reason}")
                        st.markdown(f"**Explanation:** {explanation}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="incorrect-answer">', unsafe_allow_html=True)
                        st.markdown("### ❌ Incorrect")
                        st.markdown(f"**Objection overruled. This question is PROPER.**")
                        st.markdown(f"**Why it's proper:** {reason}")
                        st.markdown(f"**Explanation:** {explanation}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.session_state.current_question = None
                    
                    if st.button("➡️ Next Question"):
                        st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("🔄 Get New Question"):
                st.session_state.current_question = None
                st.rerun()
        
        with col2:
            if st.button("🏁 End Practice"):
                st.session_state.objection_mode = False
                st.session_state.objection_history = []
                st.session_state.current_question = None
                st.rerun()
        
        # Show history
        if len(st.session_state.objection_history) > 0:
            with st.expander("📊 Practice History"):
                for i, item in enumerate(st.session_state.objection_history):
                    status = "✅" if item['correct'] else "❌"
                    st.markdown(f"**{status} Q{i+1}:** {item['question']}")
                    st.markdown(f"- Your answer: {item['user_answer']}")
                    st.markdown(f"- Correct answer: {item['correct_answer']}")
                    st.markdown(f"- Reason: {item['reason']}")
                    st.markdown("---")
        
        st.markdown(f'<p class="cost-display">Session cost: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.caption("""
**About:** Championship-level AI-powered mock trial preparation tool.

**Disclaimer:** AI-generated analysis may contain errors. Always verify information.

*Python • Streamlit • OpenAI GPT-3.5 • Built by Vihaan Paka-Hegde*
""")