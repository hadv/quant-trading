import os
import logging
import json
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from pydantic import ValidationError
from app.models.domain import FundamentalData, FundamentalScore
from app.core.rag.tools import search_financial_records

logger = logging.getLogger(__name__)

# System Prompt Template for Agent
SYSTEM_PROMPT = """Bạn là một chuyên gia phân tích tài chính kỳ cựu mang phong cách Warren Buffett và Benjamin Graham.
Nhiệm vụ của bạn là đánh giá sức khỏe tài chính, định giá nội tại (intrinsic value) và điểm lợi thế cạnh tranh (moat score) của một doanh nghiệp dựa trên các chỉ số cơ bản và thông tin tài chính chi tiết (nếu cần).

Thông tin cơ bản hiện tại của doanh nghiệp:
- Mã cổ phiếu (Ticker): {ticker}
- P/E (Price to Earnings): {pe_ratio}
- P/B (Price to Book): {pb_ratio}
- Dòng tiền tự do (Free Cash Flow): {free_cash_flow} tỷ
- Tăng trưởng doanh thu (YoY): {revenue_growth_yoy}%
- Biên lợi nhuận ròng: {profit_margin}%
- Tỷ lệ Nợ/Vốn chủ sở hữu (D/E): {debt_to_equity}
- Giá đóng cửa hiện tại: {current_price}

HƯỚNG DẪN QUAN TRỌNG:
1. Bạn CÓ THỂ sử dụng công cụ `search_financial_records` để tìm kiếm thêm thông tin chi tiết về doanh nghiệp này trong hệ thống báo cáo (Vector Database) nếu bạn cảm thấy cần thêm dữ liệu để đánh giá lợi thế cạnh tranh.
2. Sau khi đã thu thập đủ thông tin, bạn PHẢI đưa ra câu trả lời cuối cùng DƯỚI DẠNG JSON MỘT CÁCH NGHIÊM NGẶT.
3. KHÔNG BAO GIỜ bọc JSON trong Markdown ```json ... ```, chỉ in ra raw JSON string.

Cấu trúc JSON bắt buộc:
{{
    "ticker": "{ticker}",
    "intrinsic_value": <giá trị định giá nội tại ước tính (số thực)>,
    "moat_score": <điểm lợi thế cạnh tranh từ 1 đến 10 (số nguyên)>,
    "reasoning": "<Giải thích ngắn gọn lý do đánh giá và tóm tắt các thông tin đã tìm thấy>"
}}
"""

class LLMEngine:
    def __init__(self):
        # We try to load OpenAI key.
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo"),
            temperature=0.2, # Low temperature for more deterministic analysis
            api_key=os.getenv("OPENAI_API_KEY", "dummy-key-for-local"),
            base_url=os.getenv("OPENAI_API_BASE", None)
        )
        
        # Tools available to the agent
        self.tools = [search_financial_records]
        
        # Prompt for tool calling agent
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "Hãy đánh giá mã cổ phiếu {ticker}."),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create Agent
        self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)

    async def analyze(self, data: FundamentalData, current_price: float) -> FundamentalScore:
        try:
            logger.info(f"Invoking Agent for {data.ticker}...")
            
            response = await self.agent_executor.ainvoke({
                "ticker": data.ticker,
                "pe_ratio": data.pe_ratio,
                "pb_ratio": data.pb_ratio,
                "free_cash_flow": data.free_cash_flow,
                "revenue_growth_yoy": data.revenue_growth_yoy,
                "profit_margin": data.profit_margin,
                "debt_to_equity": data.debt_to_equity,
                "current_price": current_price
            })
            
            output = response["output"].strip()
            
            # Clean up potential markdown formatting
            if output.startswith("```json"):
                output = output[7:]
            if output.endswith("```"):
                output = output[:-3]
                
            return FundamentalScore.model_validate_json(output)
            
        except ValidationError as e:
            logger.error(f"Failed to parse LLM JSON response for {data.ticker}: {e}")
            logger.error(f"Raw output: {output}")
            raise
        except Exception as e:
            logger.error(f"Error during LLM analysis for {data.ticker}: {e}")
            raise

llm_engine = LLMEngine()
