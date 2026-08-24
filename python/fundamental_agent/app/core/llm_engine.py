import os
import logging
import json
import asyncio
from typing import TypedDict, List, Tuple
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langgraph.graph import StateGraph, END
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

PLANNER_PROMPT = """Bạn là một chuyên gia lập kế hoạch đầu tư.
Nhiệm vụ của bạn là lập ra một kế hoạch TỐI ĐA 3 BƯỚC để đánh giá Lợi thế cạnh tranh (Moat Score) của mã cổ phiếu {ticker}.
Mục tiêu là tìm ra ưu điểm, rủi ro và chiến lược dài hạn.
Các bước có thể bao gồm việc đọc báo cáo 10-K, 10-Q, và tìm kiếm thông tin vector.
Hãy trả về JSON chứa mảng `steps` liệt kê các bước cần thực hiện một cách ngắn gọn, rõ ràng.
"""

class Plan(BaseModel):
    steps: List[str] = Field(description="Các bước cần thực hiện để đánh giá Moat.")

EXECUTOR_PROMPT = """Bạn là chuyên gia phân tích dữ liệu và sử dụng công cụ.
Nhiệm vụ hiện tại của bạn là thực hiện bước sau đây cho cổ phiếu {ticker}:
{current_step}

Đây là các bước đã thực hiện và kết quả thu được trước đó:
{past_steps}

Hãy thực hiện nhiệm vụ, sử dụng công cụ nếu cần để tìm kiếm thông tin, và trả về kết quả quan sát của bạn một cách súc tích.
"""

MOAT_SYNTHESIZER_PROMPT = """Bạn là chuyên gia phân tích chiến lược kinh doanh (phong cách Philip Fisher).
Nhiệm vụ của bạn là đánh giá lợi thế cạnh tranh (Moat Score từ 1 đến 10) của doanh nghiệp {ticker}.
Dưới đây là các bước đã thực hiện và dữ liệu thu thập được:
{past_steps}

Hãy phân tích toàn bộ dữ liệu trên và trả về kết quả định dạng JSON.
Cấu trúc bắt buộc:
{{
    "moat_score": <số nguyên từ 1 đến 10>,
    "moat_reasoning": "<lập luận đánh giá dựa trên dữ liệu>"
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

# --- Agent State ---
class AgentState(TypedDict):
    ticker: str
    plan: List[str]
    past_steps: List[Tuple[str, str]]
    moat_score: int
    moat_reasoning: str

class LLMEngine:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY", "dummy-key-for-local")
        
        self.dcf_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=api_key)
        self.moat_llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2, google_api_key=api_key)
        self.synthesizer_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0, google_api_key=api_key)
        
        # --- DCF Chain ---
        self.dcf_prompt = ChatPromptTemplate.from_messages([
            ("system", DCF_SYSTEM_PROMPT),
            ("user", "Hãy tính giá trị nội tại cho {ticker}.")
        ])
        self.dcf_chain = self.dcf_prompt | self.dcf_llm.with_structured_output(DCFResult)
        
        # --- Plan-and-Solve Moat Graph ---
        self.tools = [search_vector_database, get_full_financial_report]
        
        executor_prompt = ChatPromptTemplate.from_messages([
            ("system", EXECUTOR_PROMPT),
            ("user", "Hãy thực hiện nhiệm vụ: {current_step}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        self.step_agent = create_tool_calling_agent(self.moat_llm, self.tools, executor_prompt)
        self.step_executor = AgentExecutor(agent=self.step_agent, tools=self.tools, verbose=True)
        
        self.moat_app = self._build_moat_graph()
        
        # --- Synthesizer ---
        self.synth_prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIZER_PROMPT),
            ("user", "Tổng hợp báo cáo cho {ticker}.")
        ])
        self.synth_chain = self.synth_prompt | self.synthesizer_llm.with_structured_output(FundamentalScore)

    def _build_moat_graph(self):
        workflow = StateGraph(AgentState)
        
        async def plan_node(state: AgentState):
            ticker = state["ticker"]
            prompt = ChatPromptTemplate.from_messages([
                ("system", PLANNER_PROMPT),
                ("user", "Hãy lập kế hoạch cho {ticker}")
            ])
            planner = prompt | self.dcf_llm.with_structured_output(Plan)
            plan_obj = await planner.ainvoke({"ticker": ticker})
            logger.info(f"Plan generated for {ticker}: {plan_obj.steps}")
            return {"plan": plan_obj.steps, "past_steps": []}
            
        async def execute_step_node(state: AgentState):
            plan = list(state["plan"])
            past_steps = list(state["past_steps"])
            ticker = state["ticker"]
            
            if not plan:
                return {"plan": plan, "past_steps": past_steps}
                
            current_step = plan.pop(0)
            logger.info(f"Executing Moat step for {ticker}: {current_step}")
            past_steps_str = "\n".join([f"Step: {s}\nResult: {r}" for s, r in past_steps]) if past_steps else "Chưa có bước nào."
            
            try:
                step_result = await self.step_executor.ainvoke({
                    "ticker": ticker,
                    "current_step": current_step,
                    "past_steps": past_steps_str
                })
                output = step_result.get("output", "No output returned")
            except Exception as e:
                logger.error(f"Error executing step '{current_step}': {e}")
                output = f"Lỗi trong quá trình thực thi: {e}"
                
            past_steps.append((current_step, output))
            return {"plan": plan, "past_steps": past_steps}
            
        async def synthesize_moat_node(state: AgentState):
            ticker = state["ticker"]
            past_steps = state["past_steps"]
            past_steps_str = "\n".join([f"Step: {s}\nResult: {r}" for s, r in past_steps])
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", MOAT_SYNTHESIZER_PROMPT),
                ("user", "Dựa trên dữ liệu thu thập được, hãy đánh giá Moat Score cho {ticker}.")
            ])
            synth = prompt | self.moat_llm.with_structured_output(MoatResult)
            
            logger.info(f"Synthesizing Moat Result for {ticker}...")
            try:
                result = await synth.ainvoke({"ticker": ticker, "past_steps": past_steps_str})
                return {"moat_score": result.moat_score, "moat_reasoning": result.moat_reasoning}
            except Exception as e:
                logger.error(f"Failed to synthesize Moat: {e}")
                return {"moat_score": 5, "moat_reasoning": "Lỗi tổng hợp dữ liệu."}
            
        def route_next(state: AgentState):
            if len(state["plan"]) == 0:
                return "synthesize"
            return "execute"
            
        workflow.add_node("planner", plan_node)
        workflow.add_node("execute", execute_step_node)
        workflow.add_node("synthesize", synthesize_moat_node)
        
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "execute")
        workflow.add_conditional_edges("execute", route_next)
        workflow.add_edge("synthesize", END)
        
        return workflow.compile()

    async def analyze(self, data: FundamentalData, current_price: float) -> FundamentalScore:
        logger.info(f"Invoking Parallel MoE Experts for {data.ticker}...")
        
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
        
        moat_task = self.moat_app.ainvoke({
            "ticker": data.ticker,
            "plan": [],
            "past_steps": [],
            "moat_score": 0,
            "moat_reasoning": ""
        })
        
        dcf_result, moat_state = await asyncio.gather(dcf_task, moat_task)
        
        moat_result = MoatResult(
            moat_score=moat_state.get("moat_score", 5),
            moat_reasoning=moat_state.get("moat_reasoning", "Lỗi hoặc không có thông tin.")
        )
            
        logger.info(f"Synthesizing final results for {data.ticker}...")
        final_score = await self.synth_chain.ainvoke({
            "ticker": data.ticker,
            "dcf_report": dcf_result.model_dump_json() if dcf_result else "{}",
            "moat_report": moat_result.model_dump_json(),
            "intrinsic_value": dcf_result.intrinsic_value if dcf_result else current_price,
            "moat_score": moat_result.moat_score
        })
        
        return final_score

llm_engine = LLMEngine()
