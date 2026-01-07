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
    st.error("⚠️ **API Key Not Found** - Please configure your OpenAI API key")
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

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
    # Meta-information patterns to remove
    meta_patterns = [
        # Dedications and honors
        "in honor of", "dedicated to", "in memory of", "this case honors",
        # Authorship
        "written by", "authored by", "created by", "developed by",
        # Competition info
        "mock trial competition", "competition rules", "tournament",
        # Instructions
        "judge instructions", "scoring", "time limit", "points",
        # Educational
        "for educational purposes", "learning objectives",
        # Case creation metadata
        "case writer", "based on", "inspired by",
        # Copyright and admin
        "copyright", "all rights reserved", "©",
        # Page numbers and formatting
        "page ", "exhibit ", "stipulation"
    ]
    
    lines = case_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_lower = line.strip().lower()
        
        # Skip empty or very short lines
        if len(line_lower) < 15:
            continue
        
        # Skip lines with meta-patterns
        has_meta = any(pattern in line_lower for pattern in meta_patterns)
        if has_meta:
            continue
        
        # Skip lines that are all caps (usually headers/instructions)
        if line.strip().isupper() and len(line.strip()) > 5:
            continue
        
        # Keep this line
        cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove multiple blank lines
    while '\n\n\n' in cleaned_text:
        cleaned_text = cleaned_text.replace('\n\n\n', '\n\n')
    
    return cleaned_text.strip()

def smart_summarize_case(case_text):
    """
    Use AI to condense while preserving ALL legal content.
    Only triggers for very long cases.
    """
    if len(case_text) <= 20000:  # Increased threshold
        return case_text
    
    summary_prompt = f"""You are extracting ONLY the legal case content from this document.

RULES - FOLLOW EXACTLY:
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
            temperature=0.1,  # Very low - maximum factuality
            max_tokens=6000
        )
        return response.choices[0].message.content
    except:
        return case_text[:20000]

def estimate_cost(tokens):
    """Calculate estimated API cost"""
    return (tokens / 1000) * 0.00175

def call_openai(system_prompt, user_prompt, max_tokens=2400, temperature=0.25):
    """
    Make OpenAI API call with maximum hallucination prevention.
    Temperature 0.25 = extremely factual (was 0.35)
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
            presence_penalty=0.2,  # Increased - discourages new topics
            frequency_penalty=0.0  # Allow repeating case facts
        )
        
        # Check if response was truncated
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
    
    # Process input
    if uploaded_file:
        with st.spinner("📄 Extracting text from PDF..."):
            case_text = extract_text_from_pdf(uploaded_file)
            if case_text:
                st.success(f"✅ Extracted {len(case_text):,} characters")
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
            st.error("⚠️ Please provide case text")
            st.stop()
        
        if analysis_type == "Witness Questions" and not witness_name_input:
            st.error("⚠️ Please enter witness name")
            st.stop()
        
        with st.spinner("🔍 Processing and cleaning case packet..."):
            # CRITICAL: Aggressive preprocessing
            case_text_cleaned = aggressive_preprocess(case_text)
            
            if len(case_text_cleaned) > 20000:
                st.info("📋 Condensing lengthy case while preserving all facts...")
                case_text_processed = smart_summarize_case(case_text_cleaned)
            else:
                case_text_processed = case_text_cleaned
        
        # MAXIMUM ANTI-HALLUCINATION SYSTEM PROMPT
        base_system = """You are an expert Mock Trial coach. You analyze ONLY what is explicitly written in the case packet.

ABSOLUTE RULES - VIOLATIONS ARE UNACCEPTABLE:

1. ONLY STATE FACTS EXPLICITLY WRITTEN IN THE CASE PACKET
   - If you're not 100% certain a fact is in the case, DO NOT include it
   - Quote directly when possible
   - Cite sources (witness name, exhibit number)

2. NEVER INVENT OR ASSUME:
   - Do not invent case citations or legal precedents
   - Do not assume facts not stated
   - Do not add details from your general knowledge
   - Do not reference people mentioned in dedications/honors as case participants

3. DISTINGUISH META-INFO FROM CASE CONTENT:
   - Dedications, honors, authorship = NOT part of case
   - Competition rules, instructions = NOT part of case
   - ONLY analyze the legal dispute, parties, witnesses, evidence

4. WHEN UNCERTAIN:
   - State "This is not specified in the case packet"
   - Do not guess or infer beyond what's written
   - Acknowledge gaps in information

5. ACCURACY OVER COMPLETENESS:
   - Better to provide less information that's accurate
   - Than more information with invented details

Your analysis must be 100% grounded in the case packet provided."""

        # IMPROVED PROMPTS WITH EVEN STRONGER CONSTRAINTS
        prompts = {
            "Full Case Analysis": f"""Analyze this case using ONLY information explicitly stated below.

BEFORE YOU START:
1. Read the entire case carefully
2. Identify: Who are the actual PARTIES? Who are the WITNESSES?
3. Ignore any dedications, honors, or case creation information

PROVIDE:

**1. CASE OVERVIEW**
- Parties in the case (plaintiff/defendant or prosecution/defendant)
- Charges or claims
- Key dates and locations

**2. CRITICAL FACTS (15-20 facts)**
For each fact:
- State the fact with exact details
- Quote source if from testimony: "According to [Witness], '[exact quote]'"
- Explain legal significance
- Note which side it helps
- Cite source (witness name or exhibit)

Focus on: disputed facts, contradictions, timeline issues, credibility problems

**3. LEGAL ISSUES**
- What must be proven?
- Key legal questions
- Burden of proof considerations

**4. PROSECUTION/PLAINTIFF STRATEGY**
- Theory of the case (based on their evidence)
- Strongest arguments (cite specific evidence)
- How they address weaknesses

**5. DEFENSE STRATEGY**
- Theory of the case (based on their evidence)
- Strongest arguments (cite specific evidence)
- How they create doubt

**6. WITNESS CREDIBILITY**
For key witnesses:
- What they claim (with quotes)
- Credibility strengths
- Credibility weaknesses
- Contradictions with other evidence

**7. EVIDENCE EVALUATION**
- Key exhibits and what they show
- Corroboration or contradictions
- Admissibility considerations

**8. STRATEGIC INSIGHTS**
- Critical points for each side
- Vulnerabilities to exploit
- Areas needing more development

REMEMBER: Quote the case. Cite sources. No inventions.

===CASE PACKET BEGINS===
{case_text_processed}
===CASE PACKET ENDS===

Analyze using ONLY the information between the markers above.""",

            "Key Facts Only": f"""Extract the 20 most legally significant facts from this case.

INSTRUCTIONS:
1. Read the case carefully
2. Identify ONLY facts explicitly stated
3. Focus on: disputed facts, contradictions, timeline issues, evidence problems

For EACH fact (numbered 1-20):

**FACT #X: [Specific fact]**
- Quote: "[Exact quote from case if applicable]"
- Source: [Witness name or exhibit number]
- Legal significance: [Why this matters for proving/disproving elements]
- Strategic value: [Which side this helps and why]

CRITICAL: Do not invent facts. If uncertain, skip to next fact.

===CASE PACKET===
{case_text_processed}
===END CASE PACKET===

Provide 20 facts with analysis.""",

            "Legal Issues": f"""Identify the key legal issues using ONLY information from this case.

For each issue:

**ISSUE #X: [Legal question]**
- Elements to prove: [What must be shown]
- Prosecution/Plaintiff evidence: [Specific facts from case]
- Defense evidence: [Specific facts from case]
- Analysis: [Which side has stronger position based on case facts]

Do not cite legal cases not mentioned in the packet.

===CASE PACKET===
{case_text_processed}
===END===

Analyze based only on this case.""",

            "Prosecution Arguments": f"""Develop 5 prosecution/plaintiff arguments using ONLY case facts.

FIRST: Confirm the charges and what must be proven.

For each argument:

**ARGUMENT #X: [Clear argument statement]**

Evidence supporting this argument:
- Witness testimony: "[Quote]" - [Witness name]
- Physical evidence: [Specific exhibit with details]
- Additional facts: [From case]

Why this is strong:
- [Logical reasoning based on evidence]
- [Corroboration from multiple sources]

Defense counter-arguments:
- [Based on defense evidence in case]

Prosecution response:
- [Using case facts]

CRITICAL: All evidence must be from the case. No inventions.

===CASE PACKET===
{case_text_processed}
===END===

5 arguments with case-based evidence only.""",

            "Defense Arguments": f"""Develop 5 defense arguments using ONLY case facts.

FIRST: Confirm what prosecution must prove and defense position.

For each argument:

**ARGUMENT #X: [Clear argument statement]**

Evidence supporting this argument:
- Witness testimony: "[Quote]" - [Witness name]
- Physical evidence: [Specific exhibit with details]
- Gaps in prosecution case: [What they cannot prove]
- Contradictions: [Specific inconsistencies in prosecution evidence]

Why this creates reasonable doubt:
- [Logical reasoning based on evidence]
- [Alternative explanations supported by case facts]

Prosecution counter-arguments:
- [Based on prosecution evidence in case]

Defense response:
- [Using case facts]

CRITICAL: All evidence must be from the case. No inventions.

===CASE PACKET===
{case_text_processed}
===END===

5 arguments with case-based evidence only.""",

            "Witness Questions": f"""Generate strategic questions for witness: {witness_name_input}

FIRST: Verify {witness_name_input} is actually a WITNESS in this case (not a case creator, dedicatee, or judge).

If {witness_name_input} is a witness in the case:

**WITNESS BACKGROUND**
- Role in case: [What they witnessed/know]
- Key testimony points: [From their statement]
- Credibility issues: [Bias, inconsistency, etc.]

**DIRECT EXAMINATION (10 questions)**
- Foundation questions
- Fact-establishing questions
- Credibility-building questions

For each: [Purpose] and [What it establishes]

**CROSS-EXAMINATION (10 questions)**
- Leading questions to control witness
- Questions exposing contradictions
- Impeachment questions

For each: [Strategic goal] and [Expected answer]

If {witness_name_input} is NOT a witness:
State: "{witness_name_input} is not identified as a witness in this case packet."

===CASE PACKET===
{case_text_processed}
===END===

Base all questions on their actual testimony in the case.""",

            "Opening Statement Ideas": f"""Draft opening statement frameworks using ONLY case facts.

**PROSECUTION/PLAINTIFF OPENING:**

1. Hook (30 seconds)
   - [Compelling opening based on case events]
   - [Theme from case facts]

2. Charges (1 minute)
   - [Actual charges from case]
   - [Elements that must be proven]

3. Story (3 minutes)
   - [Timeline from case]
   - [Key events in narrative form]
   - Quote key evidence

4. Evidence Preview (2 minutes)
   - Witness by witness: what each will testify to (from case)
   - Key exhibits: what each shows (from case)

5. Closing Line
   - [Powerful statement based on case theme]

**DEFENSE OPENING:**

1. Hook (30 seconds)
   - [Defense theme from case]
   - [Presumption of innocence]

2. Burden (1 minute)
   - [What prosecution must prove]
   - [Why burden not met - based on case gaps]

3. Defense Story (3 minutes)
   - [Alternative narrative from defense evidence]
   - [Highlighting prosecution weaknesses]

4. Evidence Preview (2 minutes)
   - Defense evidence (from case)
   - Prosecution gaps and contradictions (from case)

5. Closing Line
   - [Reasonable doubt statement]

All suggestions must use actual case facts and evidence.

===CASE PACKET===
{case_text_processed}
===END===

Use only case facts.""",

            "Closing Statement Ideas": f"""Draft closing argument frameworks using ONLY case facts.

**PROSECUTION/PLAINTIFF CLOSING:**

1. Opening Hook
   - [Emotional appeal based on case events]

2. Elements Proven (element by element)
   - Element 1: [Evidence from case that proves it]
   - Element 2: [Evidence from case that proves it]
   - [Continue for all elements]

3. Credibility
   - Why prosecution witnesses are credible: [Based on their testimony]
   - Why defense witnesses are not: [Based on contradictions in case]

4. Defense Rebuttal
   - [Address defense arguments using case facts]

5. Final Appeal
   - [Justice-based closing using case]

**DEFENSE CLOSING:**

1. Opening Hook
   - [Reasonable doubt reminder]

2. Burden Not Met (element by element)
   - Element 1: [Why not proven beyond reasonable doubt - case gaps]
   - Element 2: [Why not proven - contradictions/weaknesses]
   - [Continue for all elements]

3. Credibility
   - Problems with prosecution witnesses: [From case]
   - Defense evidence is credible: [From case]

4. Prosecution Rebuttal
   - [Address prosecution arguments using case facts]

5. Final Appeal
   - [Reasonable doubt exists - must acquit]

All arguments must cite specific case evidence.

===CASE PACKET===
{case_text_processed}
===END===

Use only case facts."""
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
                temperature=0.25  # Very low for maximum accuracy
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
1. You are a WITNESS - not a judge, not a case creator, not anyone else
2. Answer ONLY based on {witness_name}'s witness statement in the case below
3. Stay 100% consistent with what {witness_name} said in their testimony
4. If asked about something {witness_name} wouldn't know: "I don't know" or "I don't recall"
5. For improper questions: "OBJECTION: [specific procedural reason]"
6. Do NOT invent facts not in {witness_name}'s testimony

Examination type: {exam_type}

===CASE CONTENT===
{case_text_processed}
===END CASE===

You are {witness_name}. Respond only based on what {witness_name} testified to in the case above."""
                    
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
                    recent_history = st.session_state.conversation_history[-3:]  # Last 3 only
                    conversation = "\n".join([
                        f"Q: {ex['question']}\nA: {ex['answer']}"
                        for ex in recent_history
                    ])
                    
                    full_prompt = f"""{st.session_state.witness_context}

Previous questions:
{conversation}

New question: {user_question}

Respond as {st.session_state.witness_name}:
- If improper question: "OBJECTION: [reason]"
- If proper: Answer based ONLY on {st.session_state.witness_name}'s testimony in the case
- Stay in character
- Do NOT invent facts"""
                    
                    system_msg = f"You are {st.session_state.witness_name}, a witness in this case. Answer ONLY based on what {st.session_state.witness_name} testified to. Do not invent information. Object to improper questions."
                    
                    answer, tokens = call_openai(
                        system_msg, 
                        full_prompt, 
                        max_tokens=180,
                        temperature=0.3  # Low temp for witness consistency
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
                - Use leading questions (suggest the answer)
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