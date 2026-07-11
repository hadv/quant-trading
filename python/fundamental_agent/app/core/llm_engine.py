import os
import logging
import json
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from pydantic import ValidationError
from app.models.domain import FundamentalData, FundamentalScore, DCFResult, MoatResult
from app.core.rag.tools import search_vector_database, get_full_financial_report

logger = logging.getLogger(__name__)

# --- System Prompts ---
DCF_SYSTEM_PROMPT = """Bạn là một chuyên gia toán tài chính và định giá nội tại.
Nhiệm vụ của bạn là tính toán giá trị nội tại (intrinsic value) của doanh nghiệp.
Bạn KHÔNG cần quan tâm đến rủi ro thị trường hay lợi thế cạnh tranh. Chỉ tập trung vào số liệu.
Cổ phiếu: {ticker}
Giá hiện tại: {current_price}
P/E: {pe_ratio}, P/B: {pb_ratio}
FCF: {free_cash_flow} tỷ, Tăng trưởng: {revenue_growth_yoy}%
Biên lợi nhuận: {profit_margin}%, D/E: {debt_to_equity}
Phân tích cẩn thận và trả về JSON chuẩn khớp với cấu trúc được yêu cầu.
"""

MOAT_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích chiến lược kinh doanh (phong cách Philip Fisher).
Nhiệm vụ của bạn là đánh giá lợi thế cạnh tranh (Moat Score từ 1 đến 10) của doanh nghiệp.
Cổ phiếu: {ticker}.
Sử dụng công cụ `get_full_financial_report` để lấy toàn văn báo cáo tài chính (10-K, 10-Q) nhằm phân tích sâu chiến lược dài hạn.
Sử dụng công cụ `search_vector_database` để tìm kiếm các tin tức ngắn, sự kiện rủi ro gần đây.
KHÔNG bọc JSON trong Markdown ```json ... ```, chỉ in ra raw JSON string.
Cấu trúc bắt buộc:
{{
    "moat_score": <số nguyên từ 1 đến 10>,
    "moat_reasoning": "<lập luận đánh giá>"
}}
"""

SYNTHESIZER_PROMPT = """Bạn là Tổng Giám Đốc Đầu Tư.
Bạn nhận được báo cáo từ 2 chuyên gia:
- Chuyên gia định giá (DCF):
{dcf_report}

- Chuyên gia lợi thế cạnh tranh (Moat):
{moat_report}

Hãy tổng hợp lại thành một FundamentalScore cuối cùng (JSON).
Ticker: {ticker}
Intrinsic Value: {intrinsic_value}
Moat Score: {moat_score}
Viết `reasoning` kết hợp lập luận của cả 2 chuyên gia một cách súc tích.
"""

class LLMEngine:
    def __init__(self):
        # Setup Gemini Models
        api_key = os.getenv("GOOGLE_API_KEY", "dummy-key-for-local")
        
        # Chuyên gia DCF: Cần tốc độ và tính logic toán học (gemini-flash)
        self.dcf_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.0,
            google_api_key=api_key
        )
        
        # Chuyên gia Moat: Cần khả năng đọc hiểu dài và RAG (gemini-pro)
        self.moat_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.2,
            google_api_key=api_key
        )
        
        # Synthesizer: Đơn giản là tổng hợp (gemini-flash)
        self.synthesizer_llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.0,
            google_api_key=api_key
        )
        
        # --- DCF Chain ---
        self.dcf_prompt = ChatPromptTemplate.from_messages([
            ("system", DCF_SYSTEM_PROMPT),
            ("user", "Hãy tính giá trị nội tại cho {ticker}.")
        ])
        self.dcf_chain = self.dcf_prompt | self.dcf_llm.with_structured_output(DCFResult)
        
        # --- Moat Agent ---
        self.tools = [search_vector_database, get_full_financial_report]
        self.moat_prompt = ChatPromptTemplate.from_messages([
            ("system", MOAT_SYSTEM_PROMPT),
            ("user", "Hãy đánh giá Moat Score cho {ticker}."),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        self.moat_agent = create_tool_calling_agent(self.moat_llm, self.tools, self.moat_prompt)
        self.moat_executor = AgentExecutor(agent=self.moat_agent, tools=self.tools, verbose=True)
        
        # --- Synthesizer ---
        self.synth_prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIZER_PROMPT),
            ("user", "Tổng hợp báo cáo cho {ticker}.")
        ])
        self.synth_chain = self.synth_prompt | self.synthesizer_llm.with_structured_output(FundamentalScore)

    async def analyze(self, data: FundamentalData, current_price: float) -> FundamentalScore:
        logger.info(f"Invoking Parallel MoE Experts for {data.ticker}...")
        
        # 1. Run Experts in Parallel
        dcf_task = self.dcf_chain.ainvoke({
            "ticker": data.ticker,
            "pe_ratio": data.pe_ratio,
            "pb_ratio": data.pb_ratio,
            "free_cash_flow": data.free_cash_flow,
            "revenue_growth_yoy": data.revenue_growth_yoy,
            "profit_margin": data.profit_margin,
            "debt_to_equity": data.debt_to_equity,
            "current_price": current_price
        })
        
        moat_task = self.moat_executor.ainvoke({
            "ticker": data.ticker
        })
        
        # Execute both concurrently
        dcf_result, moat_response = await asyncio.gather(dcf_task, moat_task)
        
        # Parse moat_result manually since it goes through AgentExecutor
        try:
            output = moat_response["output"].strip()
            if output.startswith("```json"):
                output = output[7:]
            if output.endswith("```"):
                output = output[:-3]
            moat_result = MoatResult.model_validate_json(output)
        except Exception as e:
            logger.warning(f"Failed to parse Moat JSON, using default: {e}")
            moat_result = MoatResult(moat_score=5, moat_reasoning=f"Agent Output: {moat_response.get('output', '')}")
            
        # 2. Synthesize
        logger.info(f"Synthesizing results for {data.ticker}...")
        final_score = await self.synth_chain.ainvoke({
            "ticker": data.ticker,
            "dcf_report": dcf_result.model_dump_json() if dcf_result else "{}",
            "moat_report": moat_result.model_dump_json(),
            "intrinsic_value": dcf_result.intrinsic_value if dcf_result else current_price,
            "moat_score": moat_result.moat_score
        })
        
        return final_score

llm_engine = LLMEngine()
