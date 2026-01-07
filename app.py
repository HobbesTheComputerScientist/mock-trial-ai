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
    This is the #1 defense against hallucination.
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
    if len(case_text) <= 20000:
        return case_text
    
    summary_prompt = f"""You are extracting ONLY the legal case content from this document.

RULES:
1. INCLUDE all charges, parties, witnesses, dates, locations, events, evidence, testimony
2. PRESERVE exact names, numbers, quotes
3. KEEP all contradictions and disputed facts
4. EXCLUDE dedications, author info, competition rules, instructions

Output ONLY the case facts. No preamble.

Document:
{case_text[:20000]}

Case content only:"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract case content only. Preserve all legal details. Remove meta-information."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.1,
            max_tokens=6000
        )
        return response.choices[0].message.content
    except Exception as e:
        st.warning(f"Summarization skipped: {str(e)}")
        return case_text[:20000]

def estimate_cost(tokens):
    """Calculate estimated API cost"""
    return (tokens / 1000) * 0.00175

def call_openai(system_prompt, user_prompt, max_tokens=2400, temperature=0.25):
    """
    Make OpenAI API call with maximum hallucination prevention.
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
            
            if len(case_text_cleaned) > 20000:
                st.info("📋 Condensing lengthy case while preserving all facts...")
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
        base_system = """You are an expert Mock Trial coach. You analyze ONLY what is explicitly written in the case packet.

ABSOLUTE RULES:

1. ONLY STATE FACTS EXPLICITLY WRITTEN IN THE CASE PACKET
2. NEVER INVENT OR ASSUME
3. DISTINGUISH META-INFO FROM CASE CONTENT
4. WHEN UNCERTAIN: State "This is not specified in the case packet"
5. ACCURACY OVER COMPLETENESS

Your analysis must be 100% grounded in the case packet provided."""

        prompts = {
            "Full Case Analysis": f"""Analyze this case using ONLY information explicitly stated below.

PROVIDE:

**1. CASE OVERVIEW**
- Parties and charges
- Key dates and locations

**2. CRITICAL FACTS (15-20 facts)**
For each fact:
- State the fact with exact details
- Quote source if from testimony
- Explain legal significance
- Note which side it helps
- Cite source

**3. LEGAL ISSUES**
- What must be proven?
- Key legal questions

**4. PROSECUTION/PLAINTIFF STRATEGY**
- Theory of the case
- Strongest arguments
- How they address weaknesses

**5. DEFENSE STRATEGY**
- Theory of the case
- Strongest arguments
- How they create doubt

**6. WITNESS CREDIBILITY**
For key witnesses:
- What they claim
- Credibility strengths/weaknesses
- Contradictions

**7. EVIDENCE EVALUATION**
- Key exhibits
- Corroboration or contradictions

**8. STRATEGIC INSIGHTS**
- Critical points for each side
- Vulnerabilities to exploit

===CASE PACKET===
{case_text_processed}
===END===

Analyze using ONLY the information above.""",

            "Key Facts Only": f"""Extract the 20 most legally significant facts from this case.

For EACH fact (numbered 1-20):

**FACT #X: [Specific fact]**
- Quote: "[Exact quote if applicable]"
- Source: [Witness name or exhibit]
- Legal significance: [Why this matters]
- Strategic value: [Which side this helps]

Do not invent facts.

===CASE PACKET===
{case_text_processed}
===END===

20 facts with analysis.""",

            "Legal Issues": f"""Identify key legal issues using ONLY information from this case.

For each issue:

**ISSUE #X: [Legal question]**
- Elements to prove
- Evidence for each side
- Analysis

Do not cite legal cases not mentioned.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Prosecution Arguments": f"""Develop 5 prosecution/plaintiff arguments using ONLY case facts.

For each argument:

**ARGUMENT #X: [Statement]**

Evidence:
- Witness testimony with quotes
- Physical evidence
- Additional facts

Why this is strong
Defense counter-arguments
Prosecution response

All evidence must be from the case.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Defense Arguments": f"""Develop 5 defense arguments using ONLY case facts.

For each argument:

**ARGUMENT #X: [Statement]**

Evidence:
- Witness testimony with quotes
- Physical evidence
- Gaps in prosecution case
- Contradictions

Why this creates reasonable doubt
Prosecution counter-arguments
Defense response

All evidence must be from the case.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Witness Questions": f"""Generate strategic questions for witness: {witness_name_input}

FIRST: Verify {witness_name_input} is actually a WITNESS in this case.

**WITNESS ANALYSIS**
- Role in case
- Key testimony points
- Credibility issues

**DIRECT EXAMINATION (10 questions)**
**CROSS-EXAMINATION (10 questions)**

If {witness_name_input} is NOT a witness:
State: "{witness_name_input} is not identified as a witness in this case packet."

===CASE PACKET===
{case_text_processed}
===END===""",

            "Opening Statement Ideas": f"""Draft opening statement frameworks using ONLY case facts.

**PROSECUTION/PLAINTIFF OPENING:**
1. Hook
2. Charges
3. Story
4. Evidence Preview
5. Closing Line

**DEFENSE OPENING:**
1. Hook
2. Burden
3. Defense Story
4. Evidence Preview
5. Closing Line

Use only case facts.

===CASE PACKET===
{case_text_processed}
===END===""",

            "Closing Statement Ideas": f"""Draft closing argument frameworks using ONLY case facts.

**PROSECUTION/PLAINTIFF CLOSING:**
1. Opening Hook
2. Elements Proven
3. Credibility
4. Defense Rebuttal
5. Final Appeal

**DEFENSE CLOSING:**
1. Opening Hook
2. Burden Not Met
3. Credibility
4. Prosecution Rebuttal
5. Final Appeal

Use only case facts.

===CASE PACKET===
{case_text_processed}
===END==="""
        }
        
        with st.spinner("🤔 Analyzing case (15-25 seconds)..."):
            if analysis_type in ["Full Case Analysis", "Key Facts Only", "Prosecution Arguments", "Defense Arguments"]:
                max_tokens_to_use = 2400
            else:
                max_tokens_to_use = 1800
            
            result, tokens = call_openai(
                base_system, 
                prompts[analysis_type],
                max_tokens=max_tokens_to_use,
                temperature=0.25
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
5. For improper questions: "OBJECTION: [reason]"
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
        
        col1, col2 = st.columns([3, 1])
        
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
- If improper: "OBJECTION: [reason]"
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
            if st.button("🔄 End"):
                st.session_state.cross_exam_mode = False
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown(f'<p class="cost-display">Session cost: ${st.session_state.total_cost:.4f}</p>', unsafe_allow_html=True)
        
        with st.expander("💡 Examination Tips"):
            if "Cross" in st.session_state.exam_type:
                st.markdown("""
                **Cross-Examination Rules:**
                - Use leading questions
                - One fact per question
                - Control the witness
                
                ✅ Good: "You were 50 feet away, correct?"
                ❌ Bad: "How far away were you?"
                """)
            else:
                st.markdown("""
                **Direct Examination Rules:**
                - Use open-ended questions
                - Let witness tell their story
                - No leading questions
                
                ✅ Good: "What did you observe?"
                ❌ Bad: "You saw the defendant, didn't you?"
                """)

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.caption("""
**About:** AI-powered mock trial preparation tool. The AI analyzes only facts explicitly stated in your case packet.

**Disclaimer:** AI-generated analysis may contain errors. Always verify information and use your own legal reasoning.

*Python • Streamlit • OpenAI GPT-3.5 • Built by Vihaan Paka-Hegde*
""")