import requests
import json
import time
from datetime import datetime
import logging
import schedule
import os
from collections import defaultdict
from pymongo import MongoClient
from bson import json_util

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trade_history.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB 配置
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = "binance_trades"
TRADE_COLLECTION = "trade_history"
PORTFOLIO_COLLECTION = "portfolio_mappings"

# Binance API 配置
bns_uuid = os.getenv("BNS_UUID", "YOUR_BNC_UUID")
url = "https://www.binance.com/bapi/futures/v1/friendly/future/copy-trade/lead-portfolio/trade-history"
headers = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
    "Referer": "https://www.binance.com/zh-CN/copy-trading/lead-details/4443392216295112961?timeRange=30D",
    "Origin": "https://www.binance.com",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "X-Requested-With": "XMLHttpRequest",
    "bns-uuid": bns_uuid
}

# 配置参数
time_window = 5*60000  # 1分钟去重时间窗口（毫秒）
fetch_interval = 30  # 30秒查询一次
portfolio_ids = {
    "4515721689070429440": "蒋大侠聊量化（公域）",
    "4470506398478690304": "小黑的复利之路",
    "4420248602321069312": "傑哥新視界",
    "3865635095524633345": "币胜量化机器人",
    "4389541053511483905": "创造奇迹666"
}
page_size = 100

# MongoDB 连接
def get_mongo_collections():
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        trade_collection = db[TRADE_COLLECTION]
        portfolio_collection = db[PORTFOLIO_COLLECTION]
        # 创建索引以优化查询
        trade_collection.create_index([("symbol", 1), ("time", 1), ("portfolioId", 1)], unique=True)
        portfolio_collection.create_index([("portfolioId", 1)], unique=True)
        return trade_collection, portfolio_collection
    except Exception as e:
        logger.error(f"MongoDB 连接错误: {e}")
        return None, None

# 保存 portfolio ID 和名称映射
def save_portfolio_mappings(portfolio_collection):
    try:
        for portfolio_id, portfolio_name in portfolio_ids.items():
            portfolio_collection.update_one(
                {"portfolioId": portfolio_id},
                {"$set": {"portfolioId": portfolio_id, "portfolioName": portfolio_name}},
                upsert=True
            )
        logger.info("Portfolio ID 和名称映射已保存到数据库")
    except Exception as e:
        logger.error(f"保存 portfolio 映射错误: {e}")

# 发起 POST 请求
def fetch_copy_trade_history(url, headers, data, start_time, end_time):
    data_copy = data.copy()
    data_copy["startTime"] = start_time
    data_copy["endTime"] = end_time
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data_copy))
        response.raise_for_status()
        result = response.json()
        if result.get("code") != "000000" or not result.get("success"):
            logger.error(f"API 请求失败: code={result.get('code')}, message={result.get('message')}")
            return None
        return result
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP 错误: {http_err}")
        return None
    except Exception as err:
        logger.error(f"其他错误: {err}")
        return None

# 去重逻辑
def deduplicate_trades(trades, time_window, trade_collection, portfolio_id, portfolio_name):
    if not trades:
        return []

    trade_dict = defaultdict(list)
    for trade in trades:
        key = (trade["symbol"], trade["side"], trade["positionSide"])
        trade_dict[key].append(trade)

    deduplicated_trades = []
    for key, trade_list in trade_dict.items():
        trade_list.sort(key=lambda x: x["time"])
        i = 0
        while i < len(trade_list):
            current_trade = trade_list[i]
            current_time = current_trade["time"]
            
            # 检查 MongoDB 中是否已存在类似交易
            existing_trade = trade_collection.find_one({
                "symbol": current_trade["symbol"],
                "side": current_trade["side"],
                "positionSide": current_trade["positionSide"],
                "portfolioId": portfolio_id,
                "time": {"$gte": current_time - time_window, "$lte": current_time + time_window}
            })
            
            if not existing_trade:
                current_trade["portfolioId"] = portfolio_id
                current_trade["portfolioName"] = portfolio_name
                deduplicated_trades.append(current_trade)
                # 插入到 MongoDB
                try:
                    trade_collection.insert_one(current_trade)
                except Exception as e:
                    logger.error(f"MongoDB 插入错误: {e}")
            
            i += 1
            # 跳过时间窗口内的重复交易
            while i < len(trade_list) and trade_list[i]["time"] < current_time + time_window:
                i += 1

    return deduplicated_trades

# 单次获取和处理任务
def fetch_and_process():
    end_time = int(time.time() * 1000)
    start_time = end_time - fetch_interval * 1000
    trade_collection, portfolio_collection = get_mongo_collections()
    if trade_collection is None or portfolio_collection is None:
        logger.error("MongoDB 连接失败，跳过本次任务")
        return

    # 保存 portfolio ID 和名称映射
    save_portfolio_mappings(portfolio_collection)

    for portfolio_id, portfolio_name in portfolio_ids.items():
        all_trades = []
        page_number = 1
        data = {
            "pageNumber": page_number,
            "pageSize": page_size,
            "portfolioId": portfolio_id
        }

        logger.info(f"开始获取交易历史 (portfolioId={portfolio_id}, portfolioName={portfolio_name}): start_time={start_time}, end_time={end_time}")

        # 分页获取所有记录
        while True:
            data["pageNumber"] = page_number
            trade_history = fetch_copy_trade_history(url, headers, data, start_time, end_time)
            if not trade_history:
                logger.warning(f"无法获取交易历史 (portfolioId={portfolio_id})，跳过")
                break

            trade_data = trade_history.get("data", {})
            trades = trade_data.get("list", [])
            all_trades.extend(trades)
            logger.info(f"第 {page_number} 页获取到 {len(trades)} 条记录 (portfolioId={portfolio_id})")

            if len(trades) < page_size:
                break
            page_number += 1
            time.sleep(0.5)

        # 去重并存储到 MongoDB
        deduplicated_trades = deduplicate_trades(all_trades, time_window, trade_collection, portfolio_id, portfolio_name)
        logger.info(f"去重前记录数: {len(all_trades)} (portfolioId={portfolio_id})")
        logger.info(f"去重后记录数: {len(deduplicated_trades)} (portfolioId={portfolio_id})")

        # 输出交易信息
        if deduplicated_trades:
            logger.info(f"去重后的交易记录 (portfolioId={portfolio_id}, portfolioName={portfolio_name}):")
            for trade in deduplicated_trades:
                time_stamp = trade["time"]
                time_str = datetime.fromtimestamp(time_stamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                symbol = trade["symbol"]
                side = trade["side"]
                position_side = trade["positionSide"]
                price = trade["price"]
                realized_profit = trade["realizedProfit"]
                trade_type = {
                    ("BUY", "LONG"): "开多",
                    ("SELL", "LONG"): "平多",
                    ("SELL", "SHORT"): "开空",
                    ("BUY", "SHORT"): "平空"
                }.get((side, position_side), "未知")

                logger.info(
                    f"时间: {time_str}, 交易对: {symbol}, 方向: {side}, 价格: {price}, "
                    f"盈亏: {realized_profit}, 交易类型: {trade_type}, portfolioId: {portfolio_id}, portfolioName: {portfolio_name}"
                )

        # 保存到 JSON 文件
        # timestamp = time.strftime("%Y%m%d_%H%M%S")
        # output_file = f"deduplicated_trades_{portfolio_id}_{timestamp}.json"
        # with open(output_file, "w", encoding="utf-8") as f:
        #     json.dump(deduplicated_trades, f, indent=2, ensure_ascii=False, default=json_util.default)
        # logger.info(f"去重结果已保存到 {output_file} (portfolioId={portfolio_id})")

# 主程序
def main():
    schedule.every(fetch_interval).seconds.do(fetch_and_process)
    logger.info(f"启动定时任务，每 {fetch_interval} 秒获取一次交易历史")
    
    # 首次运行
    fetch_and_process()

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("程序终止")
            break
        except Exception as e:
            logger.error(f"程序错误: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()