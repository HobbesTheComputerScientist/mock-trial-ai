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
        st.info("Practice objecting to improper questions. Mix of proper and improper questions.")

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

STYLISTIC GUIDELINES:
- Use powerful, memorable phrasing
- Create narrative themes
- Suggest compelling metaphors from case facts
- Highlight emotional resonance
- Frame arguments with rhetorical techniques

Your analysis must be 100% grounded in the case packet provided."""

        prompts = {
            "Full Case Analysis": f"""Analyze this case using ONLY information explicitly stated below.

**1. CASE OVERVIEW & THEME**
**2. CRITICAL FACTS (18-20 facts)**
**3. LEGAL ELEMENTS & BURDEN**
**4. PROSECUTION/PLAINTIFF STRATEGY**
**5. DEFENSE STRATEGY**
**6. WITNESS BREAKDOWN**
**7. EVIDENCE & EXHIBITS**
**8. STRATEGIC ROADMAP**

===CASE PACKET===
{case_text_processed}
===END===

Championship-level analysis using only case facts.""",

            "Key Facts Only": f"""Extract 20 most legally significant facts with strategic framing.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Legal Issues": f"""Identify key legal issues with championship depth.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Prosecution Arguments": f"""Develop 5 championship prosecution arguments.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Defense Arguments": f"""Develop 5 championship defense arguments.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Witness Questions": f"""Generate championship examination questions for: {witness_name_input}

===CASE PACKET===
{case_text_processed}
===END===""",

            "Opening Statement Ideas": f"""Draft championship opening frameworks.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Closing Statement Ideas": f"""Draft championship closing frameworks.

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
            if st.button("📋 Get Feedback") and len(st.session_state.conversation_history) >= 3:
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
            
            elif st.button("📋 Get Feedback") and len(st.session_state.conversation_history) < 3:
                st.warning("⚠️ Ask at least 3 questions first")
        
        with col3:
            if st.button("🔄 End"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)

# ==========================================
# MODE 3: OBJECTION PRACTICE (FIXED)
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
                with st.spinner("🔍 Processing case..."):
                    case_text_cleaned = aggressive_preprocess(case_text)
                    if len(case_text_cleaned) > 12000:
                        case_text_processed = smart_summarize_case(case_text_cleaned)
                    else:
                        case_text_processed = case_text_cleaned
                
                st.session_state.objection_case_text = case_text_processed
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
                # Increment question count and determine if should be proper or improper
                st.session_state.question_count += 1
                
                # Randomize: ~50% proper, ~50% improper
                should_be_proper = random.choice([True, False])
                
                question_prompt = f"""You are generating ONE mock trial examination question for objection practice.

CRITICAL INSTRUCTIONS:
1. Generate {"a PROPER question (no objection needed)" if should_be_proper else "an IMPROPER question (objection should be made)"}
2. Base the question on FACTS FROM THE CASE ONLY - do NOT invent facts not in the case
3. Use witness name and case details appropriately
4. Make the question realistic and educational

Witness: {st.session_state.objection_witness}
Examination type: {st.session_state.saved_objection_exam_type}

Case excerpt (USE THESE FACTS ONLY):
{st.session_state.objection_case_text[:2500]}

{"GENERATE A PROPER QUESTION:" if should_be_proper else "GENERATE AN IMPROPER QUESTION:"}

{f'''For {st.session_state.saved_objection_exam_type}:
- Proper question example: "What did you observe at the scene?" or "Describe what happened next."
- Make it open-ended, non-leading, asks about facts the witness would know from case''' if should_be_proper and st.session_state.saved_objection_exam_type == "Direct Examination" else ""}

{f'''For {st.session_state.saved_objection_exam_type}:
- Proper question example: "You were at the location at 3pm, correct?" or "You told police you didn't see it, didn't you?"
- Make it leading, one fact, controls witness, based on case facts''' if should_be_proper and st.session_state.saved_objection_exam_type == "Cross-Examination" else ""}

{f'''For {st.session_state.saved_objection_exam_type}:
- Improper question example: "You saw the defendant run away, didn't you?" (leading on direct)
- Make it violate direct exam rules: leading, assumes facts, compound''' if not should_be_proper and st.session_state.saved_objection_exam_type == "Direct Examination" else ""}

{f'''For {st.session_state.saved_objection_exam_type}:
- Improper question example: "Why did you go to the store?" (open-ended on cross)
- Make it violate cross exam rules: open-ended, asks why, compound, argumentative''' if not should_be_proper and st.session_state.saved_objection_exam_type == "Cross-Examination" else ""}

Output format (EXACT format required):
QUESTION: [Attorney asks witness: "Your realistic question based on case facts here"]
RULING: {"PROPER" if should_be_proper else "IMPROPER"}
REASON: {("[Why this is a proper question for this exam type]" if should_be_proper else "[Specific objection that applies: Leading/Compound/Argumentative/Assumes facts not in evidence/Calls for speculation]")}
EXPLANATION: [Brief explanation of why this is proper/improper]

Generate ONE realistic question based ONLY on facts from the case provided above."""

                system_msg = "You are a mock trial judge creating educational practice questions. Generate questions based ONLY on case facts provided. Never invent facts. Make proper and improper questions equally challenging."
                
                response, tokens = call_openai(
                    system_msg,
                    question_prompt,
                    max_tokens=350,
                    temperature=0.8  # Increased for more variety
                )
                
                if response:
                    cost = estimate_cost(tokens)
                    st.session_state.total_cost += cost
                    st.session_state.current_question = response
                    st.rerun()
        
        # Display current question and handle responses
        if st.session_state.current_question and not st.session_state.show_result:
            # Parse response
            lines = st.session_state.current_question.split('\n')
            question_text = ""
            ruling = ""
            reason = ""
            explanation = ""
            
            for line in lines:
                if line.startswith("QUESTION:"):
                    question_text = line.replace("QUESTION:", "").strip()
                elif line.startswith("RULING:"):
                    ruling = line.replace("RULING:", "").strip().upper()
                elif line.startswith("REASON:"):
                    reason = line.replace("REASON:", "").strip()
                elif line.startswith("EXPLANATION:"):
                    explanation = line.replace("EXPLANATION:", "").strip()
            
            # Ensure ruling is either PROPER or IMPROPER
            if "PROPER" in ruling:
                ruling = "PROPER"
            elif "IMPROPER" in ruling:
                ruling = "IMPROPER"
            
            st.markdown("### 📝 Practice Question")
            st.markdown(f"**Attorney asks:** \"{question_text}\"")
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
        
        # Show result if answer was given
        if st.session_state.show_result and len(st.session_state.objection_history) > 0:
            last_item = st.session_state.objection_history[-1]
            
            if last_item['correct']:
                st.markdown('<div class="correct-answer">', unsafe_allow_html=True)
                st.markdown("### ✅ Correct!")
                if last_item['correct_answer'] == "PROPER":
                    st.markdown("**This question is PROPER.**")
                else:
                    st.markdown("**Objection sustained!**")
                st.markdown(f"**Reason:** {last_item['reason']}")
                st.markdown(f"**Explanation:** {last_item['explanation']}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="incorrect-answer">', unsafe_allow_html=True)
                st.markdown("### ❌ Incorrect")
                if last_item['correct_answer'] == "PROPER":
                    st.markdown("**Objection overruled. This question is PROPER.**")
                else:
                    st.markdown("**You should have objected! This question is IMPROPER.**")
                st.markdown(f"**Reason:** {last_item['reason']}")
                st.markdown(f"**Explanation:** {last_item['explanation']}")
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