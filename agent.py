from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash"
)

prompt = PromptTemplate(
    input_variables=["chat_history"],
    template="""
You are a professional meeting scheduling assistant analyzing Discord conversation history.

Chat History:
{chat_history}

INSTRUCTIONS:
1. Extract all mentioned dates, times, and timezones (explicit or implied)
2. Convert times to UTC and provide local time conversions
3. Identify participant preferences and constraints
4. Suggest 1-3 optimal meeting times based on group availability
5. Handle timezone ambiguity gracefully
6. Ignore off-topic messages
7. Include Day and Date only when mentioned

OUTPUT FORMAT (usethis structure):

📅 **Meeting Schedule Analysis**

**Recommended Time (UTC):** [Day, Date, Time UTC]
**Local Times:**
- [username]: [local time with timezone]
- [username]: [local time with timezone]

**Alternative Options:**
1. [Day, Date, Time UTC] - [brief reason]
2. [Day, Date, Time UTC] - [brief reason]

**Analysis:** [Brief 1-2 sentence summary of why this time works best]

---
FALLBACK RESPONSES:
- If no times mentioned: "⚠️ No specific times found in the conversation. Please discuss preferred meeting times and try again."
- If insufficient info: "⚠️ Found time mentions but need more details about participant availability. Please clarify preferences."
- If conflicting times: "⚠️ Multiple conflicting times suggested. Please discuss and align on preferred options."

Keep responses concise and professional. Focus on actionable scheduling information only.
"""
)
parser = StrOutputParser()

chain = prompt | llm | parser

