from fastapi import FastAPI, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect
from fastapi.security.api_key import APIKeyHeader
from pymongo import MongoClient
from bson import json_util
import os
import logging
from typing import Optional, List, Set
from pydantic import BaseModel
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import asyncio # 导入 asyncio 用于定时任务
import random # 用于生成模拟数据
from datetime import datetime # 用于生成时间戳

# 加载环境变量
load_dotenv()

# 配置日志
# ... (日志配置与之前相同)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_access_enhanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# MongoDB 配置
# ... (MongoDB 配置与之前相同)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = "binance_trades"
TRADE_COLLECTION = "trade_history"
PORTFOLIO_COLLECTION = "portfolio_mappings"

# API Key 配置
# ... (API Key 配置与之前相同)
API_KEY = os.getenv("API_KEY", "your-secret-key")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


# FastAPI 应用
app = FastAPI(title="Binance Trade History Enhanced API with WebSocket")

# CORS Configuration
origins = ["*"] # 允许所有源，方便开发
# 注意：在生产环境中，你应该指定明确的源列表
# origins = [
#     "http://localhost",
#     "http://127.0.0.1",
#     "http://localhost:5500", # VS Code Live Server
#     "http://127.0.0.1:5500",
#     "null", # 允许 file://
#     # "你的前端部署域名"
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic 模型
# ... (Pydantic 模型与之前相同)
class Trade(BaseModel):
    symbol: str
    side: str
    positionSide: str
    price: float
    realizedProfit: float
    time: int # 毫秒时间戳
    portfolioId: str
    portfolioName: str

class Portfolio(BaseModel):
    portfolioId: str
    portfolioName: str

class PortfolioStats(BaseModel):
    portfolioId: str
    portfolioName: str
    totalTrades: int
    totalRealizedProfit: float
    averagePrice: float

# --- WebSocket 连接管理 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connection accepted: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket connection closed: {websocket.client}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error sending personal message to {websocket.client}: {e}")
            self.disconnect(websocket)


    async def broadcast(self, message: str):
        # 使用副本进行迭代，以防在迭代过程中列表被修改 (例如，客户端断开连接)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(connection)
                logger.info(f"Client {connection.client} disconnected during broadcast.")
            except Exception as e:
                logger.error(f"Error broadcasting to {connection.client}: {e}")
                # 考虑是否也在此处断开连接
                # self.disconnect(connection)


manager = ConnectionManager()
# --- 结束 WebSocket 连接管理 ---


# 验证 API Key
# ... (verify_api_key 与之前相同)
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        logger.warning("无效的 API Key")
        raise HTTPException(status_code=401, detail="无效的 API Key")
    return api_key


# MongoDB 连接
# ... (get_mongo_collections 与之前相同)
def get_mongo_collections():
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        trade_collection = db[TRADE_COLLECTION]
        portfolio_collection = db[PORTFOLIO_COLLECTION]
        return trade_collection, portfolio_collection
    except Exception as e:
        logger.error(f"MongoDB 连接错误: {e}")
        raise HTTPException(status_code=500, detail="无法连接到 MongoDB")

# 辅助函数：将 MongoDB 文档转换为 JSON
# ... (parse_mongo_doc 与之前相同)
def parse_mongo_doc(doc):
    return json.loads(json_util.dumps(doc))


# --- 模拟数据生成函数 ---
def generate_mock_trade_data() -> dict:
    """生成一条模拟的交易数据"""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
    sides = ["BUY", "SELL"]
    position_sides = ["LONG", "SHORT"]
    portfolio_ids = ["P001", "P002", "P003"]
    portfolio_names = {"P001": "Alpha Portfolio", "P002": "Beta Gains", "P003": "Crypto Futures"}

    pid = random.choice(portfolio_ids)
    return {
        "symbol": random.choice(symbols),
        "side": random.choice(sides),
        "positionSide": random.choice(position_sides),
        "price": round(random.uniform(0.1, 60000), 4),
        "realizedProfit": round(random.uniform(-100, 200), 4),
        "time": int(datetime.now().timestamp() * 1000), # 当前时间的毫秒时间戳
        "portfolioId": pid,
        "portfolioName": portfolio_names[pid]
    }
# --- 结束模拟数据生成函数 ---

# --- 后台任务：定时推送数据 ---
async def periodic_data_pusher():
    """每5秒向所有连接的WebSocket客户端推送模拟交易数据"""
    while True:
        await asyncio.sleep(5) # 等待5秒
        if manager.active_connections: # 仅当有活动连接时才推送
            mock_data_list = [generate_mock_trade_data() for _ in range(random.randint(1, 3))] # 推送1-3条数据
            
            # 验证数据是否符合 Pydantic 模型 (可选，但推荐)
            try:
                validated_data = [Trade(**data).model_dump() for data in mock_data_list]
                message_payload = json.dumps({"type": "new_trades", "data": validated_data})
                logger.info(f"Broadcasting new trades data: {len(validated_data)} items")
                await manager.broadcast(message_payload)
            except Exception as e: # 包括 Pydantic ValidationError
                 logger.error(f"Error preparing or validating mock data for broadcast: {e}")

@app.on_event("startup")
async def startup_event():
    """在应用启动时启动后台任务"""
    logger.info("Application startup: Starting periodic data pusher...")
    asyncio.create_task(periodic_data_pusher())
# --- 结束后台任务 ---


# --- WebSocket 端点 ---
@app.websocket("/ws/trades")
async def websocket_trades_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # 可以先发送一条欢迎消息或历史数据
    # await manager.send_personal_message(json.dumps({"message": "Connected to trades feed!"}), websocket)
    try:
        while True:
            # 服务器可以接收来自客户端的消息 (如果需要)
            # data = await websocket.receive_text()
            # logger.info(f"Received from {websocket.client}: {data}")
            # await manager.send_personal_message(f"You wrote: {data}", websocket)

            # 这里我们主要依赖后台任务进行推送，所以这个循环可以只是保持连接
            # 或者，如果客户端发送特定请求，可以在这里处理
            await asyncio.sleep(0.1) # 短暂休眠以允许其他任务运行，并检查连接状态
            # 检查连接是否仍然活跃 (虽然 send_text 会处理 WebSocketDisconnect)
            if websocket.client_state.value != 1: # 1 表示 CONNECTED
                 logger.info(f"WebSocket {websocket.client} state is not CONNECTED, breaking loop.")
                 break
    except WebSocketDisconnect:
        logger.info(f"Client {websocket.client} disconnected (WebSocketDisconnect exception).")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for {websocket.client}: {e}")
    finally:
        manager.disconnect(websocket)
# --- 结束 WebSocket 端点 ---


# --- HTTP API 端点 ---
# (你的 /trades, /trades/{portfolio_id}, /portfolios, /stats/portfolio/{portfolio_id} 端点与之前相同)
@app.get("/trades", response_model=List[Trade])
async def get_trades(
    portfolio_id: Optional[str] = None,
    portfolio_name: Optional[str] = None,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    position_side: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    page: int = 1,
    limit: int = 50,
    sort_by: str = "time",
    sort_order: str = "desc",
):
    trade_collection, _ = get_mongo_collections()
    query = {}
    if portfolio_id: query["portfolioId"] = portfolio_id
    if portfolio_name: query["portfolioName"] = portfolio_name
    if symbol: query["symbol"] = symbol
    if side: query["side"] = side.upper()
    if position_side: query["positionSide"] = position_side.upper()
    if start_time or end_time:
        query["time"] = {}
        if start_time: query["time"]["$gte"] = start_time
        if end_time: query["time"]["$lte"] = end_time

    if page < 1: raise HTTPException(status_code=400, detail="Page 必须大于 0")
    if limit < 1 or limit > 100: raise HTTPException(status_code=400, detail="Limit 必须在 1 到 100 之间")

    sort_field = sort_by if sort_by in ["time", "price", "realizedProfit"] else "time"
    sort_direction = -1 if sort_order.lower() == "desc" else 1

    try:
        trades_cursor = trade_collection.find(query).sort(sort_field, sort_direction).skip((page - 1) * limit).limit(limit)
        result = [parse_mongo_doc(trade) for trade in trades_cursor]
        logger.info(f"返回 {len(result)} 条交易记录 for query: {query}, page={page}, limit={limit}")
        return result
    except Exception as e:
        logger.error(f"查询交易记录错误: {e}")
        raise HTTPException(status_code=500, detail="查询交易记录失败")

@app.get("/trades/{portfolio_id}", response_model=List[Trade])
async def get_trades_by_portfolio(
    portfolio_id: str, page: int = 1, limit: int = 50,
    sort_by: str = "time", sort_order: str = "desc",
    api_key: str = Security(verify_api_key)
):
    trade_collection, _ = get_mongo_collections()
    if page < 1: raise HTTPException(status_code=400, detail="Page 必须大于 0")
    if limit < 1 or limit > 100: raise HTTPException(status_code=400, detail="Limit 必须在 1 到 100 之间")
    sort_field = sort_by if sort_by in ["time", "price", "realizedProfit"] else "time"
    sort_direction = -1 if sort_order.lower() == "desc" else 1
    try:
        trades_cursor = trade_collection.find({"portfolioId": portfolio_id}).sort(sort_field, sort_direction).skip((page - 1) * limit).limit(limit)
        result = [parse_mongo_doc(trade) for trade in trades_cursor]
        logger.info(f"返回 {len(result)} 条交易记录 for portfolioId={portfolio_id}, page={page}, limit={limit}")
        return result
    except Exception as e:
        logger.error(f"查询 portfolioId={portfolio_id} 交易记录错误: {e}")
        raise HTTPException(status_code=500, detail="查询交易记录失败")

@app.get("/portfolios", response_model=List[Portfolio])
async def get_portfolios(api_key: str = Security(verify_api_key)):
    _, portfolio_collection = get_mongo_collections()
    try:
        portfolios_cursor = portfolio_collection.find()
        result = [parse_mongo_doc(portfolio) for portfolio in portfolios_cursor]
        logger.info(f"返回 {len(result)} 个 portfolio 映射")
        return result
    except Exception as e:
        logger.error(f"查询 portfolio 映射错误: {e}")
        raise HTTPException(status_code=500, detail="查询 portfolio 映射失败")

@app.get("/stats/portfolio/{portfolio_id}", response_model=PortfolioStats)
async def get_portfolio_stats(portfolio_id: str, api_key: str = Security(verify_api_key)):
    trade_collection, portfolio_collection = get_mongo_collections()
    try:
        portfolio = portfolio_collection.find_one({"portfolioId": portfolio_id})
        portfolio_name = "Unknown"
        if portfolio and "portfolioName" in portfolio: portfolio_name = portfolio["portfolioName"]
        else: logger.warning(f"Portfolio document for ID {portfolio_id} not found or missing 'portfolioName'. Using default.")

        pipeline = [
            {"$match": {"portfolioId": portfolio_id}},
            {"$group": {
                "_id": "$portfolioId", "totalTrades": {"$sum": 1},
                "totalRealizedProfit": {"$sum": {"$toDouble": "$realizedProfit"}},
                "averagePrice": {"$avg": {"$toDouble": "$price"}}
            }}
        ]
        stats_cursor = trade_collection.aggregate(pipeline)
        stats_list = list(stats_cursor)
        if not stats_list:
            logger.info(f"未找到 portfolioId={portfolio_id} 的统计数据")
            return PortfolioStats(portfolioId=portfolio_id, portfolioName=portfolio_name, totalTrades=0, totalRealizedProfit=0.0, averagePrice=0.0)
        stats_data = stats_list[0]
        result = PortfolioStats(
            portfolioId=portfolio_id, portfolioName=portfolio_name,
            totalTrades=stats_data.get("totalTrades", 0),
            totalRealizedProfit=stats_data.get("totalRealizedProfit", 0.0),
            averagePrice=stats_data.get("averagePrice", 0.0)
        )
        logger.info(f"返回 portfolioId={portfolio_id} 的统计数据")
        return result
    except Exception as e:
        logger.error(f"查询 portfolioId={portfolio_id} 统计数据错误: {e}")
        raise HTTPException(status_code=500, detail="查询统计数据失败")
# --- 结束 HTTP API 端点 ---


# 启动服务器
if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI 服务器 (HTTP 和 WebSocket)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)