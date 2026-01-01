import streamlit as st
import openai
# Custom CSS for better appearance
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        font-size: 16px;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .stButton>button:hover {
        background-color: #0052a3;
    }
</style>
""", unsafe_allow_html=True)
# ==========================================
# SETUP
# ==========================================

# Set page configuration
st.set_page_config(
    page_title="Mock Trial Case Analyzer",
    page_icon="⚖️",
    layout="wide"
)

# ==========================================
# SECURE API KEY LOADING
# ==========================================

import os

# Get API key from environment/secrets (NEVER hardcoded)
try:
    # Try Streamlit secrets first (production)
    api_key = st.secrets["OPENAI_API_KEY"]
except:
    # Fall back to environment variable (local development)
    api_key = os.getenv("OPENAI_API_KEY")

# Validate API key exists
if not api_key:
    st.error("""
    ⚠️ **API Key Not Found**
    
    Please set your OpenAI API key:
    - **For Streamlit Cloud:** Add to Secrets in deployment settings
    - **For local:** Create `.streamlit/secrets.toml` with your key
    
    See README for instructions.
    """)
    st.stop()

# Set the API key
openai.api_key = api_key

# ==========================================
# HEADER
# ==========================================

st.title("⚖️ Mock Trial Case Analyzer")
st.markdown("**AI-Powered Case Analysis for Mock Trial Teams**")
st.markdown("*Built by Vihaan Paka-Hegde - San Francisco University High School*")
st.markdown("---")

# ==========================================
# INSTRUCTIONS
# ==========================================

with st.expander("📖 How to Use This Tool"):
    st.markdown("""
    **Step 1:** Paste your case packet text in the box below
    
    **Step 2:** Choose what type of analysis you need
    
    **Step 3:** Click 'Analyze Case' and wait 10-20 seconds
    
    **Step 4:** Review the AI's analysis and download it if needed
    
    **Note:** This tool uses AI to assist with case preparation. Always verify 
    information and use your own legal reasoning!
    """)

# ==========================================
# MAIN INPUT
# ==========================================

st.subheader("📝 Case Packet Input")

case_text = st.text_area(
    "Paste your case packet text here:",
    height=300,
    placeholder="Paste the full text of your Mock Trial case packet here...",
    help="Include all witness statements, evidence, and relevant facts"
)

# ==========================================
# ANALYSIS OPTIONS
# ==========================================

st.subheader("🔍 Select Analysis Type")

col1, col2 = st.columns(2)

with col1:
    analysis_type = st.selectbox(
        "What do you need?",
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
    if analysis_type == "Witness Questions":
        witness_name = st.text_input(
            "Which witness?",
            placeholder="Enter witness name..."
        )

# ==========================================
# ANALYZE BUTTON
# ==========================================

if st.button("🚀 Analyze Case", type="primary"):
    
    # Check if user entered text
    if not case_text or len(case_text) < 50:
        st.error("⚠️ Please paste your case packet text first (at least 50 characters)")
        st.stop()
    
    # Check witness name if needed
    if analysis_type == "Witness Questions" and not witness_name:
        st.error("⚠️ Please enter a witness name")
        st.stop()
    
    # Show loading message
    with st.spinner("🤔 AI is analyzing your case... This takes 10-20 seconds..."):
        
        try:
            # ==========================================
            # CREATE PROMPTS BASED ON ANALYSIS TYPE
            # ==========================================
            
            if analysis_type == "Full Case Analysis":
                prompt = f"""You are an expert Mock Trial coach. Analyze this case packet and provide:

1. **KEY FACTS** (List the 10 most important facts)
2. **LEGAL ISSUES** (What are the main legal questions?)
3. **PROSECUTION THEORY** (What's the prosecution's best case?)
4. **DEFENSE THEORY** (What's the defense's best case?)
5. **CRITICAL EVIDENCE** (What evidence is most important?)
6. **KEY WITNESSES** (Who matters most and why?)

Case Packet:
{case_text}

Format your response with clear headers and bullet points."""

            elif analysis_type == "Key Facts Only":
                prompt = f"""Extract the 15 most important facts from this Mock Trial case packet.

Number each fact (1-15) and keep each to one clear sentence.

Prioritize facts that are:
- Legally significant
- Disputed between sides
- Critical for establishing elements of the case

Case Packet:
{case_text}"""

            elif analysis_type == "Legal Issues":
                prompt = f"""Identify the key legal issues in this Mock Trial case.

For each legal issue:
1. State the issue clearly
2. Explain why it matters legally
3. Note which side benefits from this issue

Case Packet:
{case_text}"""

            elif analysis_type == "Prosecution Arguments":
                prompt = f"""You are a prosecution attorney. Develop the 3 strongest arguments for the prosecution in this case.

For each argument:
1. State the argument clearly
2. List supporting facts from the case
3. Explain why this argument is compelling
4. Anticipate defense counter-arguments

Case Packet:
{case_text}"""

            elif analysis_type == "Defense Arguments":
                prompt = f"""You are a defense attorney. Develop the 3 strongest arguments for the defense in this case.

For each argument:
1. State the argument clearly
2. List supporting facts from the case
3. Explain why this argument is compelling
4. Anticipate prosecution counter-arguments

Case Packet:
{case_text}"""

            elif analysis_type == "Witness Questions":
                prompt = f"""Generate strategic examination questions for witness: {witness_name}

Provide:

**DIRECT EXAMINATION (If this is your witness):**
- 8 questions that establish helpful facts
- Include foundational questions (who are you, what did you see, etc.)

**CROSS EXAMINATION (If this is opposing witness):**
- 8 questions that undermine their testimony or establish your facts
- Use leading questions that control the witness

Case Packet:
{case_text}

Focus on witness: {witness_name}"""

            elif analysis_type == "Opening Statement Ideas":
                prompt = f"""Draft ideas for an opening statement for BOTH sides.

For each side (Prosecution and Defense):
1. Suggest a compelling opening hook (first 1-2 sentences)
2. Outline the theory of the case
3. Preview key evidence without arguing
4. Suggest a strong closing line

Remember: Openings preview evidence, they don't argue. Be persuasive but factual.

Case Packet:
{case_text}"""

            elif analysis_type == "Closing Statement Ideas":
                prompt = f"""Draft ideas for a closing argument for BOTH sides.

For each side (Prosecution and Defense):
1. Suggest a powerful opening (emotional hook)
2. Connect facts to legal elements that must be proven
3. Address key weaknesses in opposing case
4. Suggest a memorable final line

Remember: Closings argue and persuade based on evidence presented.

Case Packet:
{case_text}"""

            # ==========================================
            # CALL OPENAI API
            # ==========================================
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # Using gpt-3.5-turbo for better analysis
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Mock Trial coach with deep knowledge of legal strategy, evidence, and courtroom procedure. Provide clear, structured analysis that high school students can use for competition preparation. Be specific and cite facts from the case."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Get the AI's response
            result = response.choices[0].message.content
            
            # ==========================================
            # DISPLAY RESULTS
            # ==========================================
            
            st.success("✅ Analysis Complete!")
            st.markdown("---")
            
            # Show the analysis in a nice box
            st.markdown("### 📊 Analysis Results")
            st.markdown(result)
            
            # ==========================================
            # DOWNLOAD BUTTON
            # ==========================================
            
            st.markdown("---")
            st.download_button(
                label="📥 Download Analysis",
                data=result,
                file_name=f"mock_trial_analysis_{analysis_type.lower().replace(' ', '_')}.txt",
                mime="text/plain"
            )
            
            # Show token usage (so you know how much you're spending)
            tokens_used = response.usage.total_tokens
            estimated_cost = (tokens_used / 1000) * 0.03  # GPT-4 pricing
            
            st.caption(f"Tokens used: {tokens_used} | Estimated cost: ${estimated_cost:.4f}")
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.error("Check that your API key is correct and you have credit remaining")

# ==========================================
# FOOTER
# ==========================================

st.markdown("---")
st.markdown("""
**About This Tool**

This AI-powered case analyzer was built to democratize Mock Trial preparation. 
Teams with attorney coaches have advantages in case analysis—this tool aims to 
level the playing field by providing AI-assisted analysis to any team.

**Disclaimer:** This tool uses AI and may make mistakes. Always verify information 
and apply your own legal reasoning. Use this as a supplement to your preparation, 
not a replacement for critical thinking.

*Built with Python, Streamlit, and OpenAI GPT-4*
""")